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
            Check(h.Models.Contains("verify-0")&&h.Models.Contains("verify-1")&&h.FinalStatus=="INSUFFICIENT_EVIDENCE"&&!text.Contains("Select Edit"),"no retrieved evidence cannot yield invented general-knowledge answer");
            Check(text.Contains("Evidence gap:"),"insufficient answer explains the unresolved verification gap");
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
        using(var h=new Fixture(source){InitiallyInsufficient=true})
        {
            var text=await new KnowledgeRetrieval(h).Ask("edit a user");
            Check(h.Models.Contains("verify-0") && h.Models.Contains("verify-1"),"insufficient draft goes to verifier, then final answer is rechecked");
            Check(h.Operations.Count(x=>x=="qa_retrieve")==2 && h.FinalStatus=="VERIFIED","verifier can trigger one additional investigation round");
            Check(h.FollowupKeywords=="user edit","verifier topic keywords reach the expanded worker search");
        }
        using(var h=new Fixture(source){WithFrame=true})
        {
            await new KnowledgeRetrieval(h).Ask("edit a user");
            Check(h.ImageRoles.SequenceEqual(new[]{"answer-0","verify-0"}),"same frame attachment reaches Assistant and Verifier but not normalization");
        }
        using(var h=new Fixture(source){MissingScope=true})
        {
            await new KnowledgeRetrieval(h).Ask("edit a user");
            Check(h.Operations.Count(x=>x=="qa_retrieve")==2 && h.Models.Contains("verify-1"),"host coverage blocker triggers follow-up despite model PASS");
            Check(h.FinalStatus=="VERIFIED","scope repaired in follow-up is reverified before publication");
        }
        using(var h=new Fixture(source){MissingScope=true,PersistMissing=true})
        {
            var text=await new KnowledgeRetrieval(h).Ask("edit a user");
            Check(h.FinalStatus=="INSUFFICIENT_EVIDENCE" && h.FinalAnswer is null,"missing required source cannot be published after retry even when both model verdicts PASS");
            Check(text.Contains("Matching transcript missing"),"unresolved source gap is explained in the main console");
        }
        var display=KnowledgeRetrieval.Render("q",new JsonObject{{"normalized_question","q"}},new JsonObject{{"claims",new JsonArray(
            new JsonObject{{"id","C1"},{"section","ANSWER"},{"basis","SOURCE"},{"text","You can view the entries."},{"citations",new JsonArray(new JsonObject{{"evidence_id","S1"},{"excerpt","# Account display"}})}},
            new JsonObject{{"id","C2"},{"section","STEPS"},{"basis","SOURCE"},{"text","Select Posted."},{"citations",new JsonArray(new JsonObject{{"evidence_id","S2"},{"excerpt","Select Posted to open the display."}})}})},{"limitations",new JsonArray("Your version may use a different menu.")}},new JsonArray(
            new JsonObject{{"evidence_id","S1"},{"kind","SOURCE"},{"file","existing-assets/Long Folder/Account display/article.md"},{"locator",new JsonObject{{"line_start",1},{"line_end",1}}}},
            new JsonObject{{"evidence_id","S2"},{"kind","SOURCE"},{"file","existing-assets/Long Folder/Account display/article.md"},{"locator",new JsonObject{{"line_start",2},{"line_end",4}}}}));
        Check(display.Contains("Steps:")&&display.Contains("1. Select Posted."),"human-readable procedure has numbered steps");
        Check(display.Contains("Important notes:")&&display.Contains("Account display")&&!display.Contains("existing-assets/Long Folder"),"concise source names and notes replace internal path clutter");
        Check(display.Contains("Passage: Select Posted to open the display."),"display chooses supporting text rather than title-only quote");
        using(var h=new Fixture(source){Clarify=true,BlockStopContext=true})
        {
            var text=await new KnowledgeRetrieval(h).Ask("which user?");
            Check(h.FinalStatus=="CLARIFY"&&!h.Failed&&text.Contains("Which product"),"saved clarification survives local memory snapshot write failure");
        }
        using(var h=new Fixture(source){Clarify=true})
        {
            var q=new KnowledgeRetrieval(h);await q.Ask("two checkers for wire templates");h.Clarify=false;await q.Ask("this is for TradeDesk");
            Check(h.NormalizeContexts[1].Contains("two checkers for wire templates")&&h.NormalizeContexts[1].Contains("Which product"),"actual follow-up normalization input retains pending question and original request");
            q.NewSession();await q.Ask("password repetition");
            Check(!h.NormalizeContexts[2].Contains("two checkers"),"new conversation excludes prior topic from actual model input");
        }
        var memory=new ConversationState();
        memory.Record("Two checkers for wire templates",new JsonObject{{"normalized_question","Two checkers for wire templates"}},"CLARIFY","Desktop or Web?");
        Check(memory.Snapshot().ToJsonString().Contains("Two checkers")&&memory.Snapshot().ToJsonString().Contains("Desktop or Web?"),"clarification retains original task and pending question");
        memory.Record("TradeDesk",new JsonObject{{"normalized_question","Two checkers for wire templates in TradeDesk"}},"INSUFFICIENT_EVIDENCE","Assignment details unresolved");
        Check(memory.Snapshot().ToJsonString().Contains("Assignment details unresolved"),"insufficient response retains task context");
        var restored=new ConversationState();restored.Restore(memory.Snapshot());
        Check(restored.Snapshot().ToJsonString()==memory.Snapshot().ToJsonString(),"structured follow-up context survives save and restore");
        restored.Record("Explain step 3",null,"ANSWER","","3. Select the setting. This reply is an intent reference only.");
        var restarted=new ConversationState();restarted.Restore(restored.Snapshot());
        Check(restarted.Snapshot()["turns"]!.AsArray().Last()!["assistant_reply_reference"]!.ToString().Contains("Select the setting"),"assistant reply reference survives restart without becoming evidence");
        memory.Record("Is MFA available?",new JsonObject{{"normalized_question","Is MFA available?"},{"conversation_relation","NEW"}},"ANSWER","");
        Check(!memory.Snapshot().ToJsonString().Contains("Two checkers")&&memory.Snapshot()["active_task"]?["normalized_question"]?.ToString()=="Is MFA available?","topic change replaces active task instead of retaining old approval goal");
        memory.Clear();Check(!memory.Snapshot().ToJsonString().Contains("Two checkers"),"new session clears structured context");
        using(var h=new Fixture(source){Partial=true})
        {
            var text=await new KnowledgeRetrieval(h).Ask("edit a user");
            Check(h.FinalStatus=="VERIFIED"&&h.FinalAnswer?["status"]?.ToString()=="PARTIAL"&&text.Contains("Unresolved:")&&text.Contains("Next question:"),"approved partial publishes cited answer and gap");
            Check(text.Contains("incomplete"),"partial procedure clearly labelled incomplete");
        }
        using(var h=new Fixture(source){Partial=true,RejectAll=true})
        {
            var text=await new KnowledgeRetrieval(h).Ask("edit a user");
            Check(h.FinalStatus=="INSUFFICIENT_EVIDENCE"&&!text.Contains("Select Edit"),"rejected partial never auto-published");
        }
        Console.WriteLine($"Knowledge host checks passed: {count}");return count;
    }
    private sealed class Fixture:IKnowledgeHost,IDisposable
    {
        public string Root{get;}=Path.Combine(Path.GetTempPath(),"td018-qa-"+Guid.NewGuid().ToString("N"));
        private readonly string source;
        public bool BlockStopContext;public bool Partial;public bool MissingScope,PersistMissing; public bool WithFrame; public List<string> ImageRoles=[];
        public bool WrongQuote,RejectFirst,RejectAll,Clarify,EmptyEvidence,Cancel,FailFinalSave,Failed,BlockLocalFinal,InitiallyInsufficient;
        public List<string> NormalizeContexts=[];public List<string> Models=[],Operations=[],Begins=[],Events=[];
        public string? FollowupKeywords;public string? FinalStatus;public JsonNode? FinalAnswer;
        public Fixture(string source){this.source=source;foreach(var dir in new[]{"agents","contracts"}){Directory.CreateDirectory(Path.Combine(Root,dir));foreach(var file in Directory.GetFiles(Path.Combine(source,dir)))File.Copy(file,Path.Combine(Root,dir,Path.GetFileName(file)));}}
        public void Begin(string f,string r)=>Begins.Add(r);
        public void End(bool success,string message){}
        public void Failure(string folder,Exception e)=>Failed=true;
        public Task<JsonNode> Model(string role,string instructions,string context,string folder,IEnumerable<string>? images=null)
        {
            if(role=="normalize")NormalizeContexts.Add(context);Models.Add(role);if(images?.Any()==true){if(images.Single()!="fixture.jpg")throw new Exception("Unexpected image");ImageRoles.Add(role);}if(Cancel)throw new OperationCanceledException();
            if(role=="normalize")return Task.FromResult<JsonNode>(new JsonObject{{"conversation_relation","NEW"},{"request_parts",new JsonArray("Edit a user")},{"confirmed_context",new JsonArray()},{"assumptions",new JsonArray()},{"normalized_question","How do I edit a user?"},{"visual_check",false},{"recording_names",new JsonArray()},{"needs_clarification",Clarify},{"clarification_question",Clarify?"Which product do you mean?":""},{"changes",new JsonArray("spelling")},{"search_queries",new JsonArray()}});
            if(role.StartsWith("answer")&&EmptyEvidence || role=="answer-0"&&InitiallyInsufficient)return Task.FromResult<JsonNode>(new JsonObject{{"status","INSUFFICIENT_EVIDENCE"},{"clarification_question",""},{"claims",new JsonArray()},{"limitations",new JsonArray("Need source detail.")}});
            if(role.StartsWith("verify")&&EmptyEvidence || role=="verify-0"&&InitiallyInsufficient)return Task.FromResult<JsonNode>(new JsonObject{{"decision","INSUFFICIENT_EVIDENCE"},{"addresses_question",false},{"normalization_faithful",true},{"premise_supported",true},{"human_readable",true},{"requested_scope_complete",true},{"evidence_coverage_sufficient",true},{"coverage_reason","Fixture packet checked"},{"claim_checks",new JsonArray()},{"feedback",new JsonArray("Read user instructions.")},{"retrieval_queries",new JsonArray("user edit instructions")},{"retrieval_keywords",new JsonArray("user edit")},{"read_source_versions",new JsonArray()}});
            if(Partial&&role.StartsWith("answer"))return Task.FromResult<JsonNode>(new JsonObject{{"status","PARTIAL"},{"clarification_question","Is the provider configured?"},{"claims",new JsonArray(new JsonObject{{"id","C1"},{"text","Select Edit to edit a user."},{"basis","SOURCE"},{"section","STEPS"},{"citations",new JsonArray(new JsonObject{{"evidence_id","S1"},{"excerpt","Select Edit"}})}})},{"limitations",new JsonArray()},{"unresolved",new JsonArray("Provider integration unconfirmed")},{"procedure_complete",false}});
            if(Partial&&role.StartsWith("verify"))return Task.FromResult<JsonNode>(new JsonObject{{"decision",RejectAll?"REVISE":"PARTIAL_PASS"},{"addresses_question",true},{"normalization_faithful",true},{"premise_supported",true},{"human_readable",true},{"requested_scope_complete",false},{"evidence_coverage_sufficient",true},{"coverage_reason","User steps supported, integration missing"},{"claim_checks",new JsonArray(new JsonObject{{"claim_id","C1"},{"supported",!RejectAll},{"reason","Fixture"}})},{"feedback",new JsonArray()}});
            if(role.StartsWith("answer"))return Task.FromResult<JsonNode>(new JsonObject{{"status","ANSWER"},{"clarification_question",""},{"claims",new JsonArray(new JsonObject{{"id","C1"},{"text",WrongQuote?"SECRET_BAD_DRAFT":"Select Edit to edit a user."},{"basis","SOURCE"},{"citations",new JsonArray(new JsonObject{{"evidence_id","S1"},{"excerpt",WrongQuote?"Invented quote":"Select Edit"}})}})},{"limitations",new JsonArray("Saving is not demonstrated.")}});
            var reject=RejectAll||RejectFirst&&role=="verify-0";
            return Task.FromResult<JsonNode>(new JsonObject{{"decision",reject?"REVISE":"PASS"},{"addresses_question",true},{"normalization_faithful",true},{"premise_supported",true},{"human_readable",true},{"requested_scope_complete",true},{"evidence_coverage_sufficient",true},{"coverage_reason","Fixture packet checked"},{"claim_checks",new JsonArray(new JsonObject{{"claim_id","C1"},{"supported",!reject},{"reason",reject?"Fix scope":"Directly supported"}})},{"feedback",new JsonArray(reject?"Narrow the answer":"")}});
        }
        public async Task<JsonNode> Worker(string op,JsonObject args)
        {
            Operations.Add(op);
            if(op=="qa_retrieve"&&args["expand"]?.GetValue<bool>()==true)FollowupKeywords=args["keywords"]?.AsArray().FirstOrDefault()?.ToString();
            if(op=="qa_validate")
            {
                var psi=new ProcessStartInfo(OperatingSystem.IsWindows()?Path.Combine(source,".venv","Scripts","python.exe"):"python3"){RedirectStandardInput=true,RedirectStandardOutput=true,RedirectStandardError=true,UseShellExecute=false};
                psi.ArgumentList.Add(Path.Combine(source,"tests","qa_contract_bridge.py"));using var p=Process.Start(psi)!;
                await p.StandardInput.WriteAsync(args.ToJsonString());p.StandardInput.Close();var stdout=await p.StandardOutput.ReadToEndAsync();var stderr=await p.StandardError.ReadToEndAsync();await p.WaitForExitAsync();
                if(p.ExitCode!=0)throw new Exception(stderr);return JsonNode.Parse(stdout)!;
            }
            if(op=="qa_retrieve"&&WithFrame)return new JsonObject{{"evidence",new JsonArray(new JsonObject{{"evidence_id","S1"},{"kind","SOURCE"},{"text","Select Edit"},{"file","user.md"},{"locator",new JsonObject()}},new JsonObject{{"evidence_id","F2"},{"kind","FRAME"},{"text","Frame at 1 second"},{"path","fixture.jpg"},{"file","video.mp4"},{"locator",new JsonObject{{"start_seconds",1},{"end_seconds",1}}}})}};
            if(op=="qa_retrieve"&&MissingScope)return new JsonObject{{"scope",new JsonObject{{"blocking_errors",PersistMissing||Operations.Count(x=>x=="qa_retrieve")==1?new JsonArray("Matching transcript missing"):new JsonArray()}}},{"evidence",new JsonArray(new JsonObject{{"evidence_id","S1"},{"kind","SOURCE"},{"text","Select Edit"},{"file","user.md"},{"locator",new JsonObject()}})}};
            if(op=="qa_retrieve")return new JsonObject{{"evidence",EmptyEvidence?new JsonArray():new JsonArray(new JsonObject{{"evidence_id","S1"},{"kind","SOURCE"},{"text","Select Edit to open the existing user."},{"unit_id","fixture"},{"file","user.md"},{"locator",new JsonObject{{"line",1}}}})}};
            if(op=="qa_event")Events.Add(args["stage"]!.ToString());
            if(op=="qa_finish")
            {
                if(FailFinalSave&&args["status"]!.ToString()=="VERIFIED")throw new IOException("Fixture database unavailable");
                FinalStatus=args["status"]!.ToString();if(BlockStopContext&&FinalStatus=="CLARIFY")Directory.CreateDirectory(Path.Combine(args["work"]!.ToString(),"conversation-after.json"));FinalAnswer=args["answer"]?.DeepClone();
                if(BlockLocalFinal&&FinalStatus=="VERIFIED")Directory.CreateDirectory(Path.Combine(args["work"]!.ToString(),"result.txt"));
            }
            return new JsonObject{{"saved",true}};
        }
        public void Dispose()=>Directory.Delete(Root,true);
    }
}
