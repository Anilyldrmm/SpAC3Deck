; installer.iss
; MacroDeck kurulum sihirbazi (Inno Setup). Kullanici klasorune (LocalAppData)
; kurar, yonetici izni (UAC) istemez - "S" logolu tanidik bir "Ileri > Ileri > Kur"
; akisi sunar, dosya/exe indirip elle klasore cikarma derdi kalmaz.
;
; MyAppVersion'i her release'de macrodeck/__init__.py'deki __version__ ile
; senkron tut (elle bump).
;
; Derleme (once `pyinstaller MacroDeck.spec` calistirilmis, dist\MacroDeck\
; dolu olmali):
;   "C:\Users\anil_\AppData\Local\Programs\Inno Setup 6\ISCC.exe" installer.iss
; Cikti: dist\installer\MacroDeckSetup.exe

#define MyAppName "MacroDeck"
#define MyAppVersion "1.0.5"
#define MyAppExeName "MacroDeck.exe"
#define MyAppMutex "Global\MacroDeck_SingleInstance"

[Setup]
AppId={{8011FC8D-BC02-4A51-96B0-D7D387CA9199}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=SpAC3
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=dist\installer
OutputBaseFilename=MacroDeckSetup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
AppMutex={#MyAppMutex}
CloseApplications=yes
RestartApplications=no
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaustunde kisayol olustur"; GroupDescription: "Ek kisayollar:"
Name: "autostart"; Description: "Windows acilinca otomatik baslat"; GroupDescription: "Ek kisayollar:"

[Files]
Source: "dist\MacroDeck\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{#MyAppName} Kaldir"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
    ValueName: "MacroDeck"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: autostart; \
    Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; \
    Flags: nowait postinstall skipifsilent

; Sessiz otomatik guncelleme (macrodeck/updater.py) bu installer'i kullanmiyor -
; kendi zip+robocopy mekanizmasiyla calisir, degistirilmedi. Bu installer sadece
; ilk kurulum icin (yeni kullanicinin GitHub Release'den indirdigi tek dosya).
