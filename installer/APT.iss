; -------------------------------------------------------------------------
; AIVEX Processing Tool — Inno Setup installer
;
; Build:
;     cd installer
;     .\build.ps1
;
; …which invokes:
;     iscc /DMyAppVersion=<x.y.z> APT.iss
;
; Inno Setup (iscc.exe) is required on PATH or at the default install
; location (C:\Program Files (x86)\Inno Setup 6\). Download free at
; https://jrsoftware.org/isdl.php
;
; Output:
;     installer\Output\APT_Setup_v<version>.exe   (single self-contained
;                                                  installer EXE)
; -------------------------------------------------------------------------

; If iscc is run without /DMyAppVersion, fall back to this default. The
; build.ps1 script will always inject the real version parsed from
; apt/brand.py.
#ifndef MyAppVersion
  #define MyAppVersion "2.0.0"
#endif

#define MyAppName        "AIVEX Processing Tool"
#define MyAppShort       "APT"
#define MyAppPublisher   "AIVEX"
#define MyAppURL         "https://github.com/CVKim/AiV_ProcessingTool"
#define MyAppExeName     "APT.exe"
#define MimExeName       "mim2color.exe"
#define MimIniName       "mim_converter_config.ini"
#define ProjectRoot      "..\"

[Setup]
; Stable AppId so future installers upgrade in place (UNIQUE per app —
; never reuse this GUID for a different product).
AppId={{8B5A7F2D-9C4E-4A6B-A1F0-7E2D3C5B9F1A}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
DefaultDirName={autopf}\AIVEX\{#MyAppShort}
DefaultGroupName=AIVEX\{#MyAppShort}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=APT_Setup_v{#MyAppVersion}
SetupIconFile={#ProjectRoot}AiV_LOGO.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

; File properties of the setup.exe itself
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoDescription={#MyAppName} Installer

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
; Korean is bundled with Inno Setup 6 by default.
Name: "korean";  MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; \
    Description: "{cm:CreateDesktopIcon}"; \
    GroupDescription: "{cm:AdditionalIcons}"; \
    Flags: unchecked

[Files]
; ---- The four mandatory artefacts (this is the "set" of 4) -----------
;
; 1) APT.exe — main executable produced by PyInstaller
Source: "{#ProjectRoot}dist\APT\APT.exe"; \
    DestDir: "{app}"; \
    Flags: ignoreversion
;
; 2) _internal/ — Python runtime + Qt DLLs + bundled resources/samples
Source: "{#ProjectRoot}dist\APT\_internal\*"; \
    DestDir: "{app}\_internal"; \
    Flags: ignoreversion recursesubdirs createallsubdirs
;
; 3) mim2color.exe — external converter, sibling of APT.exe so the
;    MIM to BMP panel finds it via sys.argv[0] directory
Source: "{#ProjectRoot}mim2color.exe"; \
    DestDir: "{app}"; \
    Flags: ignoreversion
;
; 4) mim_converter_config.ini — default INI template (user can edit
;    after install or pick a different one from the MIM to BMP panel)
Source: "{#ProjectRoot}mim_converter_config.ini"; \
    DestDir: "{app}"; \
    Flags: ignoreversion onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; \
    Filename: "{app}\{#MyAppExeName}"; \
    Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; \
    Description: "{cm:LaunchProgram,{#MyAppName}}"; \
    Flags: nowait postinstall skipifsilent

; Leave any user-edited INI / error.log in place when uninstalling.
[UninstallDelete]
Type: files; Name: "{app}\error.log"
