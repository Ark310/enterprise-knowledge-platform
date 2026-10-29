using System.Text.Json.Nodes;
using TD.Poc.Infrastructure;
var dir=Path.Combine(Path.GetTempPath(),"td-host-test-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(Path.Combine(dir,"config"));
try
{
    File.WriteAllText(Path.Combine(dir,"config","appsettings.json"),"{\"PythonExecutable\":\"python3\",\"CodexExecutable\":\"codex\",\"AgentTimeoutMinutes\":1}");
    var r=new Runtime(dir);int passed=0;var activity=new System.Collections.Concurrent.ConcurrentQueue<string>();r.Progress+=activity.Enqueue;
    void Check(bool condition,string name){if(!condition)throw new Exception("FAIL "+name);Console.WriteLine("PASS "+name);passed++;}
    var version=await r.Run("dotnet",["--version"],"",dir,false,TimeSpan.FromSeconds(30));Check(version.Code==0,"safe process invocation");
    if(!OperatingSystem.IsWindows())
    {
        var fake=Path.Combine(dir,"codex");
        File.WriteAllText(fake,"#!/usr/bin/env python3\nimport sys,json,os\na=sys.argv[1:];out=a[a.index('--output-last-message')+1];prompt=sys.stdin.read();json.dump({'reply':'fixture only','action':'NONE','argument':''},open(out,'w'));json.dump({'args':a,'prompt':prompt,'secret_present':'TD_PG_CONNECTION' in os.environ,'codex_home':os.environ.get('CODEX_HOME')},open(out+'.capture','w'))\nprint('{\"type\":\"turn.completed\"}')\n");
        File.SetUnixFileMode(fake,UnixFileMode.UserRead|UnixFileMode.UserWrite|UnixFileMode.UserExecute);
        r.Config["CodexExecutable"]=fake;Environment.SetEnvironmentVariable("TD_PG_CONNECTION","NEVER-SEND-THIS");
        var folder=Path.Combine(dir,"agent");var text="User text ; $(touch SHOULD-NOT-EXIST) & echo injection";
        var answer=await r.Codex("test","Instructions",text,folder);
        var capture=JsonNode.Parse(File.ReadAllText(Path.Combine(folder,"test.json.capture")))!;
        Check(!capture["secret_present"]!.GetValue<bool>(),"database secret removed from Codex environment");
        Check(capture["prompt"]!.GetValue<string>().Contains(text),"user text travels through stdin without shell interpolation");
        Check(capture["args"]!.AsArray().Any(x=>x!.GetValue<string>()=="shell_tool"),"shell tools explicitly disabled");
        Check(capture["args"]!.AsArray().Any(x=>x!.GetValue<string>()=="--ignore-user-config"),"ambient Codex configuration omitted");
        Check(capture["codex_home"]!.GetValue<string>()==Path.Combine(dir,"config","codex-home"),"isolated Codex home used");
        Check(File.Exists(Path.Combine(folder,"test-events.jsonl")),"event file written");
        Check(JsonNode.Parse(File.ReadAllText(Path.Combine(folder,"test-status.json")))!["state"]!.GetValue<string>()=="COMPLETED","completion recorded");
        Check(SpinWait.SpinUntil(()=>activity.Any(x=>x.Contains("turn.completed")),2000),"agent progress reaches the main-console subscription");
        Check(answer["action"]!.GetValue<string>()=="NONE","Codex final JSON consumed");
    }
    if(!OperatingSystem.IsWindows())
    {
        var slow=Path.Combine(dir,"slow-codex");
        File.WriteAllText(slow,"#!/usr/bin/env python3\nimport time,sys\nprint('{\"type\":\"turn.started\"}',flush=True)\nprint('fixture stderr',file=sys.stderr,flush=True)\ntime.sleep(30)\n");
        File.SetUnixFileMode(slow,UnixFileMode.UserRead|UnixFileMode.UserWrite|UnixFileMode.UserExecute);
        var prefix=Path.Combine(dir,"cancelled");
        var task=r.Run(slow,[],"",dir,true,TimeSpan.FromSeconds(15),true,prefix);
        for(var i=0;i<100 && (!File.Exists(prefix+"-events.jsonl") || new FileInfo(prefix+"-events.jsonl").Length==0);i++)await Task.Delay(50);
        Check(File.ReadAllText(prefix+"-events.jsonl").Contains("turn.started"),"events available before process exits");
        Check(File.ReadAllText(prefix+"-stderr.txt").Contains("fixture stderr"),"stderr available before process exits");
        File.WriteAllText(prefix+".cancel","cancel");
        try{await task;throw new Exception("Expected cancellation");}catch(Exception e) when(e.Message.Contains("CANCELLED")){passed++;Console.WriteLine("PASS cancel file stops call");}
        Check(JsonNode.Parse(File.ReadAllText(prefix+"-status.json"))!["state"]!.GetValue<string>()=="CANCELLED","cancel state retained");
        var timed=Path.Combine(dir,"timed");
        try{await r.Run(slow,[],"",dir,true,TimeSpan.FromMilliseconds(300),true,timed);throw new Exception("Expected timeout");}catch(Exception e) when(e.Message.Contains("TIMED_OUT")){passed++;Console.WriteLine("PASS timeout stops call and keeps logs");}
        Check(File.ReadAllText(timed+"-events.jsonl").Contains("turn.started"),"partial events survive timeout");
        var failed=Path.Combine(dir,"failed");
        var failure=await r.Run("python3",["-c","import sys; print('fixture failure',file=sys.stderr);sys.exit(7)"],"",dir,true,TimeSpan.FromSeconds(10),true,failed);
        Check(failure.Code==7 && JsonNode.Parse(File.ReadAllText(failed+"-status.json"))!["state"]!.GetValue<string>()=="FAILED","nonzero exit status and stderr retained");
    }
    Console.WriteLine($"Host tests passed: {passed}");
}
finally{Directory.Delete(dir,true);}
