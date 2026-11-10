using System.Diagnostics;
using System.Security.Cryptography;
using System.Text.Json.Nodes;
using TD.Poc.Core;
using TD.Poc.Infrastructure;
using TD.Poc.Web;

Runtime.DisableQuickEdit();
try
{
var root=PocPaths.FindRoot();var mode=args.Contains("--poc1")?1:2;
var builder=WebApplication.CreateBuilder(new WebApplicationOptions{Args=args,ContentRootPath=root,WebRootPath=Path.Combine(root,"src","TD.Poc.Web","wwwroot")});
builder.Logging.ClearProviders();builder.Logging.AddConsole();builder.Logging.SetMinimumLevel(LogLevel.Warning);
var port=int.TryParse(Environment.GetEnvironmentVariable("WORKSPACE_PORT"),out var custom)?custom:5250;
if(port is <1024 or >65535)throw new Exception("Choose a port between 1024 and 65535");
builder.WebHost.UseUrls($"http://127.0.0.1:{port}");
builder.WebHost.ConfigureKestrel(k=>k.Limits.MaxRequestBodySize=15*1024*1024);
var app=builder.Build();
var runtime=new Runtime(root);var engine=new WorkspaceEngine(runtime,mode);
var token=Convert.ToHexString(RandomNumberGenerator.GetBytes(32));
app.Use(async(ctx,next)=>{
 var host=ctx.Request.Host;
 if(host.Host is not("127.0.0.1" or "localhost") || host.Port!=port || ctx.Request.Headers["Sec-Fetch-Site"]=="cross-site"){ctx.Response.StatusCode=403;return;}
 ctx.Response.Headers["X-Content-Type-Options"]="nosniff";
 ctx.Response.Headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; frame-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'";
 ctx.Response.Headers["Referrer-Policy"]="no-referrer";
 if(ctx.Request.Path.StartsWithSegments("/api"))ctx.Response.Headers.CacheControl="no-store";
 if(ctx.Request.Method!="GET"&&ctx.Request.Method!="HEAD"){
  if(ctx.Request.Headers["X-Workspace-Token"]!=token){ctx.Response.StatusCode=403;return;}
  if(ctx.Request.Headers.Origin.Count>0&&ctx.Request.Headers.Origin!=$"http://{host}"){ctx.Response.StatusCode=403;return;}
 }
 try{await next();}catch(Exception ex){Console.Error.WriteLine(ex.Message);if(!ctx.Response.HasStarted){ctx.Response.StatusCode=400;await ctx.Response.WriteAsJsonAsync(new{error=engine.PublicError(ex)});}}
});
app.UseDefaultFiles();app.UseStaticFiles();
app.MapGet("/api/init",()=>new {name="Workspace",mode,token,ready=engine.Ready,status=engine.Status});
app.MapGet("/api/videos",async()=>await engine.Data("ui_videos"));
app.MapGet("/api/chats",async()=>await engine.Data("ui_list",new(){{"poc",mode}}));
app.MapPost("/api/chats",async()=>await engine.Data("ui_create",new(){{"poc",mode}}));
app.MapGet("/api/chats/{id:guid}",async(Guid id,long? before)=>await engine.GetChat(id,before));
app.MapPost("/api/chats/{id:guid}/video-source",async(Guid id,HttpRequest request)=>{
 await engine.CheckChat(id);var obj=await request.ReadFromJsonAsync<JsonObject>()??throw new Exception("Select a video");
 return await engine.Data("ui_video_source",new(){{"chat_id",id.ToString()},{"file",obj["file"]?.ToString()??""}});
});
app.MapPost("/api/chats/{id:guid}/images",async(Guid id,HttpRequest request)=>{
 await engine.CheckChat(id);var obj=await request.ReadFromJsonAsync<JsonObject>()??throw new Exception("Missing image");
 var data=obj["base64"]?.ToString()??"";if(data.Length>14*1024*1024)throw new Exception("Image limit is 10 MB");
 return await engine.Data("ui_upload",new(){{"chat_id",id.ToString()},{"name",obj["name"]?.ToString()??"Pasted image"},{"base64",data}});
});
app.MapPost("/api/chats/{id:guid}/messages",async(Guid id,HttpRequest request)=>{
 var obj=await request.ReadFromJsonAsync<JsonObject>()??throw new Exception("Missing message");
 return await engine.Submit(id,obj["text"]?.ToString()??"",obj["attachments"]?.AsArray()??new JsonArray(),obj["recordings"]?.AsArray()??new JsonArray());
});
app.MapGet("/api/job",()=>engine.JobSnapshot());
app.MapPost("/api/stop",()=>{engine.Stop();return new{stopping=true};});
app.MapGet("/api/chats/{chat:guid}/assets/{asset:guid}",async(Guid chat,Guid asset,HttpRequest request)=>{
 await engine.CheckChat(chat);var row=await engine.Data("ui_asset",new(){{"chat_id",chat.ToString()},{"id",asset.ToString()},{"text",request.Query.ContainsKey("preview")}});
 if(request.Query.ContainsKey("preview"))return (IResult)Results.Json(new {label=row["label"]?.ToString(),path=row["metadata"]?["file"]?.ToString()??row["label"]?.ToString(),mime=row["mime"]?.ToString(),text=row["text"]?.ToString(),metadata=row["metadata"]});
 var mime=row["mime"]!.ToString();var inline=mime is "image/png" or "image/jpeg" or "image/webp" or "application/pdf" or "video/mp4";
 return Results.File(row["path"]!.ToString(),inline?mime:"application/octet-stream",inline?null:Path.GetFileName(row["path"]!.ToString()),enableRangeProcessing:true);
});
app.Lifetime.ApplicationStopping.Register(engine.Stop);
await engine.Initialize();
app.Lifetime.ApplicationStarted.Register(()=>{
 var url=$"http://127.0.0.1:{port}";Console.WriteLine($"\nWorkspace ready: {url}\nKeep this CMD window open. Ctrl+C stops the local website.");
 if(OperatingSystem.IsWindows())try{Process.Start(new ProcessStartInfo(url){UseShellExecute=true});}catch{Console.WriteLine("Open the URL above in your browser.");}
});
await app.RunAsync();
}
catch(Exception ex){Console.Error.WriteLine("Workspace could not start: "+ex.Message);Console.Error.WriteLine("Keep the existing database. Run Setup-POC.cmd if dependencies or migrations are missing.");Environment.ExitCode=1;}
public partial class Program{}
