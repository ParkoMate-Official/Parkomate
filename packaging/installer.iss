; Inno Setup script - makes dist\ParkomateStation-Setup-<version>.exe from the PyInstaller folder.
;
;   packaging\build.ps1            (builds everything; needs Inno Setup 6.3+ for this step)
;   ISCC /DAppVersion=0.1.0 packaging\installer.iss
;
; What the Setup does on each PC:
;   * installs the program to C:\Program Files\Parkomate Station
;   * creates C:\ProgramData\Parkomate (database, settings, reports, logs) - every Windows user
;     of the PC may write there; it is KEPT on uninstall and on updates
;   * asks for this PC's station name and the measuring device address (first install only)
;     and writes them to settings.toml
;   * opens TCP port 8765 in the Windows firewall for the measuring device (Wi-Fi / LAN)
;   * Start-menu shortcuts: the station, "Check this PC", and (optional) demo shortcuts
;   * at the end: create the first administrator, check the PC, start the station

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#define AppName "Parkomate Station"
#define AppExe "ParkomateStation.exe"
#define CliExe "parkomate.exe"
#define FirewallRule "Parkomate Station measuring device"

[Setup]
AppId={{6B0F3C1E-8D2A-4F7B-9C55-2E7A1D4B9F30}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Parkomate
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=ParkomateStation-Setup-{#AppVersion}
SetupIconFile=parkomate.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
SetupLogging=yes

[Tasks]
Name: "desktopicon"; Description: "Desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "demoicons"; Description: "Demo shortcuts (simulated bench, Wi-Fi measuring device simulator)"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Dirs]
Name: "{commonappdata}\Parkomate"; Permissions: users-modify

[Files]
Source: "..\dist\ParkomateStation\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\config\settings.example.toml"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\DEMO_GUIDE.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "..\docs\ADMIN_GUIDE.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "..\docs\OPERATOR_GUIDE.md"; DestDir: "{app}\docs"; Flags: ignoreversion
#ifexist "redist\vcredist_x64.exe"
; Optional: the Microsoft Visual C++ 2013 runtime (x64) that the ZBar QR decoder needs. Put the
; official vcredist_x64.exe (2013) in packaging\redist\ before building. Without it the station
; uses the OpenCV QR decoder (parkomate doctor shows a WARN).
Source: "redist\vcredist_x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
#endif

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{autoprograms}\{#AppName} - check this PC"; Filename: "{cmd}"; Parameters: "/k ""{app}\{#CliExe}"" doctor"; IconFilename: "{app}\{#AppExe}"
Name: "{autoprograms}\{#AppName} - DEMO (simulated bench)"; Filename: "{app}\{#AppExe}"; Parameters: "--mock"; Tasks: demoicons
Name: "{autoprograms}\{#AppName} - DEMO with Wi-Fi measuring device"; Filename: "{app}\{#AppExe}"; Parameters: "--mock --real-measuring-device"; Tasks: demoicons
Name: "{autoprograms}\Measuring device simulator"; Filename: "{cmd}"; Parameters: "/k ""{app}\{#CliExe}"" measuring-device"; IconFilename: "{app}\{#AppExe}"; Tasks: demoicons

[Run]
#ifexist "redist\vcredist_x64.exe"
Filename: "{tmp}\vcredist_x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Installing the Visual C++ 2013 runtime (QR decoder)..."; Flags: waituntilterminated
#endif
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#FirewallRule}"""; Flags: runhidden; StatusMsg: "Opening the firewall for the measuring device..."
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""{#FirewallRule}"" dir=in action=allow protocol=TCP localport=8765 program=""{app}\{#AppExe}"" profile=any"; Flags: runhidden
Filename: "{cmd}"; Parameters: "/k ""{app}\{#CliExe}"" admin create"; Description: "Create the first administrator now (only on a new PC)"; Flags: postinstall skipifsilent runasoriginaluser
Filename: "{cmd}"; Parameters: "/k ""{app}\{#CliExe}"" doctor"; Description: "Check this PC (doctor)"; Flags: postinstall skipifsilent runasoriginaluser unchecked
Filename: "{app}\{#AppExe}"; Description: "Start {#AppName}"; Flags: postinstall skipifsilent nowait runasoriginaluser unchecked

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#FirewallRule}"""; Flags: runhidden; RunOnceId: "FirewallRule"

[Code]
var
  StationPage: TInputQueryWizardPage;

function SettingsFile(): String;
begin
  Result := ExpandConstant('{commonappdata}\Parkomate\settings.toml');
end;

procedure InitializeWizard();
begin
  StationPage := CreateInputQueryPage(wpSelectTasks,
    'This station',
    'Give this PC its own name and tell it where the measuring device is.',
    'Every PC running Parkomate Station needs a different station name: it is printed on ' +
    'the reports and e-mails. Use letters, digits, "-" or "_" (at most 32).' + #13#10 + #13#10 +
    'The measuring device sends its data over Wi-Fi / LAN. Enter its fixed IP address, or the ' +
    'whole network when the router gives it changing addresses (e.g. 192.168.1.0/24). ' +
    'An administrator can change both later in Admin > Settings.');
  StationPage.Add('Station name (e.g. STATION-02):', False);
  StationPage.Add('Measuring device IP address or network:', False);
  StationPage.Values[0] := 'STATION-01';
  StationPage.Values[1] := '192.168.4.2';
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  { an update keeps the existing settings }
  Result := (PageID = StationPage.ID) and FileExists(SettingsFile());
end;

function OnlyChars(const S, Allowed: String): Boolean;
var
  I: Integer;
begin
  Result := Length(S) > 0;
  for I := 1 to Length(S) do
    if Pos(S[I], Allowed) = 0 then
    begin
      Result := False;
      Exit;
    end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = StationPage.ID then
  begin
    StationPage.Values[0] := Trim(StationPage.Values[0]);
    StationPage.Values[1] := Trim(StationPage.Values[1]);
    if (Length(StationPage.Values[0]) > 32) or not OnlyChars(StationPage.Values[0],
      'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_') then
    begin
      MsgBox('The station name may only use letters, digits, "-" and "_" (1 to 32 characters).',
        mbError, MB_OK);
      Result := False;
    end
    else if not OnlyChars(StationPage.Values[1], '0123456789./') then
    begin
      MsgBox('Enter an IP address like 192.168.1.50 or a network like 192.168.1.0/24.',
        mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Text: String;
begin
  if (CurStep = ssPostInstall) and not FileExists(SettingsFile()) then
  begin
    Text :=
      '# Written by the installer. Every other key keeps its default - see' + #13#10 +
      '# settings.example.toml in the program folder. Admins can change all of it in the app.' + #13#10 + #13#10 +
      '[station]' + #13#10 +
      'station_id = "' + StationPage.Values[0] + '"' + #13#10 + #13#10 +
      '[measurement]' + #13#10 +
      'allowed_ip = "' + StationPage.Values[1] + '"' + #13#10;
    if not SaveStringToFile(SettingsFile(), Text, False) then
      MsgBox('Could not write ' + SettingsFile() + '. Set the station name in Admin > Settings.',
        mbError, MB_OK);
  end;
end;
