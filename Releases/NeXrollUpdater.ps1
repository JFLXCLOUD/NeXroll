<#
NeXroll updater (Windows installer builds).

The installer registers a "NeXroll Updater" scheduled task that runs this
script as SYSTEM. NeXroll starts the task when someone clicks Install update.
The script installs a NeXroll release from GitHub, then starts NeXroll again
the way it was running before: the service, and the tray or NeXroll.exe for
each user who had one open.

The task runs as SYSTEM and any signed-in user may start it, so:
- It installs only an official release newer than the installed version,
  after checking the installer's SHA-256 against the digest GitHub publishes
  for it. A downgrade is never installed.
- Everything it writes (download, status, log) stays in <install dir>\update,
  which only administrators can change.
- The request NeXroll leaves in ProgramData, which every user can write, only
  picks the version and the port. It is read as untrusted input, and this
  script never writes, deletes or runs anything there.

Usage:
  NeXrollUpdater.ps1               install the update NeXroll asked for (the task runs this)
  NeXrollUpdater.ps1 -Register     create or refresh the task (the installer runs this)
  NeXrollUpdater.ps1 -Unregister   remove the task (the uninstaller runs this)

-ApiBase, -DownloadPrefix, -InstalledVersion and -NoInstall exist for tests.
The task always runs with the defaults; anyone passing other values runs the
script as themselves, with their own rights.

Keep this file ASCII: Windows PowerShell 5.1 reads a script without a BOM in
the ANSI code page.
#>
[CmdletBinding()]
param(
    [switch]$Register,
    [switch]$Unregister,
    # Defaults to this script's folder (set below: $PSScriptRoot is empty in
    # an advanced script's parameter defaults in Windows PowerShell 5.1).
    [string]$InstallDir = '',
    [string]$RequestFile = (Join-Path $env:ProgramData 'NeXroll\update-request.json'),
    [string]$ApiBase = 'https://api.github.com/repos/JFLXCLOUD/NeXroll',
    [string]$DownloadPrefix = 'https://github.com/JFLXCLOUD/NeXroll/releases/download/',
    [string]$InstalledVersion = '',
    [switch]$NoInstall
)

$ErrorActionPreference = 'Stop'
# Windows PowerShell 5.1 redraws a progress bar for every downloaded block,
# which makes a 100 MB download take minutes.
$ProgressPreference = 'SilentlyContinue'

$TaskName = 'NeXroll Updater'
# Lets every signed-in user read and start the task. Starting it is all they
# can do: the task takes no arguments, and the rules above limit what it installs.
$RunAce = '(A;;GRGX;;;AU)'
# How Windows stores it once set.
$RunAcePattern = '\(A;;(GRGX|0x1200a9);;;AU\)'
$VersionPattern = '^\d{1,4}\.\d{1,4}\.\d{1,4}(-[A-Za-z]{1,12}(\.?\d{1,4})?)?$'
$Utf8 = New-Object System.Text.UTF8Encoding $false

