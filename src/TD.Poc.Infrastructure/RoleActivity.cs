using System.Diagnostics;
using System.Text;
using System.Text.Json;
namespace TD.Poc.Infrastructure;
public sealed partial class Runtime
{
    private sealed class RoleSession(string work,string role)
    {
        public string Work=work,Role=role,State="RUNNING",Step="Starting";
        public bool DisplayWarning;
        public string Base=>Path.Combine(Work,"activity","agent-"+Role.ToLowerInvariant());
        public string Cancel=>Base+".cancel";
    }
    private readonly object roleGate=new();
    private RoleSession? currentRole;
    private readonly HashSet<string> connectorNotices=[];
    public string? CurrentActivity{get{lock(roleGate)return currentRole is null?null:$"{currentRole.Role}: {currentRole.Step}"+(currentRole.DisplayWarning?" (activity display could not be updated; processing continues)":"");}}
    private string? RoleCancel {get{lock(roleGate)return currentRole?.Cancel;}}
    public void BeginRole(string work,string role)
    {
        string? viewerError=null;
        lock(roleGate)
        {
            if(currentRole is not null)throw new InvalidOperationException("Previous agent activity phase was not closed");
            var session=new RoleSession(Path.GetFullPath(work),role);
            Directory.CreateDirectory(Path.Combine(work,"activity"));File.Delete(session.Cancel);
            currentRole=session;WriteRoleState(session);
            var startByte=File.Exists(session.Base+".log")?new FileInfo(session.Base+".log").Length:0;
            File.AppendAllText(session.Base+".log",$"Agent {role}: execution status, not private reasoning. Q cancels active work.\n",Encoding.UTF8);
            if(OperatingSystem.IsWindows() && Config["AgentActivityWindows"]?.GetValue<bool>()!=false)
            {
                try
                {
                    var psi=new ProcessStartInfo{FileName="powershell.exe",WorkingDirectory=Root,UseShellExecute=true};
                    foreach(var arg in new[]{"-NoProfile","-ExecutionPolicy","Bypass","-File",Path.Combine(Root,"scripts","Watch-Role.ps1"),"-Prefix",session.Base,"-StartByte",startByte.ToString(System.Globalization.CultureInfo.InvariantCulture)})psi.ArgumentList.Add(arg);
                    Process.Start(psi);
                }
                catch(Exception e){viewerError=e.Message;File.AppendAllText(session.Base+".log","Viewer failed to open: "+e.Message+"\n");}
            }
        }
        Log($"Agent {role} working. Details are in its activity window.");
        if(viewerError is not null)Log("Activity window could not open: "+viewerError+". See activity logs in the run folder.");
    }
    private static void WriteRoleState(RoleSession s)
    {
        var temp=s.Base+".status."+Guid.NewGuid().ToString("N")+".tmp";
        try
        {
            File.WriteAllText(temp,JsonSerializer.Serialize(new{role=s.Role,state=s.State,step=s.Step,updated_at=DateTimeOffset.Now}));
            File.Move(temp,s.Base+".status.json",true);
        }
        catch(Exception error) when(error is IOException or UnauthorizedAccessException)
        {
            // The activity viewer is optional. Its status file must never abort ingestion.
            s.DisplayWarning=true;
        }
        finally{try{File.Delete(temp);}catch(IOException){}catch(UnauthorizedAccessException){}}
    }
    private void PersistRoleLine(RoleSession session,string text)
    {
        {
            try{File.AppendAllText(session.Base+".log",$"[{DateTimeOffset.Now:HH:mm:ss}] {text}\n",Encoding.UTF8);}
            catch(Exception error) when(error is IOException or UnauthorizedAccessException){session.DisplayWarning=true;}
            WriteRoleState(session);
        }
    }
    public void RoleLog(string text)
    {
        RoleSession? session;
        lock(roleGate){session=currentRole;if(session is not null)session.Step=text;}
        consoleActivity.Writer.TryWrite(()=>
        {
            if(session is not null){PersistRoleLine(session,text);return;}
            try{File.AppendAllText(Path.Combine(Root,"runtime","workflow.log"),$"[{DateTimeOffset.Now:HH:mm:ss}] {text}\n");}
            catch(Exception error) when(error is IOException or UnauthorizedAccessException){}
        });
    }
    public async Task FlushActivityForTests()
    {
        var done=new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        consoleActivity.Writer.TryWrite(()=>done.TrySetResult());
        await done.Task.WaitAsync(TimeSpan.FromSeconds(5));
    }
    private void ConnectorNotice()
    {
        string key;lock(roleGate)key=currentRole?.Base??"startup";
        lock(connectorNotices)if(!connectorNotices.Add(key))return;
        RoleLog("Optional MCP startup warning received. Complete stderr is retained separately; agent failure is determined by exit/validation, not this warning alone.");
    }
    public void EndRole(bool success,string message)
    {
        string? role=null;
        lock(roleGate)
        {
            if(currentRole is null)return;
            role=currentRole.Role;currentRole.State=success?"COMPLETE":"FAILED";currentRole.Step=message;
            var completed=currentRole;currentRole=null;
            terminalActivity.Enqueue(()=>PersistRoleLine(completed,message));
            consoleActivity.Writer.TryWrite(()=>{});
        }
        Log($"Agent {role} {(success?"completed":"stopped")}: {message}");
    }
    public void RecordFailure(string work,string stage,Exception error)
    {
        Directory.CreateDirectory(work);
        string Redact(string text)
        {
            var secret=Environment.GetEnvironmentVariable("TD_PG_CONNECTION");
            return string.IsNullOrEmpty(secret)?text:text.Replace(secret,"[database connection redacted]");
        }
        var payload=JsonSerializer.Serialize(new{stage,error=Redact(error.Message),details=Redact(error.ToString()),at=DateTimeOffset.Now});
        Directory.CreateDirectory(Path.Combine(work,"failures"));
        File.WriteAllText(Path.Combine(work,"failures",DateTimeOffset.UtcNow.ToString("yyyyMMddHHmmssfff")+"-"+Guid.NewGuid().ToString("N")+".json"),payload);
        File.WriteAllText(Path.Combine(work,"failure.json"),payload);
        File.AppendAllText(Path.Combine(Root,"runtime","workflow.log"),$"[{DateTimeOffset.Now:HH:mm:ss}] FAILED at {stage}; see {Path.Combine(work,"failure.json")}\n");
    }
}
