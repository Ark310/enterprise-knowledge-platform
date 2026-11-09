using System.Text.Json.Nodes;
using TD.Poc.Core;
using TD.Poc.Infrastructure;
namespace TD.Poc.Web;

public sealed class WorkspaceEngine
{
    private readonly Runtime runtime;private readonly int mode;
    private readonly SemaphoreSlim gate=new(1,1);private readonly object sync=new();
    private CancellationTokenSource? cancellation;private string? owner,chatId;private bool busy;private readonly List<string> progress=[];
    public bool Ready{get;private set;}public string Status{get;private set;}="Preparing local workspace…";
    public WorkspaceEngine(Runtime runtime,int mode){this.runtime=runtime;this.mode=mode;runtime.Progress+=line=>{Console.WriteLine(line);lock(sync){progress.Add(line);if(progress.Count>120)progress.RemoveAt(0);}};}
    public Task<JsonNode> Data(string op,JsonObject? args=null)=>runtime.Worker(op,args);
    public string PublicError(Exception ex)=>ex is OperationCanceledException?"Stopped. No completed answer was claimed.":ex.Message.Contains("worker",StringComparison.OrdinalIgnoreCase)||ex.Message.Contains("Codex",StringComparison.OrdinalIgnoreCase)?"The operation could not finish. See the agent window and local runtime logs; your saved chat remains available.":ex.Message;
    public async Task Initialize()
    {
        Console.WriteLine("Checking PostgreSQL, Codex login and local embeddings…");await runtime.LoadSecret();
        await Data("qa_ready");await Data("ui_list",new(){{"poc",mode}});
        var login=await runtime.Run(runtime.Config["CodexExecutable"]!.ToString(),["login","status"],"",runtime.Root,false,TimeSpan.FromSeconds(30));
        if(login.Code!=0)throw new Exception("Run Setup-POC.cmd to sign in to the POC Codex account.");
        await Data("warm");var health=await Data("search_health");if(health["hnsw_ready"]?.GetValue<bool>()!=true)throw new Exception("Run Build-Search-Indexes.cmd first.");
        if(runtime.Config["StartupAutoScan"]?.GetValue<bool>()!=false)await Data("scan");
        Ready=true;Status="Ready";
    }
    public async Task<JsonNode> CheckChat(Guid id){var c=await Data("ui_get",new(){{"chat_id",id.ToString()}});if(c["poc"]!.GetValue<int>()!=mode)throw new Exception("This chat belongs to the other POC. Start that POC to open it.");return c;}
    public async Task<JsonNode> GetChat(Guid id,long? before){await CheckChat(id);var a=new JsonObject{{"chat_id",id.ToString()}};if(before is not null)a["before"]=before.Value;return await Data("ui_get",a);}
    public JsonObject JobSnapshot(){lock(sync)return new(){{"busy",busy},{"chat_id",chatId},{"owner",owner},{"status",runtime.CurrentActivity??Status},{"progress",new JsonArray(progress.Select(x=>(JsonNode?)JsonValue.Create(x)).ToArray())}};}
    public void Stop()
    {
        lock(sync)if(busy)Status="Stopping…";
        cancellation?.Cancel();
    }
    public async Task<JsonObject> Submit(Guid id,string text,JsonArray attachments)
    {
        text=text.Trim();if(text.Length is 0 or >12000)throw new Exception("Enter a question or command (up to 12,000 characters).");
        await CheckChat(id);if(!await gate.WaitAsync(0))throw new Exception("An agent is working. Wait or stop it before sending another request.");
        var job=Guid.NewGuid().ToString();
        try{await Data("ui_claim",new(){{"owner",job}});}catch{gate.Release();throw;}
        cancellation=new();runtime.JobCancellation=cancellation.Token;
        lock(sync){owner=job;chatId=id.ToString();busy=true;Status="Working";progress.Clear();}
        _=RunJob(id,text,attachments.DeepClone().AsArray(),job);return new(){{"accepted",true},{"job",job}};
    }
    private async Task RunJob(Guid id,string text,JsonArray attachments,string job)
    {
        using var heartbeatStop=new CancellationTokenSource();
        var heartbeat=Task.Run(async()=>{try{while(true){await Task.Delay(20000,heartbeatStop.Token);await Data("ui_renew",new(){{"owner",job}});}}catch(OperationCanceledException){}catch{Stop();}});
        var state=new JsonObject();var response=new JsonObject();var body="";string? work=null;KnowledgeRetrieval? qa=null;
        try
        {
            var chat=await CheckChat(id);state=chat["context"]?.DeepClone().AsObject()??new();
            await Data("ui_assets",new(){{"chat_id",id.ToString()},{"ids",attachments.DeepClone()}});
            await SaveMessage(id,"user",text,new(){{"attachments",attachments.DeepClone()},{"job",job}});
            if(text=="/new")throw new Exception("Use New chat to start a separate conversation.");
            if(text=="/help")body=mode==2?"Ask a question or use /ask, /search, /scan, /process, /status. Paste or attach an image. Use New chat for a fresh conversation.":"Use /review followed by the recording path, /results latest or a run key, /ask a question, /search a question, /scan, /process, /status. Use New chat for another review.";
            else if(text is "/scan" or "/status" or "/process" or "/pilot")
            {
                var processing=text is "/process" or "/pilot";
                if(processing)runtime.BeginRole(Path.Combine(runtime.Root,"runtime","web-processing",job),"Processing");
                try{var result=await Data(text[1..] is "pilot"?"process":text[1..],new(){{"limit",text=="/pilot"?10:0}});body=result.ToJsonString(new(){WriteIndented=true});if(processing)runtime.EndRole(true,"Processing finished. Review totals in Workspace.");}
                catch{if(processing)runtime.EndRole(false,"Processing stopped. Partial work may have been saved; inspect status before retrying.");throw;}
            }
            else if(mode==2||text.StartsWith("/search "))
            {
                qa=new(new KnowledgeRuntimeHost(runtime));qa.RestoreState(id.ToString(),state["qa"]);
                var question=text.StartsWith("/ask ")?text[5..]:text.StartsWith("/search ")?text[8..]:text;
                body=await qa.Ask(question,attachments);state["qa"]=qa.ExportState();work=qa.LastFolder;
                var turn=JsonNode.Parse(File.ReadAllText(Path.Combine(work!,"turn.json")))!;response["status"]=turn["status"]?.DeepClone();
                if(turn["status"]?.ToString()=="VERIFIED")
                {
                    var dbAnswer=await Data("ui_answer",new(){{"turn_id",turn["turn_id"]!.ToString()},{"chat_id",id.ToString()}});
                    response["answer"]=dbAnswer["answer"]?.DeepClone();
                    var evidence=dbAnswer["evidence"]!.AsArray();response["evidence"]=evidence.DeepClone();
                    try{var presentation=await Data("ui_present",new(){{"chat_id",id.ToString()},{"evidence",evidence.DeepClone()}});response["sources"]=presentation["sources"]?.DeepClone();response["images"]=presentation["images"]?.DeepClone();if(presentation["unavailable"]?.AsArray().Count>0)response["source_warning"]="Some cited originals are missing or have changed since this run. Their previews are unavailable: "+presentation["unavailable"];}
                    catch(Exception ex){response["source_warning"]="The answer was saved, but some source previews could not be prepared. See the original paths in the saved evidence.";Console.Error.WriteLine(ex.Message);}
                }
            }
            else
            {
                var review=new ModuleReview(runtime);
                var cmd=text.Split(' ',2);var argument=cmd.Length==2?cmd[1].Trim():"";
                if(cmd[0]=="/review")
                {
                    if(argument.Length==0){body="Enter /review followed by the recording path, for example current-state\\System Admin_ Security_User Master Walkthrough.mp4";}
                    else{var report=await review.Review(argument);state["run_key"]=report["run_key"]!.DeepClone();body=ModuleReview.Display(report);response["review"]=report.DeepClone();}
                }
                else if(cmd[0]=="/results")
                {
                    var report=await review.Select(argument.Length==0?"latest":argument);state["run_key"]=report["run_key"]!.DeepClone();body=ModuleReview.Display(report);response["review"]=report.DeepClone();
                }
                
                else
                {
                    if(state["run_key"] is null){body="Select a saved review with /results latest, or start one with /review followed by its recording path.";}
                    else{
                        await review.Select(state["run_key"]!.ToString());
                        var files=await Data("ui_assets",new(){{"chat_id",id.ToString()},{"ids",attachments.DeepClone()}});
                        runtime.BeginRole(Path.Combine(runtime.Root,"runtime","web-c",job),"C");
                        try{body=await review.Ask(text.StartsWith("/ask ")?text[5..]:text,state["conversation"]?.AsArray(),files["images"]!.AsArray().Select(x=>x!["path"]!.ToString()),id.ToString());runtime.EndRole(true,"Saved review answer complete.");}catch{runtime.EndRole(false,"Review answer stopped.");throw;}
                        response["review"]=review.Selected!.DeepClone();response["source_unit_ids"]=review.LastSourceUnitIds.DeepClone();response["image_ids"]=review.LastImageIds.DeepClone();
                    }
                }
                var memory=state["conversation"]?.DeepClone().AsArray()??new();memory.Add(new JsonObject{{"user_message",text},{"assistant_reply_reference",body[..Math.Min(body.Length,6000)]}});while(memory.Count>4)memory.RemoveAt(0);state["conversation"]=memory;
                if(response["review"] is {} reportNode){var p=await Data("ui_review_sources",new(){{"chat_id",id.ToString()},{"report",reportNode.DeepClone()},{"unit_ids",response["source_unit_ids"]?.DeepClone()},{"image_ids",response["image_ids"]?.DeepClone()??new JsonArray()}});response["sources"]=p["sources"]?.DeepClone();response["images"]=p["images"]?.DeepClone();if(p["unavailable"]?.AsArray().Count>0)response["source_warning"]="Some cited originals are missing or have changed since this run. Their previews are unavailable: "+p["unavailable"];}
            }
            response["job"]=job;response["work"]=work;await Data("ui_state",new(){{"chat_id",id.ToString()},{"context",state}});await SaveMessage(id,"assistant",body,response);
            lock(sync)Status="Ready";
        }
        catch(Exception ex)
        {
            if(qa is not null)try{state["qa"]=qa.ExportState();await Data("ui_state",new(){{"chat_id",id.ToString()},{"context",state}});}catch{}
            body=PublicError(ex);try{await SaveMessage(id,"system",body,new(){{"status","STOPPED"},{"job",job}});}catch{}
            lock(sync)Status="Stopped — see chat";
        }
        finally
        {
            heartbeatStop.Cancel();try{await heartbeat;}catch{}
            try{await Data("ui_release",new(){{"owner",job}});}catch{}
            runtime.JobCancellation=CancellationToken.None;cancellation?.Dispose();cancellation=null;
            lock(sync)busy=false;gate.Release();
        }
    }
    private Task<JsonNode> SaveMessage(Guid chat,string role,string text,JsonObject payload)=>Data("ui_message",new(){{"id",Guid.NewGuid().ToString()},{"chat_id",chat.ToString()},{"role",role},{"body",text},{"payload",payload}});
}
