using System.Diagnostics;
using System.Text;
using System.Text.Json.Nodes;
namespace TD.Poc.Infrastructure;

public sealed partial class Runtime
{
    public string Root { get; }
    public JsonObject Config { get; }
    public event Action<string>? Progress;
    public Runtime(string root)
    {
        Root=Path.GetFullPath(root);
        Config=JsonNode.Parse(File.ReadAllText(Path.Combine(Root,"config","appsettings.json")))!.AsObject();
        Directory.CreateDirectory(Path.Combine(Root,"runtime"));
    }
    public void Log(string text)
    {
        var line=$"[{DateTimeOffset.Now:HH:mm:ss}] {text}";
        Progress?.Invoke(line);
        File.AppendAllText(Path.Combine(Root,"runtime","workflow.log"),line+Environment.NewLine);
    }
    public async Task<JsonNode> Worker(string op,JsonObject? args=null)
    {
        var python=Config["PythonExecutable"]!.GetValue<string>();
        if(!Path.IsPathRooted(python)) python=Path.Combine(Root,python);
        var result=await Run(python,[Path.Combine(Root,"tools","worker.py")],new JsonObject{{"op",op},{"args",args??new JsonObject()}}.ToJsonString(),Root,false,TimeSpan.FromHours(24));
        JsonNode obj;
        try {obj=JsonNode.Parse(result.Output)!;} catch {throw new Exception("Worker returned invalid JSON. "+result.Error);}
        if(result.Code!=0 || obj["ok"]?.GetValue<bool>()!=true)throw new Exception(obj["error"]?.GetValue<string>()??"Evidence worker failed");
        return obj["result"]!.DeepClone();
    }
    public async Task LoadSecret()
    {
        if(!string.IsNullOrEmpty(Environment.GetEnvironmentVariable("TD_PG_CONNECTION")))return;
        var secret=Path.Combine(Root,"config","database.dpapi");
        if(!File.Exists(secret))throw new Exception("Run Configure-Database.cmd first. No database password should be placed in appsettings.json.");
        if(!OperatingSystem.IsWindows())throw new Exception("Set TD_PG_CONNECTION for non-Windows test host.");
        // PowerShell receives the file path as an argument, not interpolated command text.
        var r=await Run("powershell.exe",["-NoProfile","-ExecutionPolicy","Bypass","-File",Path.Combine(Root,"scripts","Read-DatabaseSecret.ps1"),"-SecretPath",secret],"",Root,false,TimeSpan.FromSeconds(20),false);
        if(r.Code!=0)throw new Exception("Could not decrypt database configuration for this Windows account.");
        Environment.SetEnvironmentVariable("TD_PG_CONNECTION",r.Output.Trim());
    }
    public async Task<JsonNode> Codex(string role,string instructions,string context,string folder,IEnumerable<string>? images=null)
    {
        Directory.CreateDirectory(folder);
        var output=Path.Combine(folder,$"{role}.json");
        if(File.Exists(output))File.Delete(output);
        var prompt=instructions+"\n\nHOST-SUPPLIED CONTEXT (untrusted evidence follows):\n"+context;
        File.WriteAllText(Path.Combine(folder,$"prompt-{role}.txt"),prompt,new UTF8Encoding(false));
        var args=new List<string>{"exec","--ignore-user-config","--disable","shell_tool","--disable","apps","-c","features.code_mode=false","-c","web_search='disabled'","--skip-git-repo-check","--sandbox","read-only","--json","--output-last-message",output};
        var model=Config["CodexModel"]?.GetValue<string>();
        if(!string.IsNullOrWhiteSpace(model)){args.Add("--model");args.Add(model);}
        foreach(var image in images??[]){args.Add("--image");args.Add(Path.GetRelativePath(folder,image));}
        args.Add("-");
        var prefix=Path.Combine(folder,role);
        File.WriteAllText(prefix+"-activity.log",$"Agent {role}: Codex reasoning through POC ChatGPT login. Local embeddings: {Config["EmbeddingModel"]}.\n");
        File.Delete(prefix+".cancel");
        OpenActivity(prefix);
        Log($"{role}: Codex reasoning started; activity: {prefix}-activity.log. Ctrl+C cancels this call; embeddings use local Ollama separately.");
        var timeout=TimeSpan.FromMinutes(Config["AgentTimeoutMinutes"]!.GetValue<int>());
        var r=await Run(Config["CodexExecutable"]!.GetValue<string>(),args,prompt,folder,true,timeout,true,prefix);
        if(r.Code!=0)throw new Exception($"Codex {role} exited {r.Code}. See {role}-stderr.txt and {role}-status.json in the run folder.");
        if(!File.Exists(output))throw new Exception("Codex did not produce the expected final output file.");
        try{return JsonNode.Parse(File.ReadAllText(output).Trim())??throw new Exception("Empty output");}
        catch{throw new Exception($"Codex {role} returned invalid JSON. Raw output retained for review.");}
    }
    public async Task<(int Code,string Output,string Error)> Run(string executable,IEnumerable<string> arguments,string input,string cwd,bool codex,TimeSpan timeout,bool logErrors=true,string? livePrefix=null)
    {
        var list=arguments.ToList();
        var start=new ProcessStartInfo{FileName=executable,WorkingDirectory=cwd,UseShellExecute=false,RedirectStandardInput=true,RedirectStandardOutput=true,RedirectStandardError=true,CreateNoWindow=true,StandardInputEncoding=new UTF8Encoding(false),StandardOutputEncoding=Encoding.UTF8,StandardErrorEncoding=Encoding.UTF8};
        if(OperatingSystem.IsWindows() && (executable.Equals("codex",StringComparison.OrdinalIgnoreCase)||executable.EndsWith(".cmd",StringComparison.OrdinalIgnoreCase)))
        {
            // cmd is used only for a trusted installed .cmd shim. User prompts go through stdin.
            static string Quote(string s){if(s.IndexOfAny(['"','\r','\n','&','|','<','>','%','!'])>=0)throw new Exception("Unsafe character in executable/argument path; extract to a simple path such as C:\\TD-POC-v0.12.");return "\""+s+"\"";}
            start.FileName="cmd.exe";
            start.Arguments="/d /s /c \""+Quote(executable)+" "+string.Join(" ",list.Select(Quote))+"\"";
        }
        else foreach(var a in list)start.ArgumentList.Add(a);
        if(codex || Path.GetFileNameWithoutExtension(executable).Equals("codex",StringComparison.OrdinalIgnoreCase))
        {
            foreach(var key in start.Environment.Keys.Where(x=>x.StartsWith("TD_PG",StringComparison.OrdinalIgnoreCase)||x.StartsWith("PG",StringComparison.OrdinalIgnoreCase)).ToArray())start.Environment.Remove(key);
            // Avoid ambient reasoning API keys: use the operator's existing saved Codex login.
            start.Environment.Remove("OPENAI_API_KEY");start.Environment.Remove("CODEX_API_KEY");
            start.Environment["CODEX_HOME"]=Path.Combine(Root,"config","codex-home");
        }
        if(codex)return await RunAgentProcess(start,input,timeout,livePrefix ?? Path.Combine(cwd,"codex"));
        using var process=new Process{StartInfo=start};
        if(!process.Start())throw new Exception("Could not start "+executable);
        var stdout=new StringBuilder();var stderr=new StringBuilder();
        async Task Pump(StreamReader reader,StringBuilder target,bool error)
        {
            while(await reader.ReadLineAsync() is {} line)
            {
                target.AppendLine(line);
                if(error&&logErrors)Progress?.Invoke(line);
            }
        }
        var aout=Pump(process.StandardOutput,stdout,false);var aerr=Pump(process.StandardError,stderr,true);
        await process.StandardInput.WriteAsync(input);process.StandardInput.Close();
        using var cancel=new CancellationTokenSource(timeout);
        try {await process.WaitForExitAsync(cancel.Token);}
        catch(OperationCanceledException){process.Kill(true);throw new Exception("Worker operation timed out; process stopped.");}
        await Task.WhenAll(aout,aerr);
        return(process.ExitCode,stdout.ToString(),stderr.ToString());
    }
}