if (-not $InstallDir) { $InstallDir = $PSScriptRoot }
$InstallDir = $InstallDir.TrimEnd('\')
$UpdateDir = Join-Path $InstallDir 'update'
$StatusFile = Join-Path $UpdateDir 'status.json'
$LogFile = Join-Path $UpdateDir 'update.log'

$Status = [ordered]@{
    state        = 'starting'
    message      = ''
    request_id   = $null
    from_version = $null
    to_version   = $null
    started_at   = (Get-Date).ToUniversalTime().ToString('o')
    updated_at   = $null
}

function Write-Log([string]$Message) {
    $line = '{0} {1}' -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $Message
    try {
        if ((Test-Path -LiteralPath $LogFile) -and (Get-Item -LiteralPath $LogFile).Length -gt 1MB) {
            Move-Item -LiteralPath $LogFile -Destination "$LogFile.1" -Force
        }
        [System.IO.File]::AppendAllText($LogFile, $line + "`r`n", $Utf8)
    } catch { }
}

function Set-Status([string]$State, [string]$Message) {
    $Status.state = $State
    $Status.message = $Message
    $Status.updated_at = (Get-Date).ToUniversalTime().ToString('o')
    Write-Log "[$State] $Message"
    try {
        $tmp = "$StatusFile.tmp"
        [System.IO.File]::WriteAllText($tmp, ($Status | ConvertTo-Json), $Utf8)
        Move-Item -LiteralPath $tmp -Destination $StatusFile -Force
    } catch {
        Write-Log "Could not write the status file: $($_.Exception.Message)"
    }
}

# ---------------------------------------------------------------------------
# Versions (same ordering as the backend's /update/check)
# ---------------------------------------------------------------------------

function ConvertTo-VersionKey([string]$Value) {
    $s = ($Value -replace '^[vV]', '').Trim()
    $m = [regex]::Match($s, '^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[.-]([A-Za-z]+)[.-]?(\d+)?)?')
    if (-not $m.Success) { return $null }
    $part = { param($g) if ($m.Groups[$g].Success -and $m.Groups[$g].Value) { [int]$m.Groups[$g].Value } else { 0 } }
    # A stable release sorts after every pre-release of the same version.
    $rank = 100
    if ($m.Groups[4].Success) {
        $ranks = @{ alpha = 0; beta = 1; rc = 2 }
        $tag = $m.Groups[4].Value.ToLower()
        $rank = if ($ranks.ContainsKey($tag)) { $ranks[$tag] } else { 99 }
    }
    return @((& $part 1), (& $part 2), (& $part 3), $rank, (& $part 5))
}

function Compare-Version([string]$A, [string]$B) {
    $ka = ConvertTo-VersionKey $A
    $kb = ConvertTo-VersionKey $B
    if ($null -eq $ka -or $null -eq $kb) { throw "Cannot compare versions '$A' and '$B'" }
    for ($i = 0; $i -lt 5; $i++) {
        if ($ka[$i] -gt $kb[$i]) { return 1 }
        if ($ka[$i] -lt $kb[$i]) { return -1 }
    }
    return 0
}

function Get-InstalledVersion {
    if ($InstalledVersion) { return $InstalledVersion }
    foreach ($view in @([Microsoft.Win32.RegistryView]::Registry64, [Microsoft.Win32.RegistryView]::Registry32)) {
        try {
            $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine, $view)
            $key = $base.OpenSubKey('Software\NeXroll')
            if ($key) {
                $v = [string]$key.GetValue('Version')
                $key.Close()
                if ($v -and $v.Trim()) { return $v.Trim() }
            }
        } catch { }
    }
    # Installers before 2.2.8 often skipped the registry writes.
    try {
        $v = (Get-Item -LiteralPath (Join-Path $InstallDir 'NeXroll.exe')).VersionInfo.ProductVersion
        if ($v -and $v.Trim()) { return $v.Trim() }
    } catch { }
    return $null
}

# ---------------------------------------------------------------------------
# The request NeXroll left (untrusted)
# ---------------------------------------------------------------------------

function Read-Request {
    $request = @{ version = $null; port = 9393; request_id = $null }
    $machinePort = 0
    if ([int]::TryParse([string][Environment]::GetEnvironmentVariable('NEXROLL_PORT', 'Machine'), [ref]$machinePort) -and
        $machinePort -ge 1 -and $machinePort -le 65535) {
        $request.port = $machinePort
    }
    try {
        $item = Get-Item -LiteralPath $RequestFile -ErrorAction Stop
    } catch {
        Write-Log 'No update request found; looking for the latest stable release'
        return $request
    }
    try {
        if ($item.PSIsContainer -or $item.Length -gt 16KB) { throw 'not a request file' }
        if (((Get-Date) - $item.LastWriteTime).TotalMinutes -gt 30) {
            Write-Log 'Ignoring an update request older than 30 minutes; looking for the latest stable release'
            return $request
        }
        $data = [System.IO.File]::ReadAllText($item.FullName) | ConvertFrom-Json
        if ($data.version -is [string] -and $data.version -match $VersionPattern) { $request.version = $data.version }
        $port = 0
        if ([int]::TryParse([string]$data.port, [ref]$port) -and $port -ge 1 -and $port -le 65535) { $request.port = $port }
        if ($data.request_id -is [string] -and $data.request_id -match '^[0-9a-f]{8,64}$') { $request.request_id = $data.request_id }
    } catch {
        # Never echo the file: it could be a link to something this account
        # can read and the user cannot.
        Write-Log 'Ignoring an unreadable update request'
    }
    return $request
}

# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------

function Enable-ModernTls {
    try {
        $protocols = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        try { $protocols = $protocols -bor [Net.SecurityProtocolType]'Tls13' } catch { }
        [Net.ServicePointManager]::SecurityProtocol = $protocols
    } catch { }
}

function Get-Release([string]$Version) {
    $path = if ($Version) { "/releases/tags/v$Version" } else { '/releases/latest' }
    $headers = @{ 'User-Agent' = 'NeXroll-Updater'; 'Accept' = 'application/vnd.github+json' }
    try {
        return Invoke-RestMethod -Uri ($ApiBase.TrimEnd('/') + $path) -Headers $headers -UseBasicParsing -TimeoutSec 30
    } catch {
        $code = $null
        try { $code = [int]$_.Exception.Response.StatusCode } catch { }
        if ($code -eq 404 -and $Version) { throw "GitHub has no NeXroll release v$Version" }
        throw "Could not reach GitHub: $($_.Exception.Message)"
    }
}

function Get-VerifiedInstaller($Release, [string]$Version) {
    $assetName = "NeXroll_Installer_v$Version.exe"
    $asset = @($Release.assets) | Where-Object { $_.name -eq $assetName } | Select-Object -First 1
    if (-not $asset) { throw "The v$Version release has no $assetName" }
    $digest = [string]$asset.digest
    if ($digest -notmatch '^sha256:([0-9a-fA-F]{64})$') { throw "GitHub lists no SHA-256 digest for $assetName" }
    $expected = $Matches[1].ToLowerInvariant()
    $url = [string]$asset.browser_download_url
    if (-not $url.StartsWith($DownloadPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "$assetName is not on the NeXroll release page"
    }
    if ([int64]$asset.size -gt 1GB) { throw "$assetName is unexpectedly large" }

    $target = Join-Path $UpdateDir $assetName
    if (Test-Path -LiteralPath $target) {
        if ((Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant() -eq $expected) {
            Write-Log "Using the $assetName downloaded earlier"
            return $target
        }
        Remove-Item -LiteralPath $target -Force
    }
    $part = "$target.part"
    Set-Status 'downloading' "Downloading NeXroll $Version"
    try {
        Invoke-WebRequest -Uri $url -OutFile $part -UseBasicParsing -TimeoutSec 600 -Headers @{ 'User-Agent' = 'NeXroll-Updater' }
    } catch {
        Remove-Item -LiteralPath $part -Force -ErrorAction SilentlyContinue
        throw "Could not download $($assetName): $($_.Exception.Message)"
    }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $part).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        Remove-Item -LiteralPath $part -Force -ErrorAction SilentlyContinue
        throw "The downloaded installer does not match the SHA-256 GitHub lists for it; nothing was installed"
    }
    Move-Item -LiteralPath $part -Destination $target -Force
    Write-Log "Downloaded $assetName (sha256 $actual)"
    return $target
}

# ---------------------------------------------------------------------------
# How NeXroll is running, so it comes back the same way
# ---------------------------------------------------------------------------

