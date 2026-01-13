; NeXroll Installer Script (NSIS 3+)
; Builds a single installer that:
; - Lets user choose install directory and a separate Preroll storage directory
; - Optionally installs FFmpeg via winget
; - Optionally installs NeXroll as a Windows Service
; - Optionally runs Plex Stable Token setup
; - Optionally creates a Startup shortcut
; - Writes InstallDir and PrerollPath to HKLM\Software\NeXroll
; - Installs only runtime files (no venv/sources)

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "nsDialogs.nsh"

Name "NeXroll"
InstallDir "$PROGRAMFILES64\NeXroll"
InstallDirRegKey HKLM "Software\NeXroll" "InstallDir"
RequestExecutionLevel admin
ShowInstDetails show
Icon "NeXroll_ICON\icon_1758297097_64x64.ico"
UninstallIcon "NeXroll_ICON\icon_1758297097_32x32.ico"

!define APP_VERSION "1.9.8"
VIProductVersion "1.9.8.0"
VIAddVersionKey /LANG=1033 "ProductName" "NeXroll"
VIAddVersionKey /LANG=1033 "ProductVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=1033 "FileVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=1033 "CompanyName" "JFLXCLOUD"
VIAddVersionKey /LANG=1033 "FileDescription" "NeXroll Installer"
VIAddVersionKey /LANG=1033 "LegalCopyright" "© 2025 JFLXCLOUD"
OutFile "NeXroll_Installer_v${APP_VERSION}.exe"
 
; Variables
Var PREROLL_PATH
Var hPrerollEdit

; Interface
!define MUI_ABORTWARNING
!define MUI_HEADERIMAGE

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
Page custom PrerollPathPageCreate PrerollPathPageLeave
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_LANGUAGE "English"

; ------------------------------
; Custom Page - Preroll Path
; ------------------------------
Function PrerollPathPageCreate
  nsDialogs::Create 1018
  Pop $0
 
  ${NSD_CreateLabel} 0 0 100% 12u "Select Preroll Video Storage"
  ${NSD_CreateLabel} 0 18u 100% 12u "Choose a directory where Preroll videos will be stored:"
  
  ; Default path from registry if available
  ReadRegStr $PREROLL_PATH HKLM "Software\NeXroll" "PrerollPath"
  ${If} $PREROLL_PATH == ""
    ReadEnvStr $PREROLL_PATH "ProgramData"
    StrCpy $PREROLL_PATH "$PREROLL_PATH\NeXroll\Prerolls"
  ${EndIf}
  ${NSD_CreateText} 0 36u 80% 12u "$PREROLL_PATH"
  Pop $hPrerollEdit
 
  ${NSD_CreateButton} 82% 35u 18% 14u "Browse..."
  Pop $1
  ${NSD_OnClick} $1 PrerollPathBrowse
 
  nsDialogs::Show
FunctionEnd

Function PrerollPathBrowse
  nsDialogs::SelectFolderDialog "Select Preroll Video Storage Folder" "$PREROLL_PATH"
  Pop $0
  ${If} $0 == "error"
    Return
  ${EndIf}
  ${If} $0 == ""
    Return
  ${EndIf}
  ; Update variable and textbox
  StrCpy $PREROLL_PATH "$0"
  ${NSD_SetText} $hPrerollEdit "$PREROLL_PATH"
FunctionEnd

Function PrerollPathPageLeave
  ${NSD_GetText} $hPrerollEdit $PREROLL_PATH
  ${If} $PREROLL_PATH == ""
    ReadEnvStr $PREROLL_PATH "ProgramData"
    StrCpy $PREROLL_PATH "$PREROLL_PATH\NeXroll\Prerolls"
  ${EndIf}
FunctionEnd

