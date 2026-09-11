# Re-export the cleaned raster master using Windows System.Drawing.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$repoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$destination = Join-Path $repoRoot 'NeXroll/frontend/public/icons'
New-Item -ItemType Directory -Force $destination | Out-Null
$master = [System.Drawing.Bitmap]::new((Join-Path $repoRoot 'assets/icons/nexroll-master.png'))

function Export-Icon([int]$Size, [string]$Name, [bool]$White = $false, [bool]$Opaque = $false, [double]$Scale = 1) {
    $bitmap = [System.Drawing.Bitmap]::new($Size, $Size)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.Clear($(if ($Opaque) { [System.Drawing.Color]::White } else { [System.Drawing.Color]::Transparent }))
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $attributes = [System.Drawing.Imaging.ImageAttributes]::new()
    if ($White) {
        $matrix = [System.Drawing.Imaging.ColorMatrix]::new()
        $matrix.Matrix00 = 0; $matrix.Matrix11 = 0; $matrix.Matrix22 = 0
        $matrix.Matrix40 = 1; $matrix.Matrix41 = 1; $matrix.Matrix42 = 1
        $attributes.SetColorMatrix($matrix)
    }
    $edge = [int][Math]::Round($Size * $Scale)
    $offset = [int][Math]::Floor(($Size - $edge) / 2)
    $rect = [System.Drawing.Rectangle]::new($offset, $offset, $edge, $edge)
    $graphics.DrawImage($master, $rect, 0, 0, $master.Width, $master.Height, [System.Drawing.GraphicsUnit]::Pixel, $attributes)
    $bitmap.Save((Join-Path $destination $Name), [System.Drawing.Imaging.ImageFormat]::Png)
    $attributes.Dispose(); $graphics.Dispose(); $bitmap.Dispose()
}

try {
    foreach ($size in @(16, 24, 32, 48, 64, 128, 192, 256, 512, 1024)) {
        Export-Icon $size "nexroll-black-$size.png"
        Export-Icon $size "nexroll-white-$size.png" $true
        Export-Icon $size "nexroll-$size.png" $false $true
    }
    # Scaling the entire master to 55% keeps even its corners inside the
    # maskable safe-zone circle (40% radius), regardless of master padding.
    foreach ($size in @(192, 512)) {
        Export-Icon $size "nexroll-maskable-$size.png" $false $true 0.55
    }
    Export-Icon 180 'apple-touch-icon.png' $false $true

    # ICO directory with PNG-compressed frames, supported by modern Windows.
    $sizes = @(16, 24, 32, 48, 64, 128, 256)
    $frames = @($sizes | ForEach-Object { ,([System.IO.File]::ReadAllBytes((Join-Path $destination "nexroll-$_.png"))) })
    $stream = [System.IO.File]::Create((Join-Path $destination 'nexroll.ico'))
    $writer = [System.IO.BinaryWriter]::new($stream)
    try {
        $writer.Write([uint16]0); $writer.Write([uint16]1); $writer.Write([uint16]$sizes.Count)
        $offset = 6 + 16 * $sizes.Count
        for ($i = 0; $i -lt $sizes.Count; $i++) {
            $dimension = if ($sizes[$i] -eq 256) { 0 } else { $sizes[$i] }
            $writer.Write([byte]$dimension); $writer.Write([byte]$dimension)
            $writer.Write([byte]0); $writer.Write([byte]0)
            $writer.Write([uint16]1); $writer.Write([uint16]32)
            $writer.Write([uint32]$frames[$i].Length); $writer.Write([uint32]$offset)
            $offset += $frames[$i].Length
        }
        foreach ($frame in $frames) { $writer.Write([byte[]]$frame) }
    } finally { $writer.Dispose(); $stream.Dispose() }
} finally { $master.Dispose() }
Copy-Item -LiteralPath (Join-Path $destination 'nexroll.ico') -Destination (Join-Path (Split-Path $destination -Parent) 'favicon.ico') -Force
foreach ($color in @('black', 'white')) {
    Copy-Item -LiteralPath (Join-Path $repoRoot "assets/nexroll-logo-$color.png") -Destination (Join-Path $destination "nexroll-logo-$color.png") -Force
}
Compress-Archive -Path (Join-Path $destination '*') -DestinationPath (Join-Path $repoRoot 'assets/icons/nexroll-app-icons.zip') -Force
Write-Output "Exported app icons to $destination"
