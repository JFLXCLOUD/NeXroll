[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Drawing

function Find-NeXrollRepoRoot {
    param([Parameter(Mandatory = $true)][string]$StartPath)

    $cursor = [System.IO.DirectoryInfo]::new(
        [System.IO.Path]::GetFullPath($StartPath)
    )

    while ($null -ne $cursor) {
        $candidate = Join-Path $cursor.FullName 'NeXroll/frontend/public/NeXroll_Logo_WHT.png'
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return $cursor.FullName
        }
        $cursor = $cursor.Parent
    }

    throw "Could not find the NeXroll repository root from '$StartPath'."
}

function Set-QualityRendering {
    param([Parameter(Mandatory = $true)]$Graphics)

    $Graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceOver
    $Graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
    $Graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $Graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $Graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
}

function Save-RgbPng {
    param(
        [Parameter(Mandatory = $true)]$Bitmap,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $Bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
}

function Write-CommunityIcon {
    param(
        [Parameter(Mandatory = $true)]$Source,
        [Parameter(Mandatory = $true)][System.Drawing.Rectangle]$MarkSource,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $bitmap = [System.Drawing.Bitmap]::new(
        300,
        300,
        [System.Drawing.Imaging.PixelFormat]::Format24bppRgb
    )
    $bitmap.SetResolution([single]96, [single]96)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $cyanBrush = [System.Drawing.SolidBrush]::new($script:Cyan)
    $blueBrush = [System.Drawing.SolidBrush]::new($script:Blue)
    $violetBrush = [System.Drawing.SolidBrush]::new($script:Violet)
    $amberBrush = [System.Drawing.SolidBrush]::new($script:Amber)
    $railBrush = [System.Drawing.SolidBrush]::new($script:Rail)

    try {
        Set-QualityRendering -Graphics $graphics
        $graphics.Clear($script:Charcoal)

        # A 210 px mark stays inside Reddit's circular crop and the 216 px brief.
        $markDestination = [System.Drawing.Rectangle]::new(45, 45, 210, 210)
        $graphics.DrawImage(
            $Source,
            $markDestination,
            $MarkSource,
            [System.Drawing.GraphicsUnit]::Pixel
        )

        # A compact sequence rail keeps the icon related to the banner system.
        $graphics.FillRectangle($railBrush, 78, 270, 144, 2)
        $graphics.FillRectangle($cyanBrush, 82, 268, 42, 6)
        $graphics.FillRectangle($blueBrush, 130, 268, 30, 6)
        $graphics.FillRectangle($violetBrush, 166, 268, 22, 6)
        $graphics.FillRectangle($amberBrush, 194, 268, 24, 6)

        Save-RgbPng -Bitmap $bitmap -Path $Path
    }
    finally {
        $railBrush.Dispose()
        $amberBrush.Dispose()
        $violetBrush.Dispose()
        $blueBrush.Dispose()
        $cyanBrush.Dispose()
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

function Write-DesktopBanner {
    param(
        [Parameter(Mandatory = $true)]$Source,
        [Parameter(Mandatory = $true)][System.Drawing.Rectangle]$LogoSource,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $width = 4000
    $height = 192
    $bitmap = [System.Drawing.Bitmap]::new(
        $width,
        $height,
        [System.Drawing.Imaging.PixelFormat]::Format24bppRgb
    )
    $bitmap.SetResolution([single]96, [single]96)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $cyanBrush = [System.Drawing.SolidBrush]::new($script:Cyan)
    $blueBrush = [System.Drawing.SolidBrush]::new($script:Blue)
    $violetBrush = [System.Drawing.SolidBrush]::new($script:Violet)
    $amberBrush = [System.Drawing.SolidBrush]::new($script:Amber)
    $railBrush = [System.Drawing.SolidBrush]::new($script:Rail)
    $tickBrush = [System.Drawing.SolidBrush]::new($script:Tick)

    try {
        Set-QualityRendering -Graphics $graphics
        $graphics.Clear($script:Charcoal)

        # Wide decorative rails remain expendable outside the centered safe zone.
        $graphics.FillRectangle($railBrush, 0, 18, $width, 2)
        $graphics.FillRectangle($railBrush, 0, 172, $width, 2)
        for ($x = 40; $x -lt $width; $x += 80) {
            $graphics.FillRectangle($tickBrush, $x, 13, 2, 12)
            $graphics.FillRectangle($tickBrush, $x, 167, 2, 12)
        }

        $graphics.FillRectangle($cyanBrush, 120, 16, 380, 6)
        $graphics.FillRectangle($blueBrush, 540, 16, 210, 6)
        $graphics.FillRectangle($violetBrush, 790, 16, 315, 6)
        $graphics.FillRectangle($amberBrush, 1145, 16, 92, 6)
        $graphics.FillRectangle($blueBrush, 2760, 170, 310, 6)
        $graphics.FillRectangle($cyanBrush, 3110, 170, 470, 6)
        $graphics.FillRectangle($violetBrush, 3620, 170, 180, 6)
        $graphics.FillRectangle($amberBrush, 3838, 170, 66, 6)

        # Current Reddit's centered 1072x128 safe area is x=1464..2536,
        # y=32..160. Keep the complete logo and side sequences inside it.
        $graphics.FillRectangle($railBrush, 1496, 95, 218, 2)
        $graphics.FillRectangle($cyanBrush, 1512, 92, 72, 8)
        $graphics.FillRectangle($blueBrush, 1594, 92, 42, 8)
        $graphics.FillRectangle($violetBrush, 1646, 92, 52, 8)

        $graphics.FillRectangle($railBrush, 2286, 95, 218, 2)
        $graphics.FillRectangle($violetBrush, 2302, 92, 52, 8)
        $graphics.FillRectangle($blueBrush, 2364, 92, 42, 8)
        $graphics.FillRectangle($amberBrush, 2416, 92, 72, 8)

        $logoHeight = 104
        $logoWidth = [int][System.Math]::Round(
            $LogoSource.Width * ($logoHeight / [double]$LogoSource.Height)
        )
        $logoDestination = [System.Drawing.Rectangle]::new(
            [int][System.Math]::Round(($width - $logoWidth) / 2.0),
            [int][System.Math]::Round(($height - $logoHeight) / 2.0),
            $logoWidth,
            $logoHeight
        )
        $graphics.DrawImage(
            $Source,
            $logoDestination,
            $LogoSource,
            [System.Drawing.GraphicsUnit]::Pixel
        )

        Save-RgbPng -Bitmap $bitmap -Path $Path
    }
    finally {
        $tickBrush.Dispose()
        $railBrush.Dispose()
        $amberBrush.Dispose()
        $violetBrush.Dispose()
        $blueBrush.Dispose()
        $cyanBrush.Dispose()
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

function Write-MobileBanner {
    param(
        [Parameter(Mandatory = $true)]$Source,
        [Parameter(Mandatory = $true)][System.Drawing.Rectangle]$LogoSource,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $width = 1080
    $height = 128
    $bitmap = [System.Drawing.Bitmap]::new(
        $width,
        $height,
        [System.Drawing.Imaging.PixelFormat]::Format24bppRgb
    )
    $bitmap.SetResolution([single]96, [single]96)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $cyanBrush = [System.Drawing.SolidBrush]::new($script:Cyan)
    $blueBrush = [System.Drawing.SolidBrush]::new($script:Blue)
    $violetBrush = [System.Drawing.SolidBrush]::new($script:Violet)
    $amberBrush = [System.Drawing.SolidBrush]::new($script:Amber)
    $railBrush = [System.Drawing.SolidBrush]::new($script:Rail)
    $tickBrush = [System.Drawing.SolidBrush]::new($script:Tick)

    try {
        Set-QualityRendering -Graphics $graphics
        $graphics.Clear($script:Charcoal)

        $graphics.FillRectangle($railBrush, 0, 12, $width, 2)
        $graphics.FillRectangle($railBrush, 0, 114, $width, 2)
        for ($x = 24; $x -lt $width; $x += 48) {
            $graphics.FillRectangle($tickBrush, $x, 9, 2, 8)
            $graphics.FillRectangle($tickBrush, $x, 111, 2, 8)
        }

        $graphics.FillRectangle($cyanBrush, 42, 10, 122, 6)
        $graphics.FillRectangle($blueBrush, 176, 10, 72, 6)
        $graphics.FillRectangle($violetBrush, 260, 10, 96, 6)
        $graphics.FillRectangle($blueBrush, 734, 112, 92, 6)
        $graphics.FillRectangle($cyanBrush, 838, 112, 142, 6)
        $graphics.FillRectangle($amberBrush, 992, 112, 46, 6)

        # Side rails remain readable without competing with the wordmark.
        $graphics.FillRectangle($railBrush, 62, 63, 238, 2)
        $graphics.FillRectangle($cyanBrush, 82, 60, 76, 8)
        $graphics.FillRectangle($blueBrush, 170, 60, 48, 8)
        $graphics.FillRectangle($violetBrush, 230, 60, 54, 8)

        $graphics.FillRectangle($railBrush, 780, 63, 238, 2)
        $graphics.FillRectangle($violetBrush, 796, 60, 54, 8)
        $graphics.FillRectangle($blueBrush, 862, 60, 48, 8)
        $graphics.FillRectangle($amberBrush, 922, 60, 76, 8)

        $logoHeight = 76
        $logoWidth = [int][System.Math]::Round(
            $LogoSource.Width * ($logoHeight / [double]$LogoSource.Height)
        )
        $logoDestination = [System.Drawing.Rectangle]::new(
            [int][System.Math]::Round(($width - $logoWidth) / 2.0),
            [int][System.Math]::Round(($height - $logoHeight) / 2.0),
            $logoWidth,
            $logoHeight
        )
        $graphics.DrawImage(
            $Source,
            $logoDestination,
            $LogoSource,
            [System.Drawing.GraphicsUnit]::Pixel
        )

        Save-RgbPng -Bitmap $bitmap -Path $Path
    }
    finally {
        $tickBrush.Dispose()
        $railBrush.Dispose()
        $amberBrush.Dispose()
        $violetBrush.Dispose()
        $blueBrush.Dispose()
        $cyanBrush.Dispose()
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

$repoRoot = Find-NeXrollRepoRoot -StartPath $PSScriptRoot
$logoPath = Join-Path $repoRoot 'NeXroll/frontend/public/NeXroll_Logo_WHT.png'
$assetDirectory = Join-Path $repoRoot 'community/reddit/assets'
[System.IO.Directory]::CreateDirectory($assetDirectory) | Out-Null

$script:Charcoal = [System.Drawing.Color]::FromArgb(26, 26, 26)
$script:Cyan = [System.Drawing.Color]::FromArgb(0, 212, 255)
$script:Blue = [System.Drawing.Color]::FromArgb(59, 130, 246)
$script:Violet = [System.Drawing.Color]::FromArgb(79, 70, 229)
$script:Amber = [System.Drawing.Color]::FromArgb(245, 158, 11)
$script:Rail = [System.Drawing.Color]::FromArgb(58, 58, 58)
$script:Tick = [System.Drawing.Color]::FromArgb(44, 44, 44)

$source = [System.Drawing.Bitmap]::FromFile($logoPath)
try {
    if ($source.Width -ne 649 -or $source.Height -ne 164) {
        throw "Canonical logo dimensions changed: expected 649x164, found $($source.Width)x$($source.Height)."
    }

    # Alpha bounds measured from the canonical source. The mark crop includes
    # one transparent bottom row so its 134x133 artwork stays square when scaled.
    $logoSource = [System.Drawing.Rectangle]::new(13, 2, 631, 133)
    $markSource = [System.Drawing.Rectangle]::new(510, 2, 134, 134)

    Write-CommunityIcon `
        -Source $source `
        -MarkSource $markSource `
        -Path (Join-Path $assetDirectory 'reddit-community-icon.png')

    Write-DesktopBanner `
        -Source $source `
        -LogoSource $logoSource `
        -Path (Join-Path $assetDirectory 'reddit-banner-desktop.png')

    Write-MobileBanner `
        -Source $source `
        -LogoSource $logoSource `
        -Path (Join-Path $assetDirectory 'reddit-banner-mobile.png')
}
finally {
    $source.Dispose()
}

Get-ChildItem -LiteralPath $assetDirectory -Filter 'reddit-*.png' |
    Sort-Object Name |
    ForEach-Object {
        $image = [System.Drawing.Image]::FromFile($_.FullName)
        try {
            "{0}: {1}x{2} ({3:N0} bytes)" -f $_.Name, $image.Width, $image.Height, $_.Length
        }
        finally {
            $image.Dispose()
        }
    }
