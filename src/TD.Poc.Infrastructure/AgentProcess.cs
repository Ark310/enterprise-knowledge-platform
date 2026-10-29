using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace TD.Poc.Infrastructure;

public sealed partial class Runtime
{
    // Classic Windows consoles pause writes when QuickEdit selection is active.
    // Disable only QuickEdit for this process; do not change system console defaults.
    [DllImport("kernel32.dll")] private static extern IntPtr GetStdHandle(int handle);
    [DllImport("kernel32.dll")] private static extern bool GetConsoleMode(IntPtr handle,out uint mode);
    [DllImport("kernel32.dll")] private static extern bool SetConsoleMode(IntPtr handle,uint mode);
    public static void DisableQuickEdit()
    {
        if(!OperatingSystem.IsWindows())return;
        var handle=GetStdHandle(-10);
        if(GetConsoleMode(handle,out var mode))SetConsoleMode(handle,(mode|0x80u)&~0x40u);
    }
    private async Task<(int Code,string Output,string Error)> RunAgentProcess(ProcessStartInfo start,string input,TimeSpan timeout,string prefix)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(prefix)!);
        // Flush every line so a partial export remains useful during a blocked console or crash.
        using var events=new StreamWriter(prefix+"-events.jsonl",false,new UTF8Encoding(false)){AutoFlush=true};
        using var errors=new StreamWriter(prefix+"-stderr.txt",false,new UTF8Encoding(false)){AutoFlush=true};
        using var activity=new StreamWriter(prefix+"-activity.log",true,new UTF8Encoding(false)){AutoFlush=true};
        var gate=new object();var stdout=new StringBuilder();var stderr=new StringBuilder();
        var clock=Stopwatch.StartNew();var lastEvent="starting";double lastEventAt=0;
        using var deadline=new CancellationTokenSource(timeout);
        using var manual=new CancellationTokenSource();
        using var linked=CancellationTokenSource.CreateLinkedTokenSource(deadline.Token,manual.Token);
        using var monitoring=new CancellationTokenSource();
        using var process=new Process{StartInfo=start};
        void Note(string message){lock(gate)activity.WriteLine($"[{DateTimeOffset.Now:HH:mm:ss}] {message}");}
        void State(string state,int? code=null)
        {
            lock(gate)
            {
                var data=JsonSerializer.Serialize(new{state,pid=process.Id,elapsed_seconds=Math.Round(clock.Elapsed.TotalSeconds,1),last_event=lastEvent,last_event_seconds=lastEventAt,exit_code=code,updated_at=DateTimeOffset.Now});
                File.WriteAllText(prefix+"-status.json.tmp",data);
                File.Move(prefix+"-status.json.tmp",prefix+"-status.json",true);
            }
        }
        ConsoleCancelEventHandler handler=(_,e)=>{e.Cancel=true;manual.Cancel();};
        try {if(!process.Start())throw new Exception("Could not start Codex");}
        catch(Exception e)
        {
            File.WriteAllText(prefix+"-status.json",JsonSerializer.Serialize(new{state="FAILED",error=e.Message,elapsed_seconds=clock.Elapsed.TotalSeconds}));
            Note("FAILED to launch: "+e.Message);throw;
        }
        Console.CancelKeyPress+=handler;
        State("RUNNING");Note($"Process {process.Id} started. Timeout {timeout.TotalMinutes:g} minutes. Press Ctrl+C in the main console to cancel.");
        bool connectorWarningShown=false;
        async Task Pump(StreamReader reader,bool error)
        {
            while(await reader.ReadLineAsync() is {} line)
            {
                if(error)
                {
                    stderr.AppendLine(line);errors.WriteLine(line);Note("stderr: "+line);
                    if(!connectorWarningShown && line.Contains("rmcp",StringComparison.OrdinalIgnoreCase))
                    {connectorWarningShown=true;ConnectorNotice();}
                    continue;
                }
                stdout.AppendLine(line);events.WriteLine(line);
                try
                {
                    var obj=JsonNode.Parse(line);var type=obj?["type"]?.GetValue<string>()??"unknown";
                    lock(gate){lastEvent=type;lastEventAt=clock.Elapsed.TotalSeconds;}
                    // Show status and event names, not private reasoning content.
                    Note("Codex event: "+type);
                    if(type is "turn.started" or "turn.completed" or "turn.failed" or "error")PublishActivity(Path.GetFileName(prefix)+": "+type);
                }
                catch{Note("Received non-JSON output; retained in events file.");}
            }
        }
        var outputPump=Pump(process.StandardOutput,false);var errorPump=Pump(process.StandardError,true);
        var heartbeat=Task.Run(async()=>
        {
            try
            {
                while(!monitoring.IsCancellationRequested)
                {
                    await Task.Delay(TimeSpan.FromSeconds(1),monitoring.Token);
                    if(File.Exists(prefix+".cancel") || (RoleCancel is {} roleCancel && File.Exists(roleCancel)))manual.Cancel();
                    if((int)clock.Elapsed.TotalSeconds%10==0)
                    {
                        State("RUNNING");
                        Note($"Waiting for Codex: {clock.Elapsed:mm\\:ss} elapsed; last event {lastEvent}. A heartbeat confirms the host is alive, not model progress.");
                        PublishActivity($"{Path.GetFileName(prefix)}: {clock.Elapsed:mm\\:ss} elapsed; last event {lastEvent}. Host alive; model progress unconfirmed.");
                    }
                }
            }
            catch(OperationCanceledException){ }
        });
        try
        {
            await process.StandardInput.WriteAsync(input.AsMemory(),linked.Token);
            process.StandardInput.Close();
            await process.WaitForExitAsync(linked.Token);
            // A descendant can keep pipes open after the direct child exits. Never wait indefinitely.
            try {await Task.WhenAll(outputPump,errorPump).WaitAsync(TimeSpan.FromSeconds(5));}
            catch(TimeoutException){throw new IOException("Codex exited but its output pipes did not close. Partial logs retained.");}
            monitoring.Cancel();await heartbeat;
            State(process.ExitCode==0?"COMPLETED":"FAILED",process.ExitCode);
            Note($"Codex process exited {process.ExitCode}; elapsed {clock.Elapsed:mm\\:ss}. Host validation follows separately.");
            PublishActivity($"{Path.GetFileName(prefix)} exited {process.ExitCode} after {clock.Elapsed:mm\\:ss}; validation follows separately.");
            return(process.ExitCode,stdout.ToString(),stderr.ToString());
        }
        catch(Exception e)
        {
            if(!process.HasExited)process.Kill(true);
            try {await Task.WhenAll(outputPump,errorPump).WaitAsync(TimeSpan.FromSeconds(5));}catch{ }
            monitoring.Cancel();await heartbeat;
            var state=manual.IsCancellationRequested?"CANCELLED":deadline.IsCancellationRequested?"TIMED_OUT":"FAILED";
            State(state);Note(state+": "+e.Message+". Partial logs retained; no successful handoff is claimed.");
            throw new Exception($"Agent {state}. See {prefix}-status.json and live logs.",e);
        }
        finally
        {
            monitoring.Cancel();await heartbeat;Console.CancelKeyPress-=handler;
        }
    }
}
