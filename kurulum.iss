; Misafirhane Rezervasyon - Kurulum betigi
; Kaynak: dist\Misafirhane (PyInstaller onedir) , Cikti: dist\kurulum\Misafirhane_Kurulum.exe

; iscc /DMyAppVersion=1.0.1 ile sürüm geçilebilir, verilmezse varsayılan kullanılır.
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

[Setup]
AppId={{7F3A1B9E-4C62-4D8A-9E2B-MISAFIRHANE0001}
AppName=Misafirhane Rezervasyon
AppVersion={#MyAppVersion}
AppPublisher=DorDeorz
AppVerName=Misafirhane Rezervasyon {#MyAppVersion}
DefaultDirName={autopf}\Misafirhane Rezervasyon
DefaultGroupName=Misafirhane
DisableProgramGroupPage=yes
OutputDir=dist\kurulum
OutputBaseFilename=Misafirhane_Kurulum
SetupIconFile=assets\misafirhane.ico
UninstallDisplayIcon={app}\Misafirhane.exe
UninstallDisplayName=Misafirhane Rezervasyon
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=no
RestartApplications=no

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "dist\Misafirhane\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "assets\misafirhane.ico"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "surum.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Misafirhane Rezervasyon"; Filename: "{app}\Misafirhane.exe"; WorkingDir: "{app}"
Name: "{group}\Kaldır"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Misafirhane Rezervasyon"; Filename: "{app}\Misafirhane.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\Misafirhane.exe"; Description: "Uygulamayı şimdi çalıştır"; Flags: nowait postinstall skipifsilent

; NOT: Kullanici verileri (misafirhane.db ve yedekler) %LOCALAPPDATA%\Misafirhane
; klasorunde tutulur. Kaldirma sırasında veriler KORUNUR.