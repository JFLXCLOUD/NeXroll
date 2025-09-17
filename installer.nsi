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
OutFile "NeXroll_Installer.exe"
InstallDir "$PROGRAMFILES64\NeXroll"
RequestExecutionLevel admin
ShowInstDetails show
Icon "frontend\favicon.ico"
UninstallIcon "frontend\favicon.ico"

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
  
  ; Default path
  StrCpy $PREROLL_PATH "$DOCUMENTS\NeXroll\Prerolls"
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
  StrCmp $0 "error" +2 0
  Return
  StrCmp $0 "" +2 0
  Return
  ; Update variable and textbox
  StrCpy $PREROLL_PATH "$0"
  ${NSD_SetText} $hPrerollEdit "$PREROLL_PATH"
FunctionEnd

Function PrerollPathPageLeave
  ${NSD_GetText} $hPrerollEdit $PREROLL_PATH
  StrCmp $PREROLL_PATH "" 0 +2
  StrCpy $PREROLL_PATH "$DOCUMENTS\NeXroll\Prerolls"
FunctionEnd

; ------------------------------
; Components
; ------------------------------
Section "!NeXroll Application (Required)" SEC_APP
  SectionIn RO
  SetOutPath "$INSTDIR"
  SetOverwrite on

  ; Runtime files only (built by PyInstaller)
  ; Expected locations relative to this .nsi when makensis runs:
  ;   dist\NeXroll\NeXroll.exe
  ;   dist\NeXrollService\NeXrollService.exe
  ;   dist\setup_plex_token\setup_plex_token.exe
  ;   start_windows.bat (helper launcher - optional)
  ;
  ; If paths differ in your build pipeline, adjust these File lines accordingly.

  ; Main app (onefile output goes directly under dist\)
  File /oname=NeXroll.exe "..\dist\NeXroll.exe"
  ; Windows service wrapper (onefile output)
  File /oname=NeXrollService.exe "..\dist\NeXrollService.exe"
  ; Token setup tool (onefile output)
  File /oname=setup_plex_token.exe "..\dist\setup_plex_token.exe"
  ; Tray app executable (onefile output)
  File /oname=NeXrollTray.exe "..\dist\NeXrollTray.exe"
  ; Include favicon in install dir (optional reference)
  File /oname=favicon.ico "frontend\favicon.ico"
  ; Convenience start script
  File "start_windows.bat"

  ; Create preroll directory
  CreateDirectory "$PREROLL_PATH"

  ; Persist config to registry
  WriteRegStr HKLM "Software\NeXroll" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "Software\NeXroll" "PrerollPath" "$PREROLL_PATH"

  ; Start Menu shortcuts
  CreateDirectory "$SMPROGRAMS\NeXroll"
  CreateShortCut "$SMPROGRAMS\NeXroll\NeXroll.lnk" "$INSTDIR\NeXroll.exe" "" "$INSTDIR\NeXroll.exe" 0
  CreateShortCut "$SMPROGRAMS\NeXroll\NeXroll Tray.lnk" "$INSTDIR\NeXrollTray.exe" "" "$INSTDIR\NeXrollTray.exe" 0
  CreateShortCut "$SMPROGRAMS\NeXroll\Uninstall.lnk" "$INSTDIR\uninstall.exe" "" "$INSTDIR\uninstall.exe" 0

  ; Desktop shortcut
  CreateShortCut "$DESKTOP\NeXroll.lnk" "$INSTDIR\NeXroll.exe" "" "$INSTDIR\NeXroll.exe" 0

  ; Uninstaller
  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section "Install as Windows Service" SEC_SERVICE
  SetOutPath "$INSTDIR"
  ; Install and start service using the service wrapper
  ExecWait '"$INSTDIR\NeXrollService.exe" install' $0
  ; ignore non-zero codes and attempt start
  ExecWait '"$INSTDIR\NeXrollService.exe" start' $0
SectionEnd

Section "Plex Stable Token Setup (Run Now)" SEC_TOKEN
  SetOutPath "$INSTDIR"
  ExecWait '"$INSTDIR\setup_plex_token.exe"' $0
SectionEnd

Section "Start with Windows (Startup Shortcut)" SEC_STARTUP
  ; Create shortcut in Startup folder (launches tray app so icon is visible and provides menu)
  CreateShortCut "$SMSTARTUP\NeXroll Tray.lnk" "$INSTDIR\NeXrollTray.exe" "" "$INSTDIR\NeXrollTray.exe" 0
SectionEnd

Section "Install Dependencies (FFmpeg via winget)" SEC_DEPS
  ; Install FFmpeg using winget if not present
  nsExec::ExecToStack 'powershell -NoProfile -ExecutionPolicy Bypass -Command "if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { winget install Gyan.FFmpeg --accept-source-agreements --accept-package-agreements -e }"'
  Pop $0
  ; $0 contains exit code (ignored for best-effort)
SectionEnd

; ------------------------------
; Uninstaller
; ------------------------------
Section "Uninstall"
  ; Stop and remove Windows service if installed
  IfFileExists "$INSTDIR\NeXrollService.exe" 0 +5
    ExecWait '"$INSTDIR\NeXrollService.exe" stop' $0
    ExecWait '"$INSTDIR\NeXrollService.exe" remove' $0

  ; Remove shortcuts
  Delete "$SMPROGRAMS\NeXroll\NeXroll.lnk"
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
  RMDir "$INSTDIR"

  ; Remove registry keys
  DeleteRegValue HKLM "Software\NeXroll" "InstallDir"
  DeleteRegValue HKLM "Software\NeXroll" "PrerollPath"
  DeleteRegKey /ifempty HKLM "Software\NeXroll"
SectionEnd

; ------------------------------
; Init: (no hard aborts on missing Python; PyInstaller bundles runtime)
; Optional: warn if ffmpeg not found and SEC_DEPS not selected
; ------------------------------
Function .onInit
  ; No Python checks (NeXroll.exe is self-contained)
  ; Light ffmpeg check just to inform user
  ClearErrors
  nsExec::ExecToStack 'cmd /c ffmpeg -version'
  Pop $0
  ; If non-zero and user didn't select dependency section, just inform (no abort)
  ${If} $0 != 0
    ; Do nothing here; the "Install Dependencies" component is available on the Components page
  ${EndIf}
FunctionEnd

; ------------------------------
; Post-install message
; ------------------------------
Function .onInstSuccess
  MessageBox MB_ICONINFORMATION|MB_OK "Installation complete!$\n$\n- Web interface: http://localhost:9393$\n- Preroll videos location: $PREROLL_PATH$\n- Start from Start Menu or Desktop shortcut.$\n- If installed as a service, it is running under 'NeXrollService'."
FunctionEnd