using System.Diagnostics;
using System.Text.Json.Nodes;
using TD.Poc.Core;
using TD.Poc.Infrastructure;
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
    var runtime=new Runtime(FindRoot());runtime.Progress+=Console.WriteLine;var workflow=new Workflow(runtime);
    if(args.Contains("--version")){Console.WriteLine("TD POC 0.10.0");return;}
    await runtime.LoadSecret();
    if(args.Contains("--migrate")){Console.WriteLine(await runtime.Worker("migrate"));return;}
    if(args.Contains("--process")){Console.WriteLine(await runtime.Worker("process",new JsonObject{{"limit",args.Contains("--pilot")?10:0}}));Console.WriteLine("Worker finished. Review totals above; close this window when ready.");return;}
    if(args.Contains("--status")){Console.WriteLine(await runtime.Worker("status"));return;}
    Console.WriteLine("TD POC 0.10 | Codex A/B/C | local Qwen embeddings | automatic scan, MANUAL processing");
    Console.WriteLine("Checking database...");Console.WriteLine(await runtime.Worker("status"));
    Console.WriteLine("Checking Codex login...");
    var login=await runtime.Run(runtime.Config["CodexExecutable"]!.GetValue<string>(),["login","status"],"",runtime.Root,false,TimeSpan.FromSeconds(30));
    if(login.Code!=0)throw new Exception("Codex login check failed. Run codex login in CMD first.");
    Console.WriteLine("Checking controlled Codex invocation (small readiness request, no source content)...");
    var ready=await runtime.Codex("startup-check","Return exactly one JSON object: {\"ready\":true}. Do not use tools.","Readiness check only.",Path.Combine(runtime.Root,"runtime","preflight",Guid.NewGuid().ToString("N")));
    if(ready["ready"]?.GetValue<bool>()!=true)throw new Exception("Codex readiness response was not valid.");
    Console.WriteLine("Loading embedding model (no source files processed)...");
    try {Console.WriteLine(await runtime.Worker("warm"));}catch(Exception e){Console.WriteLine("MODEL NOT READY: "+e.Message+" Run Setup-LocalModel.cmd. Scanning remains available.");}
    async Task Scan()
    {
        var s=await runtime.Worker("scan");var files=s["files"]!.AsArray();
        Console.WriteLine($"Scan: {files.Count} files; {files.Count(x=>x?["state"]?.GetValue<string>()!="UNCHANGED")} new/pending extraction; {s["errors"]!.AsArray().Count} errors. No source data was imported or embedded.");
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
    await Scan();
    Console.WriteLine("Commands: /scan | /process | /pilot | /status | /search question | /test T02 | /test T04 | /test T05 | /help | /exit");
    Console.WriteLine("Or type a question for Agent C. Processing requires your explicit /process or /pilot command.");
    while(true)
    {
        Console.Write("\nYou> ");var input=Console.ReadLine();if(input is null||input.Trim()=="/exit")break;input=input.Trim();if(input.Length==0)continue;
        try
        {
            if(input=="/scan"){await Scan();continue;}
            if(input=="/process"||input=="/pilot"){StartWorker(input=="/pilot");continue;}
            if(input=="/status"){Console.WriteLine(await runtime.Worker("status"));continue;}
            if(input.StartsWith("/search ")){Console.WriteLine(await workflow.AnswerSearch(input[8..]));continue;}
            if(input.StartsWith("/run ")){await Test(input[5..].Trim().Trim('"'));continue;}
            if(input.StartsWith("/test ")){await Test(input[6..].Trim().ToUpperInvariant());continue;}
            if(input=="/help"){Console.WriteLine("/scan finds changes; /pilot processes first 10 allowlisted files; /process handles all files and retries missing vectors; /test runs A then B; /search asks evidence questions. Read docs\\START-HERE.md for test scope and limitations.");continue;}
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
        catch(Exception e){Console.WriteLine("STOPPED: "+e.Message+"\nNo successful handoff is claimed. Check runtime logs.");}
    }
}
catch(Exception e){Console.Error.WriteLine("STARTUP/WORKER FAILED: "+e.Message);Environment.ExitCode=1;}
