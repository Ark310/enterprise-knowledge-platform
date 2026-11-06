using System.Diagnostics;
using System.Text.Json.Nodes;
using TD.Poc.Core;
using TD.Poc.Infrastructure;
Runtime.DisableQuickEdit();
Console.OutputEncoding=System.Text.Encoding.UTF8;
string FindRoot()
{
    var explicitRoot=Environment.GetEnvironmentVariable("TD_POC_ROOT");
    if(!string.IsNullOrEmpty(explicitRoot))return explicitRoot;
    foreach(var start in new[]{Environment.CurrentDirectory,AppContext.BaseDirectory})
        for(var p=new DirectoryInfo(start);p is not null;p=p.Parent)
            if(File.Exists(Path.Combine(p.FullName,"config","appsettings.json")))return p.FullName;
    throw new Exception("Cannot find solution root. Start with Start-POC.cmd or set TD_POC_ROOT.");
}
try
{
    var runtime=new Runtime(FindRoot());runtime.Progress+=Console.WriteLine;var workflow=new Workflow(runtime);var moduleReview=new ModuleReview(runtime);
    if(args.Contains("--version")){Console.WriteLine("TD POC 0.23.0");return;}
    await runtime.LoadSecret();
    if(args.Contains("--build-indexes")){Console.WriteLine(await runtime.Worker("build_indexes"));return;}
    if(args.Contains("--search-health")){Console.WriteLine(await runtime.Worker("search_health"));return;}
    if(args.Contains("--compare")){
        Console.WriteLine("Enter the search question to compare:");var query=Console.ReadLine();
        if(!string.IsNullOrWhiteSpace(query))DisplayComparison(await runtime.Worker("compare_search",new JsonObject{{"query",query},{"limit",20}}));return;
    }
    if(args.Contains("--migrate")){Console.WriteLine(await runtime.Worker("migrate"));return;}
    if(args.Contains("--process")){Console.WriteLine(await runtime.Worker("process",new JsonObject{{"limit",args.Contains("--pilot")?10:0}}));Console.WriteLine("Worker finished. Review totals above; close this window when ready.");return;}
    if(args.Contains("--status")){Console.WriteLine(await runtime.Worker("status"));return;}
    if(args.Contains("--preflight")){
        var loginCheck=await runtime.Run(runtime.Config["CodexExecutable"]!.GetValue<string>(),["login","status"],"",runtime.Root,false,TimeSpan.FromSeconds(30));
        if(loginCheck.Code!=0)throw new Exception("POC Codex login not ready. Run Setup-POC.cmd.");
        var check=await runtime.Codex("setup-check","Return exactly {\"ready\":true}. No tools.","Readiness only",Path.Combine(runtime.Root,"runtime","preflight",Guid.NewGuid().ToString("N")));
        if(check["ready"]?.GetValue<bool>()!=true)throw new Exception("Readiness failed");
        Console.WriteLine(await runtime.Worker("status"));return;
    }
    Console.WriteLine("TD Gap Analysis POC 0.23 | Codex A/B/C | local Qwen embeddings | automatic scan, MANUAL processing");
    Console.WriteLine("Checking database...");var dbStatus=await runtime.Worker("status");
    Console.WriteLine($"Database ready: {dbStatus["sources"]} sources; {dbStatus["vectors"]} source vectors.");
    Console.WriteLine("Checking Codex login...");
    var login=await runtime.Run(runtime.Config["CodexExecutable"]!.GetValue<string>(),["login","status"],"",runtime.Root,false,TimeSpan.FromSeconds(30));
    if(login.Code!=0)throw new Exception("Codex login check failed. Run Setup-POC.cmd to configure the isolated POC Codex login.");
    Console.WriteLine("Checking controlled Codex invocation (small readiness request, no source content)...");
    var ready=await runtime.Codex("startup-check","Return exactly one JSON object: {\"ready\":true}. Do not use tools.","Readiness check only.",Path.Combine(runtime.Root,"runtime","preflight",Guid.NewGuid().ToString("N")));
    if(ready["ready"]?.GetValue<bool>()!=true)throw new Exception("Codex readiness response was not valid.");
    Console.WriteLine("Loading embedding model (no source files processed)...");
    try {var warm=await runtime.Worker("warm");Console.WriteLine($"Local embeddings ready: {warm["model"]}, {warm["dimensions"]} dimensions.");}catch(Exception e){Console.WriteLine("MODEL NOT READY: "+e.Message+" Run Setup-LocalModel.cmd. Scanning remains available.");}
    async Task Scan()
    {
        var s=await runtime.Worker("scan");var files=s["files"]!.AsArray();
        Console.WriteLine($"Scan: {files.Count} files; {files.Count(x=>x?["state"]?.GetValue<string>()!="UNCHANGED")} new/pending extraction; {s["errors"]!.AsArray().Count} errors. No source data was imported or embedded.");
        Console.WriteLine($"Transcript grouping pending: {s["grouped_transcripts_pending"]}. /process prepares grouped passages; /search-health checks vectors for the current profile.");
        Console.WriteLine("Full manifest: runtime\\last-scan.json. Missing embeddings can be retried with /process even when files are unchanged.");
    }
    void StartWorker(bool pilot)
    {
        if(!OperatingSystem.IsWindows()){Console.WriteLine("Run with --process in a second terminal.");return;}
        var script=Path.Combine(runtime.Root,pilot?"Process-Pilot.cmd":"Process-Pending.cmd");
        Process.Start(new ProcessStartInfo{FileName=script,WorkingDirectory=runtime.Root,UseShellExecute=true});
        Console.WriteLine("Processing window opened. Main console remains available; check /status for completed work.");
    }
    async Task Test(string code)
    {
        Console.WriteLine("Enter recording path relative to C:\\S3 bucket Data, e.g. current-state\\User Master.mp4 (matching .srt required):");
        var rec=Console.ReadLine();if(string.IsNullOrWhiteSpace(rec))return;
        var path=await workflow.RunTest(code,rec.Replace('\\','/'));
        Console.WriteLine("Run output: "+path+"\nBring agent-a.json, agent-b.json and validation files here for review.");
    }
    void DisplayComparison(JsonNode report)
    {
        Console.WriteLine("Same question and embedding; three search modes:");
        foreach(var mode in report["modes"]!.AsObject()){
            var d=mode.Value!;Console.WriteLine($"  {mode.Key}: {d["milliseconds"]} ms; {d["final_count"]} matches; HNSW index used: {d["hnsw_index_used"]}");
        }
        Console.WriteLine($"Semantic ANN recall@k: {report["ann_semantic_recall_at_k"]!["recall"]} (same improved chunks).");
        Console.WriteLine("Grouped transcripts: "+report["grouped_transcripts"]+". Chunking comparison ready: "+report["chunking_comparison_ready"]);
        Console.WriteLine("Reports: "+report["report_markdown"]+" and "+report["report_json"]);
        Console.WriteLine("Timing excludes embedding/reasoning. If HNSW index used is false, this is not an ANN benchmark. Inspect the cited evidence for answer quality.");
    }
    await Scan();
    Console.WriteLine("Commands: /review | /results latest | /ask question | /compare question | /mode | /search-health | /help | /exit");
    Console.WriteLine("Or type a question for Agent C. Processing requires your explicit /process or /pilot command.");
    while(true)
    {
        Console.Write("\nYou> ");var input=Console.ReadLine();if(input is null||input.Trim()=="/exit")break;input=input.Trim();if(input.Length==0)continue;
        try
        {
            if(input=="/mode"){Console.WriteLine("Current search mode: "+(runtime.Config["SearchMode"]?.ToString()??"improved_hnsw")+". Choices: /mode old_exact | /mode improved_exact | /mode improved_hnsw");continue;}
            if(input.StartsWith("/mode ")){
                var mode=input[6..].Trim();
                if(mode is not("old_exact" or "improved_exact" or "improved_hnsw"))throw new Exception("Choose old_exact, improved_exact or improved_hnsw.");
                runtime.Config["SearchMode"]=mode;Console.WriteLine("Search mode for this session: "+mode+". A new review pins this mode; existing saved results are unchanged.");continue;
            }
            if(input=="/search-health"){Console.WriteLine(await runtime.Worker("search_health"));continue;}
            if(input.StartsWith("/compare ")){DisplayComparison(await runtime.Worker("compare_search",new JsonObject{{"query",input[9..].Trim()},{"limit",20}}));continue;}
            if(input.StartsWith("/resume "))
            {
                Console.WriteLine(ModuleReview.Display(await moduleReview.Resume(input[8..].Trim().Trim('"'))));continue;
            }
            if(input=="/review" || input.Equals("/test MODULE",StringComparison.OrdinalIgnoreCase))
            {
                Console.WriteLine("Recording path relative to data folder, e.g. current-state\\User Master.mp4 (matching imported SRT required):");
                var recording=Console.ReadLine();
                if(!string.IsNullOrWhiteSpace(recording))Console.WriteLine(ModuleReview.Display(await moduleReview.Review(recording)));
                continue;
            }
            if(input=="/results" || input.StartsWith("/results "))
            {
                Console.WriteLine(ModuleReview.Display(await moduleReview.Select(input=="/results"?"latest":input[9..].Trim())));continue;
            }
            if(input.StartsWith("/ask ")){Console.WriteLine("Agent C> "+await moduleReview.Ask(input[5..]));continue;}
            if(input=="/scan"){await Scan();continue;}
            if(input=="/process"||input=="/pilot"){StartWorker(input=="/pilot");continue;}
            if(input=="/status"){Console.WriteLine(await runtime.Worker("status"));continue;}
            if(input.StartsWith("/search ")){Console.WriteLine(await workflow.AnswerSearch(input[8..]));continue;}
            if(input.StartsWith("/run ")){await Test(input[5..].Trim().Trim('"'));continue;}
            if(input.StartsWith("/test ")){await Test(input[6..].Trim().ToUpperInvariant());continue;}
            if(input=="/help"){Console.WriteLine("/compare question compares all three search modes without invoking AI reasoning; /mode selects search mode for new searches/reviews; /search-health checks HNSW setup; /review reviews a whole recording in sections; /results latest selects an exact saved gap run; /ask asks about that selected run; /scan finds changes; /pilot processes first 10 allowlisted files; /process handles all files and retries missing vectors; /test runs A then B; /search asks evidence questions. Read docs\\START-HERE.md for test scope and limitations.");continue;}
            if(moduleReview.Selected is not null){Console.WriteLine("Agent C> "+await moduleReview.Ask(input));continue;}
            var response=await workflow.Chat(input);Console.WriteLine("Agent C> "+response["reply"]!.GetValue<string>());
            var action=response["action"]!.GetValue<string>();var argument=response["argument"]!.GetValue<string>();
            switch(action)
            {
                case "STATUS":Console.WriteLine(await runtime.Worker("status"));break;
                case "SCAN":await Scan();break;
                case "SEARCH":Console.WriteLine(await workflow.AnswerSearch(argument));break;
                case "RUN_TEST":
                    if(argument is not("T01" or "T02" or "T03" or "T04" or "T05"))throw new Exception("Coordinator may select only bundled test IDs. Use /run explicitly for a custom request.");
                    await Test(argument);break;
                case "PROCESS":Console.WriteLine("To retain manual control, type /process (all) or /pilot (10 files). No processing started.");break;
            }
        }
        catch(Exception e){var message=e.Message.Length>350?e.Message[..350]+"…":e.Message;Console.WriteLine("STOPPED: "+message+"\nNo final success is claimed. Export-LatestRun.cmd includes failure.json and complete worker logs.");}
    }
}
catch(Exception e){Console.Error.WriteLine("STARTUP/WORKER FAILED: "+e.Message);Environment.ExitCode=1;}