; ------------------------------
; Components
; ------------------------------
Section "!NeXroll Application (Required)" SEC_APP
  SectionIn RO
  SetOutPath "$INSTDIR"
  SetOverwrite on

  ; Runtime files only (built by PyInstaller)
  ; IMPORTANT: These paths are relative to the directory containing this .nsi file
  ; The build MUST use absolute paths or be run from the NeXroll working directory
  ;
  ; If you get "Package error: required build artifact not found":
  ; 1. You MUST build the frontend first: cd frontend && npm run build && cd ..
  ; 2. You MUST build the executables: cd build && pyinstaller --clean *.spec && cd ..
  ; 3. You MUST run makensis from the NeXroll directory
  ; 4. Expected file locations relative to installer.nsi:
  ;    - dist\NeXroll.exe
  ;    - dist\NeXrollService.exe
  ;    - dist\setup_plex_token.exe
  ;    - dist\NeXrollTray.exe
  ;    - frontend\build\* (frontend static assets)
  ;    - NeXroll_ICON\icon_*.ico (icons)
  ;    - start_windows.bat (optional launcher)

  ; Main app (onefile output goes directly under dist\)
  File "dist\NeXroll.exe"
  ; Windows service wrapper (onefile output)
  File "dist\NeXrollService.exe"
  ; Token setup tool (onefile output)
  File "dist\setup_plex_token.exe"
  ; Tray app executable (onefile output)
  File "dist\NeXrollTray.exe"
  
  SetOutPath "$INSTDIR"
  ; Convenience start script
  File "start_windows.bat"
  
  ; Documentation
  File "CHANGELOG.md"
  File /nonfatal "README.md"

  ; Clean up legacy directories from older versions
  ; These are no longer needed as files are now bundled in executables
  DetailPrint "Removing legacy directories from previous installations..."
  nsExec::ExecToStack 'cmd /c if exist "$INSTDIR\resources" rd /s /q "$INSTDIR\resources"' $0
  Pop $0
  nsExec::ExecToStack 'cmd /c if exist "$INSTDIR\frontend" rd /s /q "$INSTDIR\frontend"' $0
  Pop $0

  ; Create preroll directory
  CreateDirectory "$PREROLL_PATH"
  ; Ensure selected preroll path is writable by standard Users (Modify rights, recursive)
  nsExec::ExecToStack 'icacls "$PREROLL_PATH" /grant *S-1-5-32-545:(OI)(CI)M /T /C' $0
  Pop $0

  ; Migrate existing prerolls from previous install directory if present
  ; This preserves user thumbnails/videos across upgrades when prior versions
  ; stored data under $INSTDIR\data\prerolls (which could be wiped on reinstall)
  IfFileExists "$INSTDIR\data\prerolls\*.*" 0 +7
    DetailPrint "Migrating existing prerolls from $INSTDIR\data\prerolls to $PREROLL_PATH"
    nsExec::ExecToStack 'cmd /c xcopy /E /I /Y "$INSTDIR\data\prerolls" "$PREROLL_PATH"' $0
    Pop $0
    ; Best-effort; ignore errors. Subdirectories (including thumbnails) are copied due to /E


  ; Persist config to registry
  ; Clear old registry entries first (for upgrades)
  DeleteRegKey /ifempty HKLM "Software\NeXroll"
  WriteRegStr HKLM "Software\NeXroll" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "Software\NeXroll" "PrerollPath" "$PREROLL_PATH"
  WriteRegStr HKLM "Software\NeXroll" "Version" "${APP_VERSION}"

  ; Ensure common ProgramData log directory exists (service/tray friendly)
  ; Create ProgramData\NeXroll and logs via cmd to avoid NSIS constant compatibility issues
  nsExec::ExecToStack 'cmd /c if not exist "%ProgramData%\NeXroll" mkdir "%ProgramData%\NeXroll"' $0
  Pop $0
  nsExec::ExecToStack 'cmd /c if not exist "%ProgramData%\NeXroll\logs" mkdir "%ProgramData%\NeXroll\logs"' $0
  Pop $0
  ; Grant standard Users Modify rights to ProgramData\NeXroll so non-admin contexts can write logs/DB/WAL
  ; Use env %ProgramData% to avoid NSIS constant compatibility issues
  nsExec::ExecToStack 'cmd /c icacls "%ProgramData%\NeXroll" /grant *S-1-5-32-545:(OI)(CI)M /T /C' $0
  Pop $0

  ; Start Menu shortcuts
  CreateDirectory "$SMPROGRAMS\NeXroll"
  CreateShortCut "$SMPROGRAMS\NeXroll\NeXroll.lnk" "$INSTDIR\NeXroll.exe" "" "$INSTDIR\NeXroll.exe" 0
  CreateShortCut "$SMPROGRAMS\NeXroll\NeXroll Tray.lnk" "$INSTDIR\NeXrollTray.exe" "" "$INSTDIR\NeXrollTray.exe" 0
  CreateShortCut "$SMPROGRAMS\NeXroll\Uninstall.lnk" "$INSTDIR\uninstall.exe" "" "$INSTDIR\uninstall.exe" 0

  ; Desktop shortcut
  CreateShortCut "$DESKTOP\NeXroll.lnk" "$INSTDIR\NeXroll.exe" "" "$INSTDIR\NeXroll.exe" 0

  ; Uninstaller
  WriteUninstaller "$INSTDIR\uninstall.exe"

  ; Add Programs and Features (Uninstall) entry
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\NeXroll" "DisplayName" "NeXroll"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\NeXroll" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\NeXroll" "Publisher" "JFLXCLOUD"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\NeXroll" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\NeXroll" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\NeXroll" "DisplayIcon" "$INSTDIR\NeXroll.exe"
SectionEnd