function Get-RunningState {
    $state = @{ service = $false; trayUsers = @(); appUsers = @(); detected = $false }
    try {
        $svc = Get-Service -Name 'NeXrollService' -ErrorAction SilentlyContinue
        if ($svc -and $svc.Status -eq 'Running') { $state.service = $true }
        $procs = @(Get-CimInstance -ClassName Win32_Process -Filter "Name='NeXroll.exe' OR Name='NeXrollTray.exe'")
        $state.detected = $true
        $tray = @{}
        $app = @{}
        foreach ($p in $procs) {
            $owner = Invoke-CimMethod -InputObject $p -MethodName GetOwner -ErrorAction SilentlyContinue
            if (-not $owner -or $owner.ReturnValue -ne 0 -or -not $owner.User) { continue }
            # The service's NeXroll.exe runs as SYSTEM; starting the service brings it back.
            if ($owner.Domain -eq 'NT AUTHORITY') { continue }
            $user = if ($owner.Domain) { "$($owner.Domain)\$($owner.User)" } else { [string]$owner.User }
            if ($p.Name -eq 'NeXrollTray.exe') { $tray[$user] = $true } else { $app[$user] = $true }
        }
        $state.trayUsers = @($tray.Keys)
        # A user's tray starts their NeXroll.exe itself.
        $state.appUsers = @($app.Keys | Where-Object { -not $tray.ContainsKey($_) })
    } catch {
        Write-Log "Could not read how NeXroll is running: $($_.Exception.Message)"
    }
    $parts = @()
    if ($state.service) { $parts += 'service' }
    if ($state.trayUsers.Count) { $parts += "tray for $($state.trayUsers -join ', ')" }
    if ($state.appUsers.Count) { $parts += "NeXroll.exe for $($state.appUsers -join ', ')" }
    Write-Log ("Running before the update: " + $(if ($parts.Count) { $parts -join '; ' } else { 'nothing found' }))
    return $state
}

function Start-InUserSession([string]$Exe, $Principal) {
    # A one-off task is how SYSTEM starts a program in a signed-in user's
    # session without elevating it (the installer launches the tray this way).
    $name = 'NeXroll Relaunch'
    $action = New-ScheduledTaskAction -Execute $Exe -WorkingDirectory $InstallDir
    # No time limit: Task Scheduler would otherwise stop the program after 72 hours.
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
    Register-ScheduledTask -TaskName $name -Action $action -Principal $Principal -Settings $settings -Force | Out-Null
    try {
        Start-ScheduledTask -TaskName $name
        Start-Sleep -Seconds 3
    } finally {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
    }
}

function Restore-RunningState($State) {
    $tray = Join-Path $InstallDir 'NeXrollTray.exe'
    $app = Join-Path $InstallDir 'NeXroll.exe'
    if ($State.service) {
        try { Start-Service -Name 'NeXrollService'; Write-Log 'Started the NeXroll service' }
        catch { Write-Log "Could not start the NeXroll service: $($_.Exception.Message)" }
    }
    foreach ($user in $State.trayUsers) {
        try {
            Start-InUserSession $tray (New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited)
            Write-Log "Started the tray for $user"
        } catch { Write-Log "Could not start the tray for $($user): $($_.Exception.Message)" }
    }
    foreach ($user in $State.appUsers) {
        try {
            Start-InUserSession $app (New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited)
            Write-Log "Started NeXroll.exe for $user"
        } catch { Write-Log "Could not start NeXroll.exe for $($user): $($_.Exception.Message)" }
    }
    if (-not $State.detected) {
        # Same as the installer: the tray for whoever is signed in.
        try {
            Start-InUserSession $tray (New-ScheduledTaskPrincipal -GroupId 'S-1-5-32-545' -RunLevel Limited)
            Write-Log 'Started the tray for signed-in users'
        } catch { Write-Log "Could not start the tray: $($_.Exception.Message)" }
    }
}

function Test-Healthy([int]$Port) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health" -UseBasicParsing -TimeoutSec 5
        return $r.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Wait-Healthy([int]$Port, [int]$Seconds) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Healthy $Port) { return $true }
        Start-Sleep -Seconds 3
    }
    return $false
}

function Invoke-Installer([string]$Path) {
    $p = Start-Process -FilePath $Path -ArgumentList '/S', '/UPDATE' -PassThru
    # Without holding the handle, ExitCode stays empty after the process ends.
    $null = $p.Handle
    if (-not $p.WaitForExit(15 * 60 * 1000)) {
        try { $p.Kill() } catch { }
        throw 'The installer did not finish within 15 minutes'
    }
    return $p.ExitCode
}

