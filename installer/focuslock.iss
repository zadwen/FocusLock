; FocusLock v3.0.0 — Inno Setup Script
; Creates a professional Windows installer.
; Requires Inno Setup 6.x: https://jrsoftware.org/isinfo.php

#define MyAppName "FocusLock"
#define MyAppVersion "3.0.0"
#define MyAppPublisher "zadwen"
#define MyAppURL "https://github.com/zadwen/FocusLock"
#define MyAppExeName "FocusLock.exe"

; Path to the release folder produced by scripts/release.py
#define ReleaseDir "..\dist\FocusLock-3.0.0"

[Setup]
AppId={{F0CUSL0CK-3000-0000-0000-000000000000}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
LicenseFile={#ReleaseDir}\LICENSE
OutputDir=..\dist
OutputBaseFilename={#MyAppName}-{#MyAppVersion}-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\assets\icon.ico
DisableProgramGroupPage=yes
DisableReadyPage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Nuitka standalone: all files are flat in the distribution folder (no _internal/)
Source: "{#ReleaseDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseDir}\*.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseDir}\*.pyd"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseDir}\PySide6\*"; DestDir: "{app}\PySide6"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ReleaseDir}\shiboken6\*"; DestDir: "{app}\shiboken6"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ReleaseDir}\sqlalchemy\*"; DestDir: "{app}\sqlalchemy"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ReleaseDir}\psutil\*"; DestDir: "{app}\psutil"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ReleaseDir}\greenlet\*"; DestDir: "{app}\greenlet"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ReleaseDir}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseDir}\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ReleaseDir}\README.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