Section "Install as Windows Service" SEC_SERVICE
   SetOutPath "$INSTDIR"
   Call InstallService
SectionEnd

Section "Plex Stable Token Setup (Run Now)" SEC_TOKEN
   SetOutPath "$INSTDIR"
   ; Attempt to run token setup, but ignore errors if exe is missing/corrupted
   ${If} ${FileExists} "$INSTDIR\setup_plex_token.exe"
     nsExec::ExecToStack '"$INSTDIR\setup_plex_token.exe"' $0
     Pop $0
   ${EndIf}
SectionEnd

Section "Start with Windows (Startup Shortcut)" SEC_STARTUP
  CreateShortCut "$SMSTARTUP\NeXroll Tray.lnk" "$INSTDIR\NeXrollTray.exe" "" "$INSTDIR\NeXrollTray.exe" 0
SectionEnd

Section "Install Dependencies (FFmpeg via winget)" SEC_DEPS
   ; Install FFmpeg using winget if not present
   nsExec::ExecToStack 'powershell -NoProfile -ExecutionPolicy Bypass -Command "if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { winget install Gyan.FFmpeg --accept-source-agreements --accept-package-agreements -e }"' $0
   Pop $0
   ; $0 contains exit code (ignored for best-effort)
SectionEnd

; Auto-detect ffmpeg/ffprobe and record absolute paths in HKLM\Software\NeXroll
; This helps the service and tray resolve tools without relying on PATH.
Section "FFmpeg Path Registration (Auto-detect)" SEC_FFREG
  ; Detect ffmpeg.exe
  StrCpy $0 ""
  IfFileExists "$PROGRAMFILES64\ffmpeg\bin\ffmpeg.exe" 0 +2
    StrCpy $0 "$PROGRAMFILES64\ffmpeg\bin\ffmpeg.exe"
  IfFileExists "$PROGRAMFILES\ffmpeg\bin\ffmpeg.exe" 0 +2
    StrCpy $0 "$PROGRAMFILES\ffmpeg\bin\ffmpeg.exe"
  IfFileExists "$PROGRAMFILES64\FFmpeg\bin\ffmpeg.exe" 0 +2
    StrCpy $0 "$PROGRAMFILES64\FFmpeg\bin\ffmpeg.exe"
  IfFileExists "$PROGRAMFILES\FFmpeg\bin\ffmpeg.exe" 0 +2
    StrCpy $0 "$PROGRAMFILES\FFmpeg\bin\ffmpeg.exe"
  IfFileExists "%ProgramData%\chocolatey\bin\ffmpeg.exe" 0 +2
    StrCpy $0 "%ProgramData%\chocolatey\bin\ffmpeg.exe"
  IfFileExists "C:\ffmpeg\bin\ffmpeg.exe" 0 +2
    StrCpy $0 "C:\ffmpeg\bin\ffmpeg.exe"
  ${If} $0 != ""
    WriteRegStr HKLM "Software\NeXroll" "FFmpegPath" "$0"
  ${EndIf}

  ; Detect ffprobe.exe
  StrCpy $1 ""
  IfFileExists "$PROGRAMFILES64\ffmpeg\bin\ffprobe.exe" 0 +2
    StrCpy $1 "$PROGRAMFILES64\ffmpeg\bin\ffprobe.exe"
  IfFileExists "$PROGRAMFILES\ffmpeg\bin\ffprobe.exe" 0 +2
    StrCpy $1 "$PROGRAMFILES\ffmpeg\bin\ffprobe.exe"
  IfFileExists "$PROGRAMFILES64\FFmpeg\bin\ffprobe.exe" 0 +2
    StrCpy $1 "$PROGRAMFILES64\FFmpeg\bin\ffprobe.exe"
  IfFileExists "$PROGRAMFILES\FFmpeg\bin\ffprobe.exe" 0 +2
    StrCpy $1 "$PROGRAMFILES\FFmpeg\bin\ffprobe.exe"
  IfFileExists "%ProgramData%\chocolatey\bin\ffprobe.exe" 0 +2
    StrCpy $1 "%ProgramData%\chocolatey\bin\ffprobe.exe"
  IfFileExists "C:\ffmpeg\bin\ffprobe.exe" 0 +2
    StrCpy $1 "C:\ffmpeg\bin\ffprobe.exe"
  ${If} $1 != ""
    WriteRegStr HKLM "Software\NeXroll" "FFprobePath" "$1"
  ${EndIf}
