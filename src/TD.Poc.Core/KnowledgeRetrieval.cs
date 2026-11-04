using System.Text;
using System.Text.Json.Nodes;
using TD.Poc.Infrastructure;
namespace TD.Poc.Core;

public interface IKnowledgeHost
{
    string Root {get;}
    Task<JsonNode> Worker(string operation,JsonObject arguments);
    Task<JsonNode> Model(string role,string instructions,string context,string folder);
    void Begin(string folder,string role);
    void End(bool success,string message);
    void Failure(string folder,Exception error);
}
public sealed class KnowledgeRuntimeHost(Runtime runtime):IKnowledgeHost
{
    public string Root=>runtime.Root;
    public Task<JsonNode> Worker(string op,JsonObject args)=>runtime.Worker(op,args);
    public Task<JsonNode> Model(string role,string instructions,string context,string folder)=>runtime.Codex(role,instructions,context,folder);
    public void Begin(string folder,string role)=>runtime.BeginRole(folder,role);
    public void End(bool success,string message)=>runtime.EndRole(success,message);
    public void Failure(string folder,Exception error)=>runtime.RecordFailure(folder,"knowledge-retrieval",error);
}
public sealed class KnowledgeRetrieval(IKnowledgeHost host)
{
    private string session=Guid.NewGuid().ToString();
    private readonly List<JsonNode> history=[];
    public string? LastFolder {get;private set;}
    public string? LastResult {get;private set;}
    public void NewSession(){session=Guid.NewGuid().ToString();history.Clear();LastFolder=null;LastResult=null;}
    private string Instructions(string file,string part)=>File.ReadAllText(Path.Combine(host.Root,"agents",file))+"\nOUTPUT CONTRACT (only this definition):\n"+JsonNode.Parse(File.ReadAllText(Path.Combine(host.Root,"contracts","knowledge-qa.schema.json")))!["$defs"]![part]!.ToJsonString();
    public async Task<string> Ask(string question)
    {
        question=question.Trim();
        if(question.Length is 0 or >12000)throw new ArgumentException("Enter a question between 1 and 12000 characters.");
        var id=Guid.NewGuid().ToString();var folder=Path.Combine(host.Root,"runtime","knowledge-runs",DateTime.UtcNow.ToString("yyyyMMdd-HHmmss")+"-"+id[..8]);
        Directory.CreateDirectory(folder);LastFolder=folder;LastResult=null;bool started=false;bool active=false;
        async Task<JsonNode> Work(string op,JsonObject? arguments=null){arguments??=new();arguments["turn_id"]=id;arguments["work"]=folder;return await host.Worker(op,arguments);}
        void Snapshot(string status,string note=""){File.WriteAllText(Path.Combine(folder,"turn.json"),new JsonObject{{"turn_id",id},{"session_id",session},{"question",question},{"status",status},{"note",note}}.ToJsonString());}
        async Task Event(string stage,JsonNode value)=>await Work("qa_event",new(){{"stage",stage},{"payload",value.DeepClone()}});
        async Task<string> Stop(string status,string note)
        {
            if(active){host.End(false,note);active=false;}
            await Work("qa_finish",new(){{"status",status},{"note",note}});Snapshot(status,note);
            history.Add(new JsonObject{{"question",question},{"outcome",note}});TrimHistory();
            File.WriteAllText(Path.Combine(folder,"result.txt"),note);LastResult=note;
            return note+"\nRun: "+folder;
        }
        try
        {
            await Work("qa_begin",new(){{"session_id",session},{"question",question}});started=true;Snapshot("PROCESSING");
            host.Begin(folder,"Knowledge");active=true;
            var context=new JsonObject{{"original_question",question},{"conversation",new JsonArray(history.Select(x=>x.DeepClone()).ToArray())}};
            var normalized=await host.Model("normalize",Instructions("knowledge-assistant.md","normalization")+"\nTASK: NORMALIZE ONLY. Return the normalization contract, not an answer.",context.ToJsonString(),folder);
            await Event("NORMALIZATION",normalized);
            var nv=await Work("qa_validate",new(){{"part","normalization"},{"original",question},{"object",normalized.DeepClone()}});
            if(nv["valid"]?.GetValue<bool>()!=true)return await Stop("CLARIFY","I could not safely normalize that question while preserving its names and identifiers. Please rephrase it or confirm the intended product, version and source names.");
            if(normalized["needs_clarification"]!.GetValue<bool>())return await Stop("CLARIFY",normalized["clarification_question"]!.GetValue<string>());
            File.WriteAllText(Path.Combine(folder,"normalization.json"),normalized.ToJsonString());
            var retrieved=await Work("qa_retrieve",new(){{"normalization",normalized.DeepClone()}});
            File.WriteAllText(Path.Combine(folder,"evidence.json"),retrieved.ToJsonString());
            var evidence=retrieved["evidence"]!.AsArray();
            if(evidence.Count==0)return await Stop("INSUFFICIENT_EVIDENCE","I couldn't retrieve supporting evidence from the imported dataset. Try a more specific product, topic or video title. This does not prove the information is absent.");
            var packet=new JsonObject{{"original_question",question},{"normalization",normalized.DeepClone()},{"conversation",new JsonArray(history.Select(x=>x.DeepClone()).ToArray())},{"retrieval",retrieved.DeepClone()}};
            JsonNode? feedback=null;
            for(var attempt=0;attempt<2;attempt++)
            {
                if(!active){host.Begin(folder,"Knowledge");active=true;}
                var input=packet.DeepClone().AsObject();if(feedback is not null)input["correction_feedback"]=feedback.DeepClone();
                var candidate=await host.Model("answer-"+attempt,Instructions("knowledge-assistant.md","answer")+"\nTASK: ANSWER. Return the answer contract. A correction must address all feedback without inventing evidence.",input.ToJsonString(),folder);
                await Event("DRAFT",candidate);
                var av=await Work("qa_validate",new(){{"part","answer"},{"object",candidate.DeepClone()},{"evidence",evidence.DeepClone()}});await Event("VALIDATION",av);
                host.End(true,"Draft saved; handing off to verification. No answer published yet.");active=false;
                if(av["valid"]?.GetValue<bool>()!=true){feedback=av;continue;}
                if(candidate["status"]!.GetValue<string>()!="ANSWER")
                    return await Stop(candidate["status"]!.GetValue<string>(),candidate["status"]!.GetValue<string>()=="CLARIFY"?candidate["clarification_question"]!.GetValue<string>():"The retrieved dataset does not establish a supported answer to this question. Try narrowing the scope or importing the relevant source.");
                host.Begin(folder,"Verifier");active=true;
                var verificationInput=packet.DeepClone().AsObject();verificationInput["candidate"]=candidate.DeepClone();
                var verdict=await host.Model("verify-"+attempt,Instructions("knowledge-verifier.md","verdict"),verificationInput.ToJsonString(),folder);
                await Event("VERIFICATION",verdict);
                var vv=await Work("qa_validate",new(){{"part","verdict"},{"object",verdict.DeepClone()},{"answer",candidate.DeepClone()}});await Event("VALIDATION",vv);
                var passed=vv["valid"]?.GetValue<bool>()==true && verdict["decision"]?.GetValue<string>()=="PASS";
                host.End(passed,passed?"Evidence and relevance checks passed. Saving the final answer.":"Answer not approved. "+(attempt==0?"One correction is allowed.":"Stopping without an unverified answer."));active=false;
                if(passed)
                {
                    // Prepare local output before committing. DB completion is authoritative after this point.
                    var result=Render(question,normalized,candidate,evidence);
                    var pending=Path.Combine(folder,"verified-answer.pending.txt");
                    File.WriteAllText(pending,result);Snapshot("AWAITING_SAVE");
                    await Work("qa_finish",new(){{"status","VERIFIED"},{"answer",candidate.DeepClone()},{"verdict",verdict.DeepClone()}});
                    LastResult=result;
                    string localWarning="";
                    try{File.Move(pending,Path.Combine(folder,"result.txt"),true);}
                    catch(Exception e) when(e is IOException or UnauthorizedAccessException){localWarning="\nThe verified answer is saved in PostgreSQL; local result-file finalization failed. /last can still display it in this session. The pending file is retained for recovery.";}
                    try{Snapshot("VERIFIED",localWarning);}catch(Exception e) when(e is IOException or UnauthorizedAccessException){localWarning+="\nLocal status snapshot could not be updated; PostgreSQL has the final status.";}
                    history.Add(new JsonObject{{"question",question},{"normalized_question",normalized["normalized_question"]!.DeepClone()},{"outcome",result[..Math.Min(result.Length,3000)]}});TrimHistory();
                    return result+localWarning+"\nRun: "+folder;
                }
                feedback=new JsonObject{{"verifier",verdict.DeepClone()},{"contract_validation",vv.DeepClone()}};
            }
            return await Stop("INSUFFICIENT_EVIDENCE","I could not produce an answer that passed the evidence and relevance checks after one correction. No unverified answer is being shown. The drafts and verifier feedback are saved for diagnosis.");
        }
        catch(Exception e)
        {
            if(active)host.End(false,"Stopped; see failure.json. No verified answer published.");
            host.Failure(folder,e);Snapshot(e is OperationCanceledException?"CANCELLED":"FAILED",e.Message);
            if(started)try{await Work("qa_finish",new(){{"status",e is OperationCanceledException?"CANCELLED":"FAILED"},{"note",e.Message}});}catch(Exception save){File.WriteAllText(Path.Combine(folder,"save-failure.txt"),save.Message);}
            throw;
        }
    }
    private void TrimHistory(){if(history.Count>4)history.RemoveRange(0,history.Count-4);}
    public static string Render(string original,JsonNode normalized,JsonNode answer,JsonArray evidence)
    {
        var refs=evidence.ToDictionary(x=>x!["evidence_id"]!.GetValue<string>(),x=>x!);
        var used=new HashSet<string>();var files=new HashSet<string>();var output=new StringBuilder();
        output.AppendLine("Evidence-checked answer (AI verification; not human approval)");
        if(normalized["normalized_question"]!.GetValue<string>()!=original)output.AppendLine("Interpreted question: "+normalized["normalized_question"]);
        foreach(var c in answer["claims"]!.AsArray())
        {
            var prefix=c!["basis"]!.ToString() switch{"INFERENCE"=>"Reasoned interpretation: ","REVIEW_REPORT"=>"Saved review finding (check approval status): ",_=>""};
            output.AppendLine("\n"+prefix+c["text"]);
            foreach(var cite in c["citations"]!.AsArray())
            {
                var id=cite!["evidence_id"]!.GetValue<string>();used.Add(id);var p=refs[id];files.Add(p["file"]!.ToString());
                output.AppendLine($"  [{id}] {p["file"]} | {p["locator"]?.ToJsonString()}");
                output.AppendLine("  Evidence: "+cite["excerpt"]!.GetValue<string>());
            }
        }
        foreach(var limit in answer["limitations"]!.AsArray())output.AppendLine("Limitation: "+limit);
        output.AppendLine($"\nUsed {used.Count} evidence passages/review records from {files.Count} distinct source paths/review labels. Retrieval is bounded, not exhaustive.");
        return output.ToString();
    }
}
