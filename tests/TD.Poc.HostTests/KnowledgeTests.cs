using System.Diagnostics;
using System.Text.Json.Nodes;
using TD.Poc.Core;
internal static class KnowledgeTests
{
    public static async Task<int> Run(string source)
    {
        int count=0;
        void Check(bool condition,string name){if(!condition)throw new Exception("FAIL QA: "+name);Console.WriteLine("PASS QA: "+name);count++;}
        Check(PocPaths.ProjectForChoice("1")=="TD.Poc.Console" && PocPaths.ProjectForChoice("2")=="TD.Poc.Retrieval.Console" && PocPaths.ProjectForChoice("1 & whoami")==null,"launcher only selects the two allowed projects");
        using(var h=new Fixture(source))
        {
            var qa=new KnowledgeRetrieval(h);var text=await qa.Ask("how do i edit a user?");
            Check(h.Models.SequenceEqual(new[]{"normalize","answer-0","verify-0"}),"normalization then answer then independent verifier");
            Check(text.Contains("Select Edit")&&text.Contains("user.md")&&text.Contains("Interpreted question"),"verified final answer includes normalization and original source");
            Check(h.FinalStatus=="VERIFIED"&&h.FinalAnswer is not null,"verified answer saved before publication");
            Check(h.Events.Count(x=>x=="VERIFICATION")==1,"verifier result retained in audit history");
            Check(h.Begins.SequenceEqual(new[]{"Knowledge","Verifier"}),"one activity phase for each agent on successful turn");
            Check(!h.Operations.Any(x=>x=="process"||x=="save_output"),"retrieval does not ingest or promote answers to gap/source vectors");
        }
        using(var h=new Fixture(source){WrongQuote=true})
        {
            var text=await new KnowledgeRetrieval(h).Ask("edit a user");
            Check(h.Models.SequenceEqual(new[]{"normalize","answer-0","answer-1"}),"fabricated citation receives only one correction and never reaches semantic pass");
            Check(h.FinalStatus=="INSUFFICIENT_EVIDENCE"&&h.FinalAnswer is null&&!text.Contains("SECRET_BAD_DRAFT"),"invalid draft is withheld and saved only as audit");
        }
        using(var h=new Fixture(source){RejectFirst=true})
        {
            await new KnowledgeRetrieval(h).Ask("edit a user");
            Check(h.Models.SequenceEqual(new[]{"normalize","answer-0","verify-0","answer-1","verify-1"}),"one bounded verifier correction followed by re-verification");
            Check(h.FinalStatus=="VERIFIED","corrected answer can pass");
        }
        using(var h=new Fixture(source){RejectAll=true})
        {
            var text=await new KnowledgeRetrieval(h).Ask("edit a user");
            Check(h.FinalStatus=="INSUFFICIENT_EVIDENCE"&&!text.Contains("Select Edit"),"repeated semantic rejection withholds the answer");
        }
        using(var h=new Fixture(source){Clarify=true})
        {
            var text=await new KnowledgeRetrieval(h).Ask("which one?");
            Check(h.Models.Count==1&&!h.Operations.Contains("qa_retrieve")&&h.FinalStatus=="CLARIFY"&&text.Contains("Which product"),"ambiguous normalization asks instead of searching wrong scope");
        }
        using(var h=new Fixture(source){EmptyEvidence=true})
        {
            var text=await new KnowledgeRetrieval(h).Ask("unknown topic");
            Check(h.Models.Count==1&&h.FinalStatus=="INSUFFICIENT_EVIDENCE"&&!text.Contains("Select Edit"),"no retrieved evidence cannot yield invented general-knowledge answer");
        }
        using(var h=new Fixture(source){Cancel=true})
        {
            try{await new KnowledgeRetrieval(h).Ask("edit a user");throw new Exception("Expected cancellation");}catch(OperationCanceledException){}
            Check(h.FinalStatus=="CANCELLED"&&h.Failed,"cancellation persists a non-success outcome");
        }
        using(var h=new Fixture(source){FailFinalSave=true})
        {
            try{await new KnowledgeRetrieval(h).Ask("edit a user");throw new Exception("Expected save failure");}catch(IOException){}
            Check(h.FinalStatus=="FAILED"&&h.Failed,"database save failure never returns a verified answer");
        }
        using(var h=new Fixture(source){BlockLocalFinal=true})
        {
            var qa=new KnowledgeRetrieval(h);var text=await qa.Ask("edit a user");
            Check(h.FinalStatus=="VERIFIED" && text.Contains("Select Edit") && !h.Failed,"local final-file failure cannot contradict a committed verified answer");
        }
        Console.WriteLine($"Knowledge host checks passed: {count}");return count;
    }
    private sealed class Fixture:IKnowledgeHost,IDisposable
    {
        public string Root{get;}=Path.Combine(Path.GetTempPath(),"td018-qa-"+Guid.NewGuid().ToString("N"));
        private readonly string source;
        public bool WrongQuote,RejectFirst,RejectAll,Clarify,EmptyEvidence,Cancel,FailFinalSave,Failed,BlockLocalFinal;
        public List<string> Models=[],Operations=[],Begins=[],Events=[];
        public string? FinalStatus;public JsonNode? FinalAnswer;
        public Fixture(string source){this.source=source;foreach(var dir in new[]{"agents","contracts"}){Directory.CreateDirectory(Path.Combine(Root,dir));foreach(var file in Directory.GetFiles(Path.Combine(source,dir)))File.Copy(file,Path.Combine(Root,dir,Path.GetFileName(file)));}}
        public void Begin(string f,string r)=>Begins.Add(r);
        public void End(bool success,string message){}
        public void Failure(string folder,Exception e)=>Failed=true;
        public Task<JsonNode> Model(string role,string instructions,string context,string folder)
        {
            Models.Add(role);if(Cancel)throw new OperationCanceledException();
            if(role=="normalize")return Task.FromResult<JsonNode>(new JsonObject{{"normalized_question","How do I edit a user?"},{"needs_clarification",Clarify},{"clarification_question",Clarify?"Which product do you mean?":""},{"changes",new JsonArray("spelling")},{"search_queries",new JsonArray()}});
            if(role.StartsWith("answer"))return Task.FromResult<JsonNode>(new JsonObject{{"status","ANSWER"},{"clarification_question",""},{"claims",new JsonArray(new JsonObject{{"id","C1"},{"text",WrongQuote?"SECRET_BAD_DRAFT":"Select Edit to edit a user."},{"basis","SOURCE"},{"citations",new JsonArray(new JsonObject{{"evidence_id","S1"},{"excerpt",WrongQuote?"Invented quote":"Select Edit"}})}})},{"limitations",new JsonArray("Saving is not demonstrated.")}});
            var reject=RejectAll||RejectFirst&&role=="verify-0";
            return Task.FromResult<JsonNode>(new JsonObject{{"decision",reject?"REVISE":"PASS"},{"addresses_question",true},{"normalization_faithful",true},{"premise_supported",true},{"human_readable",true},{"claim_checks",new JsonArray(new JsonObject{{"claim_id","C1"},{"supported",!reject},{"reason",reject?"Fix scope":"Directly supported"}})},{"feedback",new JsonArray(reject?"Narrow the answer":"")}});
        }
        public async Task<JsonNode> Worker(string op,JsonObject args)
        {
            Operations.Add(op);
            if(op=="qa_validate")
            {
                var psi=new ProcessStartInfo(OperatingSystem.IsWindows()?Path.Combine(source,".venv","Scripts","python.exe"):"python3"){RedirectStandardInput=true,RedirectStandardOutput=true,RedirectStandardError=true,UseShellExecute=false};
                psi.ArgumentList.Add(Path.Combine(source,"tests","qa_contract_bridge.py"));using var p=Process.Start(psi)!;
                await p.StandardInput.WriteAsync(args.ToJsonString());p.StandardInput.Close();var stdout=await p.StandardOutput.ReadToEndAsync();var stderr=await p.StandardError.ReadToEndAsync();await p.WaitForExitAsync();
                if(p.ExitCode!=0)throw new Exception(stderr);return JsonNode.Parse(stdout)!;
            }
            if(op=="qa_retrieve")return new JsonObject{{"evidence",EmptyEvidence?new JsonArray():new JsonArray(new JsonObject{{"evidence_id","S1"},{"kind","SOURCE"},{"text","Select Edit to open the existing user."},{"unit_id","fixture"},{"file","user.md"},{"locator",new JsonObject{{"line",1}}}})}};
            if(op=="qa_event")Events.Add(args["stage"]!.ToString());
            if(op=="qa_finish")
            {
                if(FailFinalSave&&args["status"]!.ToString()=="VERIFIED")throw new IOException("Fixture database unavailable");
                FinalStatus=args["status"]!.ToString();FinalAnswer=args["answer"]?.DeepClone();
                if(BlockLocalFinal&&FinalStatus=="VERIFIED")Directory.CreateDirectory(Path.Combine(args["work"]!.ToString(),"result.txt"));
            }
            return new JsonObject{{"saved",true}};
        }
        public void Dispose()=>Directory.Delete(Root,true);
    }
}
