; Installer Senandung (Inno Setup 6.3+)
; Prasyarat (compile manual): jalankan dulu  install-senandung.ps1 -BuildExe  sampai Senandung.exe jadi.
; Di GitHub Actions, file ini di-compile otomatis (lihat .github/workflows/release.yml).
; Hasil: Senandung-Setup-<versi>.exe. Saat dipasang, Inno membuat unins000.exe di folder aplikasi dan
; mendaftarkan Senandung di Settings > Apps > Installed apps (tombol Uninstall).
; Bahasa wizard: Inggris + Indonesia (pengguna memilih di awal pemasangan). Inno Setup tidak membawa
; Indonesian.isl secara resmi; bila belum ada di folder Languages-nya, unduh dari
; https://jrsoftware.org/files/istrans/ lalu taruh di sana. Tanpa file itu wizard tetap jadi, hanya Inggris.
; Compile:   "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" senandung.iss
;            (atau buka file ini di Inno Setup lalu tekan Ctrl+F9)

#define AppName    "Senandung"
#define AppExe     "Senandung.exe"
#define AppUrl     "https://github.com/mazerangga/senandung-lirik"
#define BuildRoot  GetEnv("LOCALAPPDATA") + "\senandung"

; Nilai di bawah bisa ditimpa lewat variabel lingkungan (dipakai GitHub Actions).
; Bila kosong (compile manual), dipakai nilai bawaan.
#define AppVersion GetEnv("SENANDUNG_VERSION")
#if AppVersion == ""
  #undef AppVersion
  #define AppVersion "1.0"
#endif
#define ExeSrc GetEnv("SENANDUNG_EXE")
#if ExeSrc == ""
  #undef ExeSrc
  #define ExeSrc BuildRoot + "\dist\Senandung.exe"
#endif
#define IconSrc GetEnv("SENANDUNG_ICON")
#if IconSrc == ""
  #undef IconSrc
  #define IconSrc BuildRoot + "\senandung.ico"
#endif
#define OutDir GetEnv("SENANDUNG_OUT")
#if OutDir == ""
  #undef OutDir
  #define OutDir "."
#endif
#define IdIsl      AddBackslash(CompilerPath) + "Languages\Indonesian.isl"
#if FileExists(IdIsl)
  #define HaveId
#endif

[Setup]
AppId={{7F66E065-CD6C-4315-9A6E-3C0CE50FE9EC}
AppName={#AppName}
AppVersion={#AppVersion}
; tampil di Settings > Apps > Installed apps
AppPublisher=mazerangga
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; pasang per-user, tanpa admin
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile={#IconSrc}
UninstallDisplayIcon={app}\{#AppExe}
OutputDir={#OutDir}
OutputBaseFilename=Senandung-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
#ifdef HaveId
Name: "indonesian"; MessagesFile: "{#IdIsl}"
#endif

[CustomMessages]
english.TaskAutostart=Run automatically when I log in to Windows
english.TaskDesktopIcon=Create a desktop shortcut
english.RunApp=Launch %1
#ifdef HaveId
indonesian.TaskAutostart=Jalankan otomatis saat login Windows
indonesian.TaskDesktopIcon=Buat ikon di Desktop
indonesian.RunApp=Jalankan %1
#endif

[Tasks]
Name: "autostart"; Description: "{cm:TaskAutostart}"; Flags: unchecked
Name: "desktopicon"; Description: "{cm:TaskDesktopIcon}"; Flags: unchecked

[Files]
Source: "{#ExeSrc}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; nama value sama dengan yang dipakai toggle "Mulai bersama Windows" di aplikasi
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
  ValueName: "Senandung"; ValueData: """{app}\{#AppExe}"""; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:RunApp,{#AppName}}"; Flags: nowait postinstall skipifsilent
; Update dari dialog "Tentang" memanggil Setup dengan /SILENT /RELAUNCH=1: jalankan lagi aplikasinya.
Filename: "{app}\{#AppExe}"; Flags: nowait skipifnotsilent; Check: RelaunchRequested

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM {#AppExe}"; Flags: runhidden; RunOnceId: "KillSenandung"

[Code]
function RelaunchRequested: Boolean;
begin
  Result := ExpandConstant('{param:RELAUNCH|0}') = '1';
end;