function Remove-Installers {
    # Kept only while an update hasn't gone through, so a retry needn't download again.
    Get-ChildItem -LiteralPath $UpdateDir -Filter 'NeXroll_Installer_v*.exe*' -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue }
}

# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

function Invoke-Update {
    $request = Read-Request
    $Status.request_id = $request.request_id
    $installed = Get-InstalledVersion
    $Status.from_version = $installed
    if (-not $installed) { throw 'Could not read the installed NeXroll version' }

    Set-Status 'checking' 'Looking for the release on GitHub'
    Enable-ModernTls
    $release = Get-Release $request.version
    if ($release.draft) { throw 'That release is not published' }
    $version = ([string]$release.tag_name) -replace '^[vV]', ''
    if ($version -notmatch $VersionPattern) { throw "Unexpected release tag '$($release.tag_name)'" }
    $Status.to_version = $version
    if ((Compare-Version $version $installed) -le 0) {
        Set-Status 'up_to_date' "NeXroll $installed is installed and $version is not newer; nothing to install"
        return
    }

    $installer = Get-VerifiedInstaller $release $version
    if ($NoInstall) {
        Set-Status 'verified' "Downloaded and checked NeXroll $version; not installed (-NoInstall)"
        return
    }

    $before = Get-RunningState
    Set-Status 'installing' "Installing NeXroll $version"
    $code = Invoke-Installer $installer
    Set-Status 'restarting' 'Starting NeXroll'
    # An installer that gave up before stopping NeXroll leaves it running.
    if (Test-Healthy $request.port) {
        Write-Log 'NeXroll is still running; nothing to restart'
    } else {
        Restore-RunningState $before
    }
    if ($code -ne 0) {
        throw "The NeXroll $version installer stopped with code $code. If NeXroll does not start, run the installer from the release page"
    }
    Remove-Installers
    if (Wait-Healthy $request.port 240) {
        Set-Status 'done' "Updated NeXroll from $installed to $version"
    } else {
        Set-Status 'failed' "NeXroll $version is installed but did not answer on port $($request.port) within 4 minutes"
    }
}

# ---------------------------------------------------------------------------
# Task registration (installer and uninstaller)
# ---------------------------------------------------------------------------

function Get-OpenAccess {
    # Allow entries that let someone other than SYSTEM, Administrators or
    # TrustedInstaller change files here. CREATOR OWNER only matters to
    # someone who can create files, so it isn't counted on its own.
    $trusted = @('S-1-5-18', 'S-1-5-32-544', 'S-1-3-0',
        'S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464')
    $write = [Security.AccessControl.FileSystemRights]'WriteData, AppendData, WriteAttributes, WriteExtendedAttributes, Delete, DeleteSubdirectoriesAndFiles, ChangePermissions, TakeOwnership'
    $acl = Get-Acl -LiteralPath $InstallDir
    return @($acl.Access | Where-Object {
        $ace = $_
        $sid = try { $ace.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value } catch { [string]$ace.IdentityReference.Value }
        $ace.AccessControlType -eq 'Allow' -and ($ace.FileSystemRights -band $write) -and ($trusted -notcontains $sid)
    } | ForEach-Object { $_.IdentityReference.Value } | Select-Object -Unique)
}

function Protect-InstallDir {
    # The task runs this script as SYSTEM, so only administrators may be able
    # to change it. Program Files is like that; a folder picked elsewhere (a
    # second drive, say) often lets every user change it, which would hand
    # SYSTEM to anyone signed in (NeXrollService.exe has the same exposure).
    # Such a folder gets the Program Files permissions.
    $open = Get-OpenAccess
    if (-not $open.Count) { return $true }
    Write-Output "The install folder can be changed by $($open -join ', '); limiting changes to administrators"
    & icacls.exe $InstallDir /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-32-545:(OI)(CI)RX' /Q | Out-Null
    foreach ($id in $open) {
        & icacls.exe $InstallDir /remove:g $id /Q | Out-Null
    }
    $still = Get-OpenAccess
    if ($still.Count) {
        Write-Output "Could not secure the install folder ($($still -join ', ') can still change it); Install update stays off"
        return $false
    }
    return $true
}

