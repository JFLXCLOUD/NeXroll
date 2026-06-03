<#
.SYNOPSIS
    Package the NeXroll Intros Jellyfin plugin into a distributable zip.

.DESCRIPTION
    Produces NeXroll.Jellyfin-<version>.zip containing exactly the files Jellyfin
    needs at the zip root:
        - NeXroll.Jellyfin.dll   (the plugin)
        - meta.json              (name, version, guid, imagePath -> dashboard icon)
        - thumb.png              (the dashboard icon)

    Server/SDK assemblies (MediaBrowser.*, Jellyfin.*, Microsoft.Extensions.*,
    System.Net.Http.Json, etc.) are intentionally EXCLUDED: Jellyfin already
    provides them, and shipping copies causes assembly-load conflicts on startup.

    The version is read from meta.json so it stays in lockstep with the plugin.

.PARAMETER NoPublish
    Skip 'dotnet publish' and package from the existing publish/ folder. Used by
    build.bat, which has already published. Run without this switch to do a full
    publish + package in one step.
#>
[CmdletBinding()]
param(
    [string]$Configuration = 'Release',
    [switch]$NoPublish
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$pub  = Join-Path $root 'publish'

if (-not $NoPublish) {
    Write-Host 'Publishing...' -ForegroundColor Cyan
    dotnet publish (Join-Path $root 'NeXroll.Jellyfin.csproj') -c $Configuration -o $pub | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'dotnet publish failed' }
}

# Exactly the files a Jellyfin plugin should ship.
$files = @('NeXroll.Jellyfin.dll', 'meta.json', 'thumb.png')
foreach ($f in $files) {
    if (-not (Test-Path (Join-Path $pub $f))) {
        throw "Missing expected file in publish output: $f (run a build/publish first)"
    }
}

$meta = Get-Content (Join-Path $pub 'meta.json') -Raw | ConvertFrom-Json
$ver  = $meta.version
if (-not $ver) { throw 'Could not read "version" from meta.json' }

$zip = Join-Path $root "NeXroll.Jellyfin-$ver.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }

Compress-Archive -Path ($files | ForEach-Object { Join-Path $pub $_ }) -DestinationPath $zip -Force

$size = [math]::Round((Get-Item $zip).Length / 1KB, 1)
Write-Host "Packaged: $zip ($size KB)" -ForegroundColor Green
Write-Host "Contents: $($files -join ', ')"
