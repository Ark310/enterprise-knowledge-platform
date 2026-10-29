using System.Text.Json.Nodes;
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
    public static string Display(JsonNode report)
    {
        var text=$"Run: {report["run_key"]}\nStatus: {report["status"]}\n";
        if(report["rows"] is not JsonArray rows)return text+(report["message"]?.ToString()??"No final gap report.");
        if(report["source_revisions_current"]?.GetValue<bool>()==false)text+="WARNING: Some cited source revisions have been superseded. This is a historical snapshot.\n";
        text+="Summary: "+report["summary"]+"\n";
        foreach(var row in rows)
        {
            text+=$"\n{row!["topic_id"]} | {row["module"]} / {row["title"]} | {row["coverage"]}\n{row["reason"]}\n";
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
    public async Task<JsonNode> Review(string recording)
    {
        Selected=null;
        var start=await runtime.Worker("module_start",new JsonObject{{"recording",recording.Replace('\\','/')}});
        var work=start["work"]!.ToString();var key=start["run_key"]!.ToString();
        runtime.Log($"Whole-recording review {key}: {start["sections"]!.AsArray().Count} sections; frames sampled every two seconds. This takes longer than a targeted test.");
        try
        {
            foreach(var section in start["sections"]!.AsArray())
            {
                var id=section!["id"]!.ToString();runtime.Log($"A section {id}: {section["start"]}–{section["end"]} seconds");
                var packet=await runtime.Worker("module_section",new JsonObject{{"work",work},{"section_id",id}});
                var context=new JsonObject{{"envelope",Envelope(key,"CURRENT_STATE_SECTION")},{"evidence",packet.DeepClone()}};
                var images=packet["frames"]!.AsArray().Select(x=>x!["path"]!.ToString());
                await runtime.Codex("a",Instructions("agent-a-module.md"),context.ToJsonString(),Path.Combine(work,id),images);
                var valid=await runtime.Worker("module_check_section",new JsonObject{{"work",work},{"section_id",id}});
                if(valid["valid"]?.GetValue<bool>()!=true)throw new Exception("A section validation failed: "+valid);
            }
            var collected=await runtime.Worker("module_collect",new JsonObject{{"work",work}});
            var index=await runtime.Codex("index",Instructions("agent-a-module.md"),new JsonObject{{"envelope",Envelope(key,"TOPIC_INDEX")},{"validated_observations",collected.DeepClone()}}.ToJsonString(),work);
            File.WriteAllText(Path.Combine(work,"topic-index.json"),index.ToJsonString());
            runtime.Log("A topic index → validation, PostgreSQL save and shared local embeddings");
            await runtime.Worker("module_save_a",new JsonObject{{"work",work}});
            var evidence=await runtime.Worker("module_retrieve",new JsonObject{{"work",work}});
            var topics=evidence["topics"]!.AsArray();var batches=Path.Combine(work,"batches");Directory.CreateDirectory(batches);
            for(var offset=0;offset<topics.Count;offset+=3)
            {
                var id=$"batch-{offset/3+1:D3}";var slice=topics.Skip(offset).Take(3).ToArray();
                var ids=new JsonArray(slice.Select(x=>JsonValue.Create(x!["topic"]!["topic_id"]!.ToString())).ToArray());
                File.WriteAllText(Path.Combine(batches,id+".json"),new JsonObject{{"topic_ids",ids.DeepClone()}}.ToJsonString());
                var context=new JsonObject{{"envelope",Envelope(key,"DOCUMENTATION_GAP_BATCH")},{"topics",new JsonArray(slice.Select(x=>x!.DeepClone()).ToArray())}};
                runtime.Log($"B {id}: coverage for {string.Join(", ",ids.Select(x=>x!.ToString()))}");
                await runtime.Codex("b",Instructions("agent-b-gaps.md"),context.ToJsonString(),Path.Combine(batches,id));
                var valid=await runtime.Worker("module_check_batch",new JsonObject{{"work",work},{"batch_id",id},{"topic_ids",ids.DeepClone()}});
                if(valid["valid"]?.GetValue<bool>()!=true)throw new Exception("B gap batch validation failed: "+valid);
            }
            Selected=await runtime.Worker("module_finalize",new JsonObject{{"work",work}});
            File.WriteAllText(Path.Combine(work,"gap-list.json"),Selected.ToJsonString());
            File.WriteAllText(Path.Combine(work,"gap-list.txt"),Display(Selected));
            runtime.Log("Gap list saved and embedded. Use /results latest or ask a question about the selected run.");
            return Selected;
        }
        catch
        {
            try{await runtime.Worker("fail_run",new JsonObject{{"run_key",key}});}catch{}
            throw;
        }
    }
}
