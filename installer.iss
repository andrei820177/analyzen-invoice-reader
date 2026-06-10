; Analyzen Invoice Reader — Inno Setup Script
; Requires: Inno Setup 6.x (https://jrsoftware.org/isinfo.php)
; Build: Run tools\build_installer.py first to produce dist\AnalyzenInvoiceReader\

#define AppName      "Analyzen Invoice Reader"
#define AppVersion   "1.0.0"
#define AppPublisher "Analyzen"
#define AppExeName   "AnalyzenInvoiceReader.exe"
#define AppURL       "https://analyzen.ro"
#define DistDir      "dist\AnalyzenInvoiceReader"
#define TessDir      "tools\tesseract"

[Setup]
AppId={{A7B3C2D1-4E5F-6A7B-8C9D-0E1F2A3B4C5D}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\Analyzen\Invoice Reader
DefaultGroupName=Analyzen
AllowNoIcons=yes
LicenseFile=LICENSE.txt
OutputDir=installer_output
OutputBaseFilename=AnalyzenInvoiceReader_Setup_v{#AppVersion}
SetupIconFile=
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardResizable=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableProgramGroupPage=yes
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}

[Languages]
Name: "romanian"; MessagesFile: "compiler:Languages\Romanian.isl"
Name: "english";  MessagesFile: "compiler:Default.isl"
Name: "german";   MessagesFile: "compiler:Languages\German.isl"
Name: "french";   MessagesFile: "compiler:Languages\French.isl"
Name: "italian";  MessagesFile: "compiler:Languages\Italian.isl"
Name: "spanish";  MessagesFile: "compiler:Languages\Spanish.isl"
Name: "dutch";    MessagesFile: "compiler:Languages\Dutch.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Components]
Name: "main";     Description: "Analyzen Invoice Reader";         Types: full compact custom; Flags: fixed
Name: "tesseract"; Description: "Tesseract OCR (factturi scanate)"; Types: full custom

[Files]
; Main application — all PyInstaller output
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: main

; Bundled Tesseract binaries + ron+eng packs (minimal)
Source: "{#TessDir}\*"; DestDir: "{app}\tesseract"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: tesseract; Check: TesseractDirExists

[Icons]
Name: "{group}\{#AppName}";            Filename: "{app}\{#AppExeName}"
Name: "{group}\Dezinstalare";          Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}";    Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Lansează {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
function TesseractDirExists: Boolean;
begin
  Result := DirExists(ExpandConstant('{src}\{#TessDir}'));
end;

procedure InitializeWizard;
begin
  WizardForm.WizardSmallBitmapImage.Visible := False;
end;
