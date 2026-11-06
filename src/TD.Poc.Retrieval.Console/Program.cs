using System.Diagnostics;
using System.Text.Json.Nodes;
using TD.Poc.Core;
using TD.Poc.Infrastructure;
Runtime.DisableQuickEdit();Console.OutputEncoding=System.Text.Encoding.UTF8;
if(args.Contains("--version")){Console.WriteLine("TD Knowledge Retrieval POC 0.23.0");return;}
try
{
    var runtime=new Runtime(PocPaths.FindRoot());runtime.Progress+=Console.WriteLine;
    runtime.Config["SearchMode"]="improved_hnsw";
    runtime.Config["AgentTimeoutMinutes"]=runtime.Config["KnowledgeAgentTimeoutMinutes"]?.DeepClone()??JsonValue.Create(5);
    await runtime.LoadSecret();
    Console.WriteLine("Knowledge Retrieval POC 0.23 | dataset evidence + labelled reasoning | HNSW | verifier gate");
    await runtime.Worker("qa_ready");
    var login=await runtime.Run(runtime.Config["CodexExecutable"]!.GetValue<string>(),["login","status"],"",runtime.Root,false,TimeSpan.FromSeconds(30));
    if(login.Code!=0)throw new Exception("Codex login is not ready. Run Setup-POC.cmd.");
    Console.WriteLine("Checking existing embedding model and HNSW indexes...");
    var health=await runtime.Worker("search_health");
    if(health["hnsw_ready"]?.GetValue<bool>()!=true)throw new Exception("HNSW indexes are not ready. Run Build-Search-Indexes.cmd and retry.");
    Console.WriteLine($"Ready: {health["model"]}, {health["dimensions"]} dimensions. No source files were processed.");
    if(runtime.Config["StartupAutoScan"]?.GetValue<bool>()!=false){
        Console.WriteLine("Scanning local files (read-only; no import)...");
        var startupScan=await runtime.Worker("scan");
        Console.WriteLine($"Scan: {startupScan["files"]!.AsArray().Count} files, {startupScan["errors"]!.AsArray().Count} scan errors. New files need /process before retrieval. Manifest: runtime/last-scan.json.");
    }
    Console.WriteLine("Ask a question, or /ask question. /new clears conversation; /last shows the last result; /status; /scan; /process; /diagnose keyword; /help; /exit.");
    Console.WriteLine("Knowledge and Verifier activity windows show status, not private reasoning. Ctrl+C cancels active work; Q in an activity window cancels that phase.");
    var qa=new KnowledgeRetrieval(new KnowledgeRuntimeHost(runtime));
    while(true)
    {
        Console.Write("\nYou> ");var input=Console.ReadLine();if(input is null)break;input=input.Trim();if(input.Length==0)continue;
        try
        {
            if(input=="/exit")break;
            if(input=="/new"){qa.NewSession();Console.WriteLine("New conversation. Previous run history is retained.");continue;}
            if(input=="/last"){
                var file=qa.LastFolder is null?null:Path.Combine(qa.LastFolder,"result.txt");
                Console.WriteLine(qa.LastResult??(file is not null&&File.Exists(file)?File.ReadAllText(file):"No completed answer in this conversation. Check the last run folder for failures."));continue;
            }
            if(input.StartsWith("/diagnose ")){
                var report=await runtime.Worker("qa_diagnose",new JsonObject{{"query",input[10..].Trim()}});
                var matches=report["matching_source_versions"]!.AsArray();
                Console.WriteLine($"Direct text matches: {matches.Count} source versions (up to 100 shown in report).");
                foreach(var row in matches.Take(20))Console.WriteLine($"  Text passages: {row!["matching_units"]}; embedded passages: {row["embedded_matching_units"]}; {row["storage_uri"]}");
                Console.WriteLine("Full diagnostic: "+report["report_json"]);Console.WriteLine(report["note"]);continue;
            }
            if(input=="/status"){Console.WriteLine(await runtime.Worker("status"));continue;}
            if(input=="/scan"){
                var scan=await runtime.Worker("scan");Console.WriteLine($"Scan: {scan["files"]!.AsArray().Count} files; {scan["errors"]!.AsArray().Count} errors. Scan only: no import. Manifest: runtime/last-scan.json.");continue;
            }
            if(input=="/process"){
                if(!OperatingSystem.IsWindows()){Console.WriteLine("Run the Gap Console with --process in a second terminal.");continue;}
                Process.Start(new ProcessStartInfo{FileName=Path.Combine(runtime.Root,"Process-Pending.cmd"),WorkingDirectory=runtime.Root,UseShellExecute=true});
                Console.WriteLine("Import window opened. Finish processing before asking questions for a consistent dataset.");continue;
            }
            if(input=="/help"){
                Console.WriteLine("Ask about imported articles, current-state or existing-assets transcripts, or saved gap findings. General reasoning is allowed, but product facts need cited dataset evidence. /new starts a fresh conversation. /last repeats the last result. /scan checks files; /process imports them manually. /diagnose keyword checks imported text and vectors directly. Use Export-LatestRetrieval.cmd from a separate CMD to export diagnostic files. /exit returns to the launcher. Gap analysis commands belong in menu option 1.");continue;
            }
            if(input.StartsWith('/')&&!input.StartsWith("/ask ")){Console.WriteLine("Unknown command. Use /help or type a question.");continue;}
            Console.WriteLine(await qa.Ask(input.StartsWith("/ask ")?input[5..]:input));
        }
        catch(Exception e){Console.WriteLine("Question stopped: "+e.Message+"\nNo unverified answer was published. Export-LatestRetrieval.cmd captures the latest run. You can ask again.");}
    }
}
catch(Exception e){Console.Error.WriteLine("RETRIEVAL STARTUP FAILED: "+e.Message);Environment.ExitCode=1;}
