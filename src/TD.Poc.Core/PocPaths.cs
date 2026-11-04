namespace TD.Poc.Core;
public static class PocPaths
{
    public static string FindRoot()
    {
        var explicitRoot=Environment.GetEnvironmentVariable("TD_POC_ROOT");
        if(!string.IsNullOrEmpty(explicitRoot))return Path.GetFullPath(explicitRoot);
        foreach(var start in new[]{Environment.CurrentDirectory,AppContext.BaseDirectory})
            for(var p=new DirectoryInfo(start);p is not null;p=p.Parent)
                if(File.Exists(Path.Combine(p.FullName,"config","appsettings.json")))return p.FullName;
        throw new Exception("Cannot find solution root. Run Start-POC.cmd or set TD_POC_ROOT.");
    }
    public static string? ProjectForChoice(string? choice)=>choice?.Trim() switch
    {
        "1"=>"TD.Poc.Console", "2"=>"TD.Poc.Retrieval.Console", _=>null
    };
}
