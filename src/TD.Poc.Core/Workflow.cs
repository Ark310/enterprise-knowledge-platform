using System.Text.Json.Nodes;
using TD.Poc.Infrastructure;
namespace TD.Poc.Core;
public sealed class Workflow(Runtime runtime)
{
    private readonly List<JsonObject> history=[];
    private string Instructions(string name)=>File.ReadAllText(Path.Combine(runtime.Root,"agents",name));
    public async Task<JsonNode> Chat(string message)
    {
        history.Add(new JsonObject{{"role","user"},{"text",message}});
        if(history.Count>16)history.RemoveRange(0,history.Count-16);
        var folder=Path.Combine(runtime.Root,"runtime","chat",Guid.NewGuid().ToString("N"));
        var status=await runtime.Worker("status");
        var context=new JsonObject{{"history",new JsonArray(history.Select(x=>(JsonNode)x.DeepClone()).ToArray())},{"actual_status",status}};
        var answer=await runtime.Codex("coordinator",Instructions("agent-c-coordinator.md"),context.ToJsonString(),folder);
        var action=answer["action"]?.GetValue<string>();
        if(action is not("NONE" or "STATUS" or "SCAN" or "PROCESS" or "SEARCH" or "RUN_TEST"))throw new Exception("Coordinator requested an unsupported action; nothing executed.");
        if(answer["reply"] is null||answer["argument"] is null)throw new Exception("Coordinator response missing required fields.");
        history.Add(new JsonObject{{"role","assistant"},{"text",answer["reply"]!.GetValue<string>()}});
        return answer;
    }
    public async Task<string> AnswerSearch(string query)
    {
        var evidence=await runtime.Worker("search",new JsonObject{{"query",query},{"limit",20}});
        var folder=Path.Combine(runtime.Root,"runtime","chat",Guid.NewGuid().ToString("N"));
        var obj=await runtime.Codex("answer",Instructions("agent-c-coordinator.md")+"\nAnswer the question using only this retrieved evidence. action MUST be NONE. Cite original paths and locators. No import or test action.",new JsonObject{{"question",query},{"evidence",evidence}}.ToJsonString(),folder);
        var reply=obj["reply"]?.GetValue<string>()??throw new Exception("No answer returned");
        history.Add(new JsonObject{{"role","tool"},{"text",reply}});return reply;
    }
    public async Task<string> RunTest(string test,string recording)
    {
        var requestPath=test.EndsWith(".json",StringComparison.OrdinalIgnoreCase)?Path.GetFullPath(test):Path.Combine(runtime.Root,"tests","scenarios",test+"-original.json");
        if(!File.Exists(requestPath))throw new Exception("Request JSON not found. Choose T01 through T05 or use /run with a full request JSON path.");
        runtime.Log("Preparing "+test+" with pinned recording and SRT versions");
        var prep=await runtime.Worker("prepare_test",new JsonObject{{"request_path",requestPath},{"recording",recording}});
        var work=prep["work"]!.GetValue<string>();var runKey=prep["request"]!["run_id"]!.GetValue<string>();
        try
        {
            var schema=File.ReadAllText(Path.Combine(runtime.Root,"contracts","contracts-v2.schema.json"));
            var common=Instructions("shared-guardrails.md")+"\nAPPROVED JSON SCHEMA:\n"+schema;
            var images=prep["frames"]!.AsArray().Select(x=>x!["path"]!.GetValue<string>()).ToArray();
            // Use distinct names for host validation; original agent prompts retained alongside local adapter.
            var a=await runtime.Codex("a",Instructions("agent-a-current-state.md")+"\n"+common,prep["evidence"]!.ToJsonString(),work,images);
            File.WriteAllText(Path.Combine(work,"agent-a.json"),a.ToJsonString());
            runtime.Log("A → validation gate");
            var av=await runtime.Worker("save_output",new JsonObject{{"work",work},{"role","CURRENT_STATE"},{"output",Path.Combine(work,"agent-a.json")}});
            if(av["valid"]!.GetValue<bool>()!=true)throw new Exception("Agent A failed validation. Handoff stopped. See validation-a.json.");
            if(a["status"]!.GetValue<string>()=="BLOCKED"){runtime.Log("A is BLOCKED: B not started");await runtime.Worker("fail_run",new JsonObject{{"run_key",runKey}});return work;}
            runtime.Log("A validated and saved → observations embedded → B evidence retrieval");
            var bp=await runtime.Worker("prepare_b",new JsonObject{{"work",work}});
            bp.AsObject().Remove("upstream"); // Already supplied once as upstream_handoff; retain original evidence-b packet on disk.
            var bcontext=new JsonObject{{"upstream_handoff",a.DeepClone()},{"existing_evidence",bp},{"current_evidence",prep["evidence"]!.DeepClone()}};
            var b=await runtime.Codex("b",Instructions("agent-b-documentation-review.md")+"\n"+common,bcontext.ToJsonString(),work,images);
            File.WriteAllText(Path.Combine(work,"agent-b.json"),b.ToJsonString());
            runtime.Log("B → validation gate");
            var bv=await runtime.Worker("save_output",new JsonObject{{"work",work},{"role","ARTICLE_REVIEW"},{"output",Path.Combine(work,"agent-b.json")}});
            if(!bv["valid"]!.GetValue<bool>())throw new Exception("Agent B failed validation. See validation-b.json.");
            runtime.Log("B saved → findings embedded. Structural checks passed; factual review remains human work.");
            return work;
        }
        catch
        {
            try {await runtime.Worker("fail_run",new JsonObject{{"run_key",runKey}});}catch { }
            throw;
        }
    }
}
