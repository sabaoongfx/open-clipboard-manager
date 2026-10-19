; Inno Setup script for the Windows installer. Built by .github/workflows/release.yml:
;   ISCC /DAppVersion=<version> /DAppVersion4=<version>.0 installer\open-clipboard-manager.iss
; It installs the PyInstaller one-folder build (dist\Open-Clipboard-Manager\), which starts faster than
; the single-file exe because nothing has to be unpacked first.
#define AppName "Open Clipboard Manager"
#define AppExe "Open-Clipboard-Manager.exe"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
; Windows file versions have four numbers (passed in by the build: /DAppVersion4=<version>.0).
#ifndef AppVersion4
  #define AppVersion4 "0.0.0.0"
#endif

[Setup]
AppId={{8F3C2A74-5B1D-4E6A-9C0B-2D7E41A93F58}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=sabaoongfx
AppCopyright=Copyright (c) 2026 sabaoongfx. MIT License.
AppPublisherURL=https://github.com/sabaoongfx/open-clipboard-manager
AppSupportURL=https://github.com/sabaoongfx/open-clipboard-manager/issues
AppUpdatesURL=https://github.com/sabaoongfx/open-clipboard-manager/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Per-user install by default (no administrator prompt); the dialog lets people choose "for all users".
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=Open-Clipboard-Manager-x64-setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; File properties (Details tab) of the installer. Code-signing services require the product name and version.
VersionInfoVersion={#AppVersion4}
VersionInfoProductVersion={#AppVersion4}
VersionInfoProductName={#AppName}
VersionInfoCompany=sabaoongfx
VersionInfoDescription={#AppName} setup
VersionInfoCopyright=Copyright (c) 2026 sabaoongfx. MIT License.
; Close a running copy during an upgrade or uninstall, and start it again afterwards.
CloseApplications=yes
RestartApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\Open-Clipboard-Manager\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
