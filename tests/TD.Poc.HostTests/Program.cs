using System.Text.Json.Nodes;
using TD.Poc.Infrastructure;
var dir=Path.Combine(Path.GetTempPath(),"td-host-test-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(Path.Combine(dir,"config"));
try
{
    File.WriteAllText(Path.Combine(dir,"config","appsettings.json"),"{\"PythonExecutable\":\"python3\",\"CodexExecutable\":\"codex\",\"AgentTimeoutMinutes\":1}");
    var r=new Runtime(dir);int passed=0;
    void Check(bool condition,string name){if(!condition)throw new Exception("FAIL "+name);Console.WriteLine("PASS "+name);passed++;}
    var version=await r.Run("dotnet",["--version"],"",dir,false,TimeSpan.FromSeconds(30));Check(version.Code==0,"safe process invocation");
    if(!OperatingSystem.IsWindows())
    {
        var fake=Path.Combine(dir,"codex");
        File.WriteAllText(fake,"#!/usr/bin/env python3\nimport sys,json,os\na=sys.argv[1:];out=a[a.index('--output-last-message')+1];prompt=sys.stdin.read();json.dump({'reply':'fixture only','action':'NONE','argument':''},open(out,'w'));json.dump({'args':a,'prompt':prompt,'secret_present':'TD_PG_CONNECTION' in os.environ},open(out+'.capture','w'))\nprint('{\"type\":\"turn.completed\"}')\n");
        File.SetUnixFileMode(fake,UnixFileMode.UserRead|UnixFileMode.UserWrite|UnixFileMode.UserExecute);
        r.Config["CodexExecutable"]=fake;Environment.SetEnvironmentVariable("TD_PG_CONNECTION","NEVER-SEND-THIS");
        var folder=Path.Combine(dir,"agent");var text="User text ; $(touch SHOULD-NOT-EXIST) & echo injection";
        var answer=await r.Codex("test","Instructions",text,folder);
        var capture=JsonNode.Parse(File.ReadAllText(Path.Combine(folder,"test.json.capture")))!;
        Check(!capture["secret_present"]!.GetValue<bool>(),"database secret removed from Codex environment");
        Check(capture["prompt"]!.GetValue<string>().Contains(text),"user text travels through stdin without shell interpolation");
        Check(capture["args"]!.AsArray().Any(x=>x!.GetValue<string>()=="shell_tool"),"shell tools explicitly disabled");
        Check(capture["args"]!.AsArray().Any(x=>x!.GetValue<string>()=="--ignore-user-config"),"ambient Codex configuration omitted");
        Check(answer["action"]!.GetValue<string>()=="NONE","Codex final JSON consumed");
    }
    Console.WriteLine($"Host tests passed: {passed}");
}
finally{Directory.Delete(dir,true);}