function Get-TaskArguments {
    $script = Join-Path $InstallDir 'NeXrollUpdater.ps1'
    return '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $script + '"'
}

function Register-UpdaterTask {
    $scheduler = New-Object -ComObject 'Schedule.Service'
    $scheduler.Connect()
    if (-not (Protect-InstallDir)) {
        try { $scheduler.GetFolder('\').DeleteTask($TaskName, 0) } catch { }
        return
    }
    $folder = $scheduler.GetFolder('\')
    $exe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $arguments = Get-TaskArguments

    $existing = $null
    try { $existing = $folder.GetTask($TaskName) } catch { }
    $current = $false
    if ($existing) {
        $action = @($existing.Definition.Actions)[0]
        $current = $action -and $action.Path -eq $exe -and $action.Arguments -eq $arguments -and
            $existing.Definition.Principal.UserId -match 'SYSTEM|S-1-5-18'
    }
    # During an update the task is running this script's old copy; leave a
    # task that already says the right thing untouched.
    if (-not $current) {
        $def = $scheduler.NewTask(0)
        $def.RegistrationInfo.Author = 'NeXroll'
        $def.RegistrationInfo.Description = 'Installs a NeXroll update when NeXroll asks for one. Installs only official releases newer than the one installed.'
        $def.Settings.Enabled = $true
        $def.Settings.AllowDemandStart = $true
        $def.Settings.MultipleInstances = 2          # ignore a second start while one runs
        $def.Settings.ExecutionTimeLimit = 'PT1H'
        $def.Settings.DisallowStartIfOnBatteries = $false
        $def.Settings.StopIfGoingOnBatteries = $false
        $def.Principal.RunLevel = 1                  # highest
        $action = $def.Actions.Create(0)             # run a program
        $action.Path = $exe
        $action.Arguments = $arguments
        $action.WorkingDirectory = $InstallDir
        # 6 = create or update, 5 = service account
        $null = $folder.RegisterTaskDefinition($TaskName, $def, 6, 'SYSTEM', $null, 5)
        Write-Output "Registered the $TaskName task"
    }
    $task = $folder.GetTask($TaskName)
    $sddl = $task.GetSecurityDescriptor(4)           # DACL only
    if ($sddl -notmatch $RunAcePattern) {
        # Explicit entries go before the inherited ones.
        $updated = if ($sddl -match '^D:[A-Z]*') { $sddl.Insert($Matches[0].Length, $RunAce) } else { $sddl + $RunAce }
        $task.SetSecurityDescriptor($updated, 0)
        Write-Output "Let signed-in users start the $TaskName task"
    }
}

function Unregister-UpdaterTask {
    $scheduler = New-Object -ComObject 'Schedule.Service'
    $scheduler.Connect()
    try {
        $scheduler.GetFolder('\').DeleteTask($TaskName, 0)
        Write-Output "Removed the $TaskName task"
    } catch { }
}

# ---------------------------------------------------------------------------

if ($Register) { Register-UpdaterTask; exit 0 }
if ($Unregister) { Unregister-UpdaterTask; exit 0 }

New-Item -ItemType Directory -Path $UpdateDir -Force | Out-Null
$mutex = New-Object System.Threading.Mutex($false, 'Global\NeXrollUpdater')
if (-not $mutex.WaitOne(0)) {
    Write-Log 'Another update is already running'
    exit 0
}
try {
    Write-Log "Updater started as $([Security.Principal.WindowsIdentity]::GetCurrent().Name)"
    Invoke-Update
    exit 0
} catch {
    Set-Status 'failed' $_.Exception.Message
    exit 1
} finally {
    $mutex.ReleaseMutex()
}
