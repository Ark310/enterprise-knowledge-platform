using System.Diagnostics;
using TD.Poc.Core;
using TD.Poc.Infrastructure;
Runtime.DisableQuickEdit();
Console.OutputEncoding=System.Text.Encoding.UTF8;
if(args.Contains("--version")){Console.WriteLine("Workspace launcher 0.24.0");return;}
try
{
    var root=PocPaths.FindRoot();
    while(true)
    {
        Console.WriteLine("\nWorkspace 0.24\n1. Documentation Gap Analysis\n2. Knowledge Retrieval and Verification\n0. Exit");
        Console.Write("Choose 1 or 2: ");var choice=Console.ReadLine();if(choice is null || choice.Trim()=="0")break;
        var selected=PocPaths.ProjectForChoice(choice);
        var project=args.Contains("--cli")?selected:"TD.Poc.Web";
        if(selected is null){Console.WriteLine("Enter 1, 2 or 0.");continue;}
#if DEBUG
        const string configuration="Debug";
#else
        const string configuration="Release";
#endif
        var dll=Path.Combine(root,"src",project!,"bin",configuration,"net10.0",project+".dll");
        if(!File.Exists(dll)){Console.WriteLine("Program has not been built. Run Setup-POC.cmd first. Expected: "+dll);continue;}
        var psi=new ProcessStartInfo("dotnet"){WorkingDirectory=root,UseShellExecute=false};psi.ArgumentList.Add(dll);if(!args.Contains("--cli"))psi.ArgumentList.Add(choice!.Trim()=="1"?"--poc1":"--poc2");psi.Environment["TD_POC_ROOT"]=root;
        using var process=Process.Start(psi)??throw new Exception("Could not launch the selected POC.");
        // Child owns this same console. Do not intercept Ctrl+C: its worker cancellation must receive it.
        ConsoleCancelEventHandler keepLauncher=(_,e)=>e.Cancel=true;Console.CancelKeyPress+=keepLauncher;
        try{await process.WaitForExitAsync();}finally{Console.CancelKeyPress-=keepLauncher;}
        if(process.ExitCode!=0)Console.WriteLine("Selected POC stopped with an error. Review its message and runtime logs.");
    }
}
catch(Exception e){Console.Error.WriteLine(e.Message);Environment.ExitCode=1;}
