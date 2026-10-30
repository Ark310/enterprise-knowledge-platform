using System.Text.Json.Nodes;
using System.Security.Cryptography;
using System.Text;
using TD.Poc.Infrastructure;
namespace TD.Poc.Core;

public sealed class ModuleReview(Runtime runtime)
{
    public JsonNode? Selected {get;private set;}
    string Instructions(string name)=>File.ReadAllText(Path.Combine(runtime.Root,"agents",name))+"\nCONTRACT:\n"+File.ReadAllText(Path.Combine(runtime.Root,"contracts","module-review.schema.json"));
    static JsonObject Envelope(string key,string kind)
    {
        var b=kind.StartsWith("DOCUMENTATION");
        return new JsonObject{{"contract_version","td-module-review-1.0"},{"run_id",key},{"test_id","MODULE_REVIEW"},{"module","Whole recording; modules identified in topic index"},{"topic","Whole-recording documentation coverage"},{"message_type",kind},{"sender",b?"ARTICLE_REVIEW":"CURRENT_STATE"},{"recipient",b?"HUMAN":"ARTICLE_REVIEW"},{"status","PARTIAL"},{"payload",new JsonObject()},{"next_action","Host validates, saves and embeds; human factual review remains required."}};
    }
    public async Task<JsonNode> Select(string key="latest")
    {
        Selected=await runtime.Worker("module_results",new JsonObject{{"run_key",key}});
        return Selected;
    }
    public static string Display(JsonNode report,bool detailed=false)
    {
        var text=$"Run: {report["run_key"]}\nStatus: {report["status"]}\n";
        if(report["rows"] is not JsonArray rows)return text+(report["message"]?.ToString()??"No final gap report.");
        if(report["source_revisions_current"]?.GetValue<bool>()==false)text+="WARNING: Some cited source revisions have been superseded. This is a historical snapshot.\n";
        text+="Summary: "+report["summary"]+"\n";
        foreach(var row in rows)
        {
            text+=$"\n{row!["topic_id"]} | {row["coverage"]} | {row["title"]}\n";
            if(!detailed)continue;
            text+=$"{row["module"]}: {row["reason"]}\n";
            foreach(var cite in row["article_citations"]!.AsArray())text+="Article: "+cite!["article_title"]+" | "+cite["locator"]+"\nExcerpt: "+cite["excerpt"]+"\n";
            foreach(var action in row["actions"]!.AsArray())text+="Action: "+action+"\n";
        }
        return text+"\nScope: "+report["coverage"]+"\nFindings remain AGENT_PROPOSED; no exhaustive absence or human approval claimed.";
    }
    public async Task<string> Ask(string question)
    {
        if(Selected is null)await Select();
        var folder=Path.Combine(runtime.Root,"runtime","chat",Guid.NewGuid().ToString("N"));
        var context=new JsonObject{{"question",question},{"selected_run",Selected!.DeepClone()}};
        var answer=await runtime.Codex("coordinator","Answer from ONLY the selected run below. Explain coverage, missing-in-reviewed-sources, concrete work and uncertainties. Cite topic IDs, original paths and evidence. If source_revisions_current is false, disclose that the report cites superseded revisions. Do not mix other runs, invent completion, claim human verification or execute anything. Return exactly {\"reply\":string,\"action\":\"NONE\",\"argument\":\"\"}.",context.ToJsonString(),folder);
        if(answer["action"]?.ToString()!="NONE")throw new Exception("Run answer attempted an unsupported action");
        return answer["reply"]?.ToString()??throw new Exception("No run answer");
    }
    private string stage="idle";
    private void Stage(string work,string value)
    {
        stage=value;File.WriteAllText(Path.Combine(work,"workflow-state.json"),new JsonObject{{"stage",stage},{"updated_at",DateTimeOffset.Now.ToString("o")}}.ToJsonString());
        runtime.RoleLog(value);
    }
    private async Task Fail(string work,string key,Exception error)
    {
        runtime.RecordFailure(work,stage,error);
        runtime.RoleLog("ERROR: "+error.Message);
        runtime.EndRole(false,$"Stopped at {stage}; full details are in failure.json.");
        File.WriteAllText(Path.Combine(work,"workflow-state.json"),new JsonObject{{"stage",stage},{"status","FAILED"},{"error",error.Message}}.ToJsonString());
        try{await runtime.Worker("fail_run",new JsonObject{{"run_key",key},{"work",work}});}catch{}
    }
    public async Task<JsonNode> Review(string recording)
    {
        Selected=null;
        var start=await runtime.Worker("module_start",new JsonObject{{"recording",recording.Replace('\\','/')}});
        var work=start["work"]!.ToString();var key=start["run_key"]!.ToString();
        runtime.Log("Review: "+key);
        try
        {
            runtime.BeginRole(work,"A");
            foreach(var section in start["sections"]!.AsArray())
            {
                var id=section!["id"]!.ToString();Stage(work,$"A section {id} of {start["sections"]!.AsArray().Count}: {section["start"]}–{section["end"]} seconds");
                var packet=await runtime.Worker("module_section",new JsonObject{{"work",work},{"section_id",id}});
                var context=new JsonObject{{"envelope",Envelope(key,"CURRENT_STATE_SECTION")},{"evidence",packet.DeepClone()}};
                var images=packet["frames"]!.AsArray().Select(x=>x!["path"]!.ToString());
                await runtime.Codex("a",Instructions("agent-a-module.md"),context.ToJsonString(),Path.Combine(work,id),images);
                var valid=await runtime.Worker("module_check_section",new JsonObject{{"work",work},{"section_id",id}});
                if(valid["valid"]?.GetValue<bool>()!=true)throw new Exception("A section validation failed: "+valid);
            }
            await FinishA(work,key);
            return await FinishB(work,key);
        }
        catch(Exception e){await Fail(work,key,e);throw;}
    }
    public async Task<JsonNode> Resume(string work)
    {
        Selected=null;
        var resume=await runtime.Worker("module_resume_start",new JsonObject{{"work",Path.GetFullPath(work)}});
        var key=resume["run_key"]!.ToString();work=resume["work"]!.ToString();
        runtime.Log("Resuming "+key+" from "+resume["checkpoint"]);
        try
        {
            if(resume["checkpoint"]!.ToString()!="A_SAVED_AND_EMBEDDED")
            {runtime.BeginRole(work,"A");await FinishA(work,key);}
            else runtime.Log("Agent A's stored records and vectors verified; reusing them unchanged.");
            return await FinishB(work,key);
        }
        catch(Exception e){await Fail(work,key,e);throw;}
    }
    private async Task FinishA(string work,string key)
    {
        Stage(work,"A consolidating supported topics");
        var collected=await runtime.Worker("module_collect",new JsonObject{{"work",work}});
        var index=await runtime.Codex("index",Instructions("agent-a-module.md"),new JsonObject{{"envelope",Envelope(key,"TOPIC_INDEX")},{"validated_observations",collected.DeepClone()}}.ToJsonString(),work);
        File.WriteAllText(Path.Combine(work,"topic-index.json"),index.ToJsonString());
        Stage(work,"A validating handoff, saving records and embedding observations");
        var saved=await runtime.Worker("module_save_a",new JsonObject{{"work",work}});
        runtime.EndRole(true,$"Validated, saved and embedded {saved["records"]} observations.");
    }
    private async Task<JsonNode> FinishB(string work,string key)
    {
        runtime.BeginRole(work,"B");Stage(work,"B retrieving documentation separately for each topic");
        var evidence=await runtime.Worker("module_retrieve",new JsonObject{{"work",work}});
        var topics=evidence["topics"]!.AsArray();var batches=Path.Combine(work,"batches");Directory.CreateDirectory(batches);
        for(var offset=0;offset<topics.Count;offset+=3)
        {
            var id=$"batch-{offset/3+1:D3}";var slice=topics.Skip(offset).Take(3).ToArray();
            var ids=new JsonArray(slice.Select(x=>JsonValue.Create(x!["topic"]!["topic_id"]!.ToString())).ToArray());
            File.WriteAllText(Path.Combine(batches,id+".json"),new JsonObject{{"topic_ids",ids.DeepClone()}}.ToJsonString());
            var context=new JsonObject{{"envelope",Envelope(key,"DOCUMENTATION_GAP_BATCH")},{"module_context",new JsonArray(topics.Select(x=>x!["topic"]!.DeepClone()).ToArray())},{"evidence_scope","All passages supplied in this batch are shared across its requested topics. This is one whole-recording review."},{"topics",new JsonArray(slice.Select(x=>x!.DeepClone()).ToArray())}};
            var folder=Path.Combine(batches,id);Directory.CreateDirectory(folder);
            var fingerprint=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(context.ToJsonString())));
            var checkpoint=Path.Combine(folder,"validated-context.sha256");
            async Task<JsonNode> Validate()=>await runtime.Worker("module_check_batch",new JsonObject{{"work",work},{"batch_id",id},{"topic_ids",ids.DeepClone()}});
            Stage(work,$"B {id}: {Math.Min(offset+3,topics.Count)} of {topics.Count} topics");
            if(File.Exists(checkpoint)&&File.ReadAllText(checkpoint)==fingerprint&&File.Exists(Path.Combine(folder,"b.json")))
            {
                var cached=await Validate();
                if(cached["valid"]?.GetValue<bool>()==true){runtime.RoleLog(id+": verified checkpoint reused.");continue;}
            }
            await BatchRecovery.Run(async (attempt,feedback)=>
            {
                var input=context.DeepClone().AsObject();
                if(feedback is not null)input["correction_feedback"]=new JsonObject{{"validation",feedback.DeepClone()},{"previous_output",JsonNode.Parse(File.ReadAllText(Path.Combine(folder,"b.json")))}};
                runtime.RoleLog($"{id}: attempt {attempt}/3 (whole-module coverage).");
                var attemptFolder=Path.Combine(folder,"attempt-"+DateTime.UtcNow.ToString("yyyyMMddHHmmssfff")+"-"+Guid.NewGuid().ToString("N"));
                await runtime.Codex("b",Instructions("agent-b-gaps.md"),input.ToJsonString(),attemptFolder);
                File.Copy(Path.Combine(attemptFolder,"b.json"),Path.Combine(folder,"b.json"),true);
            },async ()=>
            {
                var result=await Validate();
                File.WriteAllText(Path.Combine(folder,"validation-"+Guid.NewGuid().ToString("N")+".json"),result.ToJsonString());
                return result;
            });
            File.WriteAllText(checkpoint,fingerprint);
        }
        Stage(work,"B validating final gap list, saving records and embedding findings");
        Selected=await runtime.Worker("module_finalize",new JsonObject{{"work",work}});
        File.WriteAllText(Path.Combine(work,"gap-list.json"),Selected.ToJsonString());
        File.WriteAllText(Path.Combine(work,"gap-list.txt"),Display(Selected,true));
        runtime.EndRole(true,"Gap list validated, saved and embedded.");Stage(work,"RESULTS_READY");
        runtime.Log("Results ready. /results latest shows the summary; /ask discusses this run.");
        return Selected;
    }
}
