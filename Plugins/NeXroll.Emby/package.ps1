<#
.SYNOPSIS
    Package the NeXroll Intros Emby plugin into a distributable zip.

.DESCRIPTION
    Emby plugins ship as a single assembly. The dashboard icon is embedded in the
    DLL (via IHasThumbImage), and Emby reads the version from the assembly, so the
    package is just NeXroll.Emby.dll. The Emby server assemblies (MediaBrowser.*)
    are referenced with <Private>false> and never copied to output, so they are
    not shipped.

    Produces NeXroll.Emby-<version>.zip with the version read from the built
    assembly (AssemblyInfo.cs).

.PARAMETER NoBuild
    Skip 'dotnet build' and package the existing Release output (used by build.bat,
    which has already built). Run without this switch to build + package in one step.
#>
[CmdletBinding()]
param(
    [string]$Configuration = 'Release',
    [switch]$NoBuild
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$dll  = Join-Path $root "bin\$Configuration\net8.0\NeXroll.Emby.dll"

if (-not $NoBuild) {
    Write-Host 'Building...' -ForegroundColor Cyan
    dotnet build (Join-Path $root 'NeXroll.Emby.csproj') -c $Configuration | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'dotnet build failed' }
}

if (-not (Test-Path $dll)) { throw "Plugin DLL not found: $dll (build first)" }

$ver = [System.Reflection.AssemblyName]::GetAssemblyName($dll).Version.ToString()

$zip = Join-Path $root "NeXroll.Emby-$ver.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path $dll -DestinationPath $zip -Force

$size = [math]::Round((Get-Item $zip).Length / 1KB, 1)
Write-Host "Packaged: $zip ($size KB)" -ForegroundColor Green
Write-Host "Contents: NeXroll.Emby.dll (icon embedded, v$ver)"
