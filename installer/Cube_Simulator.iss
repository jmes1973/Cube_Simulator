#define MyAppName "Cube_Simulator"
#define MyAppVersion "1.0.1"
#define MyAppPublisher "Volutracer / OPUS"
#define MyAppExeName "Cube_Simulator.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-47A0-9C10-112233445566}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=C:\Cube_Simulator\installer\output
OutputBaseFilename=Setup_{#MyAppName}_{#MyAppVersion}
Compression=lzma
SolidCompression=yes
SetupIconFile=C:\Cube_Simulator\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "C:\Cube_Simulator\dist\Cube_Simulator\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "C:\Cube_Simulator\assets\icon.ico"; DestDir: "{app}\assets"; Flags: ignoreversion

[Tasks]
Name: "desktopicon"; Description: "Crear un icono en el escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\assets\icon.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Ejecutar {#MyAppName}"; Flags: nowait postinstall skipifsilent