SectionEnd

Section "Windows Firewall Rule (Allow TCP 9393)" SEC_FIREWALL
   ; Add inbound firewall rule for NeXroll port
   ; Only add the rule if it does not already exist
   nsExec::ExecToStack 'cmd /c netsh advfirewall firewall show rule name="NeXroll (TCP 9393)" | findstr /C:"Rule Name"' $0
   Pop $0
   ${If} $0 != 0
     nsExec::ExecToStack 'netsh advfirewall firewall add rule name="NeXroll (TCP 9393)" dir=in action=allow protocol=TCP localport=9393' $0
     Pop $0
   ${Else}
     DetailPrint "Firewall rule 'NeXroll (TCP 9393)' already exists; skipping add."
   ${EndIf}
SectionEnd

Function InstallService
  DetailPrint "Installing and starting NeXroll service..."
  ${If} ${FileExists} "$INSTDIR\NeXrollService.exe"
    nsExec::ExecToStack '"$INSTDIR\NeXrollService.exe" install' $0
    Pop $0
    ${If} $0 != 0
      DetailPrint "Service installation completed with code: $0"
    ${EndIf}
    Sleep 1000
    nsExec::ExecToStack '"$INSTDIR\NeXrollService.exe" start' $0
    Pop $0
    Sleep 2000
    ; Check service state without displaying errors
    nsExec::ExecToStack 'sc query "NeXrollService" | findstr "RUNNING"' $0
    Pop $0
    ${If} $0 != 0
      DetailPrint "Note: Service will start automatically on next system boot."
    ${EndIf}
  ${Else}
    DetailPrint "Warning: NeXrollService.exe not found; service will not be installed."
  ${EndIf}
  Return
FunctionEnd

