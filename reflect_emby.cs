using System;
using System.Linq;
using System.Reflection;

var asmPath = @"c:\Users\HDTV\Documents\Preroll Projects\NeXroll-main\emby-libs\MediaBrowser.Controller.dll";
var commonPath = @"c:\Users\HDTV\Documents\Preroll Projects\NeXroll-main\emby-libs\MediaBrowser.Common.dll";
var modelPath = @"c:\Users\HDTV\Documents\Preroll Projects\NeXroll-main\emby-libs\MediaBrowser.Model.dll";

Assembly.LoadFrom(commonPath);
Assembly.LoadFrom(modelPath);
var asm = Assembly.LoadFrom(asmPath);

Type[] types;
try { types = asm.GetTypes(); }
catch (ReflectionTypeLoadException ex) { types = ex.Types.Where(t => t != null).ToArray()!; }

var iface = types.FirstOrDefault(t => t.Name == "IIntroProvider");
if (iface == null) { Console.WriteLine("IIntroProvider NOT FOUND"); return; }

Console.WriteLine("Interface: " + iface.FullName);
foreach (var m in iface.GetMethods())
{
    var parms = string.Join(", ", m.GetParameters().Select(p => p.ParameterType + " " + p.Name));
    Console.WriteLine($"  Method: {m.ReturnType} {m.Name}({parms})");
}
foreach (var p in iface.GetProperties())
{
    Console.WriteLine($"  Property: {p.PropertyType} {p.Name}");
}

var introInfo = types.FirstOrDefault(t => t.Name == "IntroInfo");
if (introInfo != null)
{
    Console.WriteLine("\nIntroInfo: " + introInfo.FullName);
    foreach (var p in introInfo.GetProperties())
    {
        Console.WriteLine($"  Property: {p.PropertyType} {p.Name}");
    }
    foreach (var f in introInfo.GetFields())
    {
        Console.WriteLine($"  Field: {f.FieldType} {f.Name}");        
    }
}

// Also check what interfaces it inherits
Console.WriteLine("\nIIntroProvider interfaces:");
foreach (var i in iface.GetInterfaces())
{
    Console.WriteLine($"  Inherits: {i.FullName}");
}
