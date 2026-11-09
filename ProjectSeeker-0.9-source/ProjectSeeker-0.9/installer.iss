; Copyright (C) 2026 Gato
; SPDX-License-Identifier: GPL-3.0-only
; Licensed under the GNU General Public License v3.0; see LICENSE.
; Project Seeker - installer (Inno Setup 6, free: https://jrsoftware.org/isinfo.php)
; Used by build.bat after PyInstaller; by hand: open this file in Inno Setup and press Compile.
; Per-user install only (no admin rights, no "for me / for all users" question), with Start menu entry,
; optional desktop icon and uninstaller.
; Uninstalling does NOT delete %APPDATA%\ProjectSeeker (library, preferences, notes): it is user data.
; The version must match VERSION in app.py. The automatic build (GitHub Actions) passes it with /DAppVersion=...
#define AppName "Project Seeker"
#ifndef AppVersion
  #define AppVersion "0.9"
#endif

[Setup]
AppId={{8C1B7A52-3F0E-4E7B-9C51-2B7F3E9D4A10}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppName}
DefaultDirName={autopf}\Project Seeker
DefaultGroupName=Project Seeker
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=ProjectSeeker-setup-{#AppVersion}
SetupIconFile=icona.ico
UninstallDisplayIcon={app}\ProjectSeeker.exe
UninstallDisplayName={#AppName}
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
VersionInfoDescription={#AppName} Setup
VersionInfoCopyright=Copyright (C) 2026 Gato - GPL-3.0
LicenseFile=LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; setup language = Windows language; the language list only appears when Windows uses none of the four
ShowLanguageDialog=auto
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\ProjectSeeker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\ProjectSeeker.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\ProjectSeeker.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ProjectSeeker.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
