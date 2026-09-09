<# Package only the Jellyfin 12 plugin, metadata, and thumbnail. #>
[CmdletBinding()]
param(
    [string]$Configuration = 'Release',
    [string]$Dotnet = 'dotnet'
)
$ErrorActionPreference = 'Stop'
$publishDir = Join-Path $PSScriptRoot 'publish'
& $Dotnet publish (Join-Path $PSScriptRoot 'NeXroll.Jellyfin12.csproj') -c $Configuration -o $publishDir
if ($LASTEXITCODE -ne 0) { throw 'Jellyfin 12 plugin publish failed' }

$files = @('NeXroll.Jellyfin.dll', 'meta.json', 'thumb.png')
foreach ($name in $files) {
    if (-not (Test-Path -LiteralPath (Join-Path $publishDir $name))) {
        throw "Missing package file: $name"
    }
}
$meta = Get-Content -LiteralPath (Join-Path $publishDir 'meta.json') -Raw | ConvertFrom-Json
$assembly = [System.Reflection.AssemblyName]::GetAssemblyName((Join-Path $publishDir 'NeXroll.Jellyfin.dll'))
if ($assembly.Version.ToString() -ne $meta.version -or $meta.targetAbi -ne '12.0.0.0' -or $meta.framework -ne 'net10.0') {
    throw 'Jellyfin 12 package metadata does not match the compiled plugin'
}
$zip = Join-Path $PSScriptRoot "NeXroll.Jellyfin12-$($meta.version).zip"
Compress-Archive -LiteralPath ($files | ForEach-Object { Join-Path $publishDir $_ }) -DestinationPath $zip -Force
Get-FileHash -LiteralPath $zip -Algorithm SHA256
Write-Output "Packaged: $zip"
