using System.Text.Json.Nodes;
using TD.Poc.Infrastructure;
using TD.Poc.Core;
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
    if(!OperatingSystem.IsWindows())
    {
        r.Config["PythonExecutable"]="/usr/bin/python3";
        var python=Path.Combine(dir,"tools");Directory.CreateDirectory(python);
        var unicode="□ ₹ العربية 中文 café 😀";
        File.WriteAllText(Path.Combine(python,"worker.py"),"import sys,json,os\nassert os.environ.get('PYTHONUTF8')=='1' and os.environ.get('PYTHONIOENCODING')=='utf-8'\nr=json.load(sys.stdin)\nif r['op']=='bad': print('not json');sys.exit(1)\nif r['op']=='packet': print(json.dumps({'ok':True,'result':json.load(open(os.environ['TD_TEST_PACKET'],encoding='utf-8'))},ensure_ascii=False));sys.exit(0)\nprint(json.dumps({'ok':True,'result':{'text':'□ ₹ العربية 中文 café 😀','large':('□ ₹ العربية 中文 '*20000)}},ensure_ascii=False))\n");
        var packet=await r.Worker("unicode",new JsonObject{{"query",unicode}});
        Check(packet["text"]!.ToString()==unicode && packet["large"]!.ToString().Length>100000,"UTF-8 C#/Python worker roundtrip with large non-ASCII packet");
        var actualPacketPath=Environment.GetEnvironmentVariable("TD_TEST_PACKET");
        if(!string.IsNullOrEmpty(actualPacketPath))
        {
            var actualPacket=await r.Worker("packet");
            Check(JsonNode.DeepEquals(actualPacket,JsonNode.Parse(File.ReadAllText(actualPacketPath))),"actual failed-run retrieval packet survives C#/Python process boundary");
        }
        var failedWork=Path.Combine(dir,"bad-worker");
        try{await r.Worker("bad",new JsonObject{{"work",failedWork}});throw new Exception("Expected bad worker failure");}catch(Exception e) when(e.Message.Contains("invalid JSON")){}
        Check(File.Exists(Path.Combine(failedWork,"failure.json")) && Directory.GetFiles(Path.Combine(failedWork,"workers"),"*-stdout.json").Length==1,"worker exception and raw output persisted");
        var roleWork=Path.Combine(dir,"role-work");
        r.BeginRole(roleWork,"A");r.RoleLog("Section 1 of 2");await r.Codex("a","fixture","section",Path.Combine(roleWork,"S1"));r.RoleLog("Section 2 of 2");await r.Codex("index","fixture","index",roleWork);r.EndRole(true,"A saved and embedded (fixture)");
        r.BeginRole(roleWork,"B");await r.Codex("b","fixture","batch",Path.Combine(roleWork,"batch"));r.EndRole(true,"B saved and embedded (fixture)");
        Check(Directory.GetFiles(Path.Combine(roleWork,"activity"),"*.status.json").Length==2,"one aggregate status stream per A/B role");
        var roleLog=File.ReadAllText(Path.Combine(roleWork,"activity","agent-a.log"));
        Check(roleLog.Contains("Section 1 of 2") && roleLog.Contains("Section 2 of 2"),"A sections share one activity stream");
        Check(JsonNode.Parse(File.ReadAllText(Path.Combine(roleWork,"activity","agent-b.status.json")))!["state"]!.ToString()=="COMPLETE","B aggregate completion recorded");
    }
    int generated=0,validated=0;bool receivedFeedback=false;
    await BatchRecovery.Run((attempt,feedback)=>{generated++;receivedFeedback|=feedback is not null;return Task.CompletedTask;},()=>Task.FromResult<JsonNode>(new JsonObject{{"valid",++validated==2},{"errors",new JsonArray("fixture citation mismatch")}}));
    Check(generated==2&&receivedFeedback,"invalid batch repaired with validation feedback");
    generated=0;bool stopped=false;
    try{await BatchRecovery.Run((attempt,feedback)=>{generated++;return Task.CompletedTask;},()=>Task.FromResult<JsonNode>(new JsonObject{{"valid",false}}));}catch(InvalidOperationException){stopped=true;}
    Check(stopped&&generated==3,"persistent invalid batch stops after two corrections");
    generated=0;bool propagated=false;
    try{await BatchRecovery.Run((attempt,feedback)=>{generated++;throw new OperationCanceledException();},()=>Task.FromResult<JsonNode>(new JsonObject{{"valid",true}}));}catch(OperationCanceledException){propagated=true;}
    Check(propagated&&generated==1,"cancellation propagates without retry");
    Console.WriteLine($"Host tests passed: {passed}");
    await KnowledgeTests.Run(PocPaths.FindRoot());
}
finally{Directory.Delete(dir,true);}
