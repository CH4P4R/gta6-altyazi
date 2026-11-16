; GTA6 Altyazı kurulum sihirbazı (Inno Setup 6)
; iscc /DAppVersion=0.2.0 packaging\installer.iss

#ifndef AppVersion
  #define AppVersion "0.2.0"
#endif

[Setup]
AppId={{6B6F1E5A-3C2D-4F8E-9A71-6A0C7D2B9E41}
AppName=GTA6 Altyazı
AppVersion={#AppVersion}
AppVerName=GTA6 Altyazı {#AppVersion}
AppPublisher=GTA6 Altyazı
DefaultDirName={localappdata}\Programs\GTA6Altyazi
DefaultGroupName=GTA6 Altyazı
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=GTA6Altyazi-Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\GTA6Altyazi.exe
UninstallDisplayName=GTA6 Altyazı
WizardStyle=modern
WizardSizePercent=110
WizardImageFile=assets\wizard_large_1x.bmp,assets\wizard_large_2x.bmp
WizardSmallImageFile=assets\wizard_small_1x.bmp,assets\wizard_small_2x.bmp
Compression=lzma2/max
SolidCompression=no
LZMANumBlockThreads=4
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "tr"; MessagesFile: "compiler:Languages\Turkish.isl"

[Messages]
tr.WelcomeLabel1=GTA6 Altyazı'ya hoş geldin
tr.WelcomeLabel2=Oyundaki İngilizce yazılar anında Türkçe olarak İngilizcenin yerine yazılır: altyazılar, yardım kutuları, bildirimler. TV'de ve Discord yayınında da görünür.%n%nKurulum bir dakika sürer. İlk açılışta kısa bir sihirbaz PS5, TV ve çeviri ayarlarını birlikte yapacak.
tr.FinishedHeadingLabel=Kurulum tamam!
tr.FinishedLabel=GTA6 Altyazı kuruldu. Açınca kurulum sihirbazı seni karşılayacak.

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne kısayol koy"; GroupDescription: "Kısayollar:"

[Files]
Source: "..\dist\GTA6Altyazi\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\GTA6 Altyazı"; Filename: "{app}\GTA6Altyazi.exe"
Name: "{userdesktop}\GTA6 Altyazı"; Filename: "{app}\GTA6Altyazi.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\GTA6Altyazi.exe"; Description: "GTA6 Altyazı'yı şimdi aç"; Flags: nowait postinstall skipifsilent