; ------------------------------
; Uninstaller
; ------------------------------
Section "Uninstall"
  ; Stop and remove Windows service if installed
  IfFileExists "$INSTDIR\NeXrollService.exe" 0 +5
    nsExec::ExecToStack '"$INSTDIR\NeXrollService.exe" stop' $0
    Pop $0
    nsExec::ExecToStack '"$INSTDIR\NeXrollService.exe" remove' $0
    Pop $0

  ; Ensure no running processes are locking files (best-effort)
  nsExec::ExecToStack 'taskkill /F /IM NeXrollTray.exe /T' $0
  Pop $0
  nsExec::ExecToStack 'taskkill /F /IM NeXroll.exe /T' $0
  Pop $0
  nsExec::ExecToStack 'taskkill /F /IM NeXrollService.exe /T' $0
  Pop $0

  ; Remove firewall rule (best-effort)
  nsExec::ExecToStack 'netsh advfirewall firewall delete rule name="NeXroll (TCP 9393)"' $0
  Pop $0
 
  ; Remove shortcuts
  Delete "$SMPROGRAMS\NeXroll\NeXroll.lnk"
  Delete "$SMPROGRAMS\NeXroll\NeXroll Tray.lnk"
  Delete "$SMPROGRAMS\NeXroll\Uninstall.lnk"
  RMDir "$SMPROGRAMS\NeXroll"
 
  ; Remove desktop shortcut
  Delete "$DESKTOP\NeXroll.lnk"
 
  ; Remove startup shortcuts
  Delete "$SMSTARTUP\NeXroll.lnk"
  Delete "$SMSTARTUP\NeXroll Tray.lnk"
 
  ; Remove install directory (keep user data at $PREROLL_PATH)
  Delete "$INSTDIR\NeXroll.exe"
  Delete "$INSTDIR\NeXrollService.exe"
  Delete "$INSTDIR\setup_plex_token.exe"
  Delete "$INSTDIR\NeXrollTray.exe"
  Delete "$INSTDIR\favicon.ico"
  Delete "$INSTDIR\start_windows.bat"
  Delete "$INSTDIR\uninstall.exe"
  ; Attempt to remove the install dir (will fail if non-empty; that's OK)
  RMDir "$INSTDIR"
 
  ; Remove registry keys
  DeleteRegValue HKLM "Software\NeXroll" "InstallDir"
  DeleteRegValue HKLM "Software\NeXroll" "PrerollPath"
  DeleteRegValue HKLM "Software\NeXroll" "Version"
  DeleteRegValue HKLM "Software\NeXroll" "FFmpegPath"
  DeleteRegValue HKLM "Software\NeXroll" "FFprobePath"
  DeleteRegKey /ifempty HKLM "Software\NeXroll"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\NeXroll"
SectionEnd

; ------------------------------
; Init: (no hard aborts on missing Python; PyInstaller bundles runtime)
; Optional: warn if ffmpeg not found and SEC_DEPS not selected
; ------------------------------
Function .onInit
   ; Best-effort: stop running NeXroll processes so upgrade can proceed
   ; Try to stop the Windows service first (ignore errors if not installed/running)
   DetailPrint "Stopping NeXroll service and processes..."
   nsExec::ExecToStack 'sc stop "NeXrollService"' $0
   Pop $0
   Sleep 2000
   
   ; Kill all NeXroll processes multiple times to ensure they're stopped
   nsExec::ExecToStack 'taskkill /F /IM NeXroll.exe /T' $0
   Pop $0
   Sleep 500
   nsExec::ExecToStack 'taskkill /F /IM NeXrollTray.exe /T' $0
   Pop $0
   Sleep 500
   nsExec::ExecToStack 'taskkill /F /IM NeXrollService.exe /T' $0
   Pop $0
   Sleep 500
   nsExec::ExecToStack 'taskkill /F /IM setup_plex_token.exe /T' $0
   Pop $0
   Sleep 1000
   
   ; Second pass to catch any stragglers
   nsExec::ExecToStack 'taskkill /F /IM NeXroll.exe /T' $0
   Pop $0
   nsExec::ExecToStack 'taskkill /F /IM NeXrollTray.exe /T' $0
   Pop $0
   nsExec::ExecToStack 'taskkill /F /IM NeXrollService.exe /T' $0
   Pop $0
   Sleep 1500
   
   DetailPrint "Process cleanup complete."

   ; No Python checks (NeXroll.exe is self-contained)
   ; Light ffmpeg check just to inform user
   ClearErrors
   nsExec::ExecToStack 'cmd /c ffmpeg -version' $0
   Pop $0
   ; If non-zero and user didn't select dependency section, just inform (no abort)
   ${If} $0 != 0
     ; Do nothing here; the "Install Dependencies" component is available on the Components page
   ${EndIf}
FunctionEnd

; ------------------------------
; Post-install message (simplified)
; ------------------------------
Function .onInstSuccess
   ; Launch NeXrollTray.exe after installation (best-effort)
   Exec '"$INSTDIR\NeXrollTray.exe"'

   ; Show a simple informational message to avoid complex quoting/escaping issues
   MessageBox MB_ICONINFORMATION|MB_OK "Installation complete. You can launch NeXroll from the Start Menu or the system tray. If you installed the service, check Services or the ProgramData\\NeXroll\\logs\\service.log for details."
FunctionEnd

