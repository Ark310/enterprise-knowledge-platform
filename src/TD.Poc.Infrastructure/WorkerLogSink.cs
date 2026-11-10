using System.Text;
using System.Threading.Channels;
namespace TD.Poc.Infrastructure;
// Best-effort importer telemetry. Child pipes and database commits never wait for this disk writer.
internal sealed class WorkerLogSink:IDisposable
{
    private readonly Channel<(bool Error,string Text)> pending=Channel.CreateBounded<(bool,string)>(new BoundedChannelOptions(256){SingleReader=true,FullMode=BoundedChannelFullMode.Wait});
    private readonly ManualResetEventSlim finished=new(false);
    private readonly Action<string> warning;
    private int warned;
    public WorkerLogSink(string prefix,Action<string> warning)
    {
        this.warning=warning;
        var thread=new Thread(()=>
        {
            try
            {
                using var output=new StreamWriter(prefix+"-stdout.json",false,new UTF8Encoding(false)){AutoFlush=true};
                using var error=new StreamWriter(prefix+"-stderr.txt",false,new UTF8Encoding(false)){AutoFlush=true};
                while(pending.Reader.WaitToReadAsync().AsTask().GetAwaiter().GetResult())
                    while(pending.Reader.TryRead(out var item))(item.Error?error:output).WriteLine(item.Text);
            }
            catch(Exception error) when(error is IOException or UnauthorizedAccessException){Warn();}
            finally{finished.Set();}
        }){IsBackground=true,Name="Import telemetry writer"};
        thread.Start();
    }
    private void Warn(){if(Interlocked.Exchange(ref warned,1)==0)warning("Import progress log unavailable or incomplete; processing and timeout checks continue. Final results come from the importer and database.");}
    public void Write(bool error,string text){if(finished.IsSet || !pending.Writer.TryWrite((error,text)))Warn();}
    public void Dispose(){pending.Writer.TryComplete();if(!finished.Wait(TimeSpan.FromMilliseconds(250)))Warn();}
}
