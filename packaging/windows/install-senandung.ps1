<#
Senandung installer for Windows - single file, installs to %LOCALAPPDATA%\senandung (no admin needed).

  powershell -ExecutionPolicy Bypass -File install-senandung.ps1                  install
  powershell -ExecutionPolicy Bypass -File install-senandung.ps1 -Autostart       + run at login
  powershell -ExecutionPolicy Bypass -File install-senandung.ps1 -BuildExe        + build Senandung.exe (PyInstaller)
  powershell -ExecutionPolicy Bypass -File install-senandung.ps1 -Uninstall [-Purge]
  powershell -ExecutionPolicy Bypass -File install-senandung.ps1 -Lang id         installer language: id | en | auto (default)

Requires: Python 3.10+ (64-bit) from python.org or "winget install Python.Python.3.12".
Players that are read: anything shown in the Windows media controls (Spotify, browsers, etc.) and AIMP.
Installer language: -Lang id|en; "auto" (default) follows the Windows display language.
#>
param(
  [switch]$Uninstall, [switch]$Purge, [switch]$Autostart, [switch]$BuildExe,
  [ValidateSet("auto", "id", "en")][string]$Lang = "auto"
)
$ErrorActionPreference = "Stop"
$App = "senandung"; $Version = "1.0"
$Prefix = Join-Path $env:LOCALAPPDATA $App
$Venv   = Join-Path $Prefix "venv"
$Py     = Join-Path $Venv "Scripts\python.exe"
$Pyw    = Join-Path $Venv "Scripts\pythonw.exe"
$Script = Join-Path $Prefix "senandung.py"
$Ico    = Join-Path $Prefix "senandung.ico"
$ExeDir = Join-Path $Prefix "dist\Senandung"
$Exe    = Join-Path $ExeDir "Senandung.exe"
$Lnk    = Join-Path ([Environment]::GetFolderPath("Programs")) "Senandung.lnk"
$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$UnKey  = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Senandung"   # daftar Settings > Apps
$UnPs1  = Join-Path $Prefix "uninstall.ps1"
$Pkgs   = @("PySide6-Essentials", "pykakasi", "pypinyin", "korean-romanizer", "unidecode",
            "winrt-runtime", "winrt-Windows.Media.Control", "winrt-Windows.Foundation",
            "winrt-Windows.Foundation.Collections", "winrt-Windows.Storage.Streams")

function Say($m)  { Write-Host "==> $m" -ForegroundColor Green }
function Warn($m) { Write-Host "!!  $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "XX  $m" -ForegroundColor Red; exit 1 }

# --- messages / pesan (ASCII only, so it also works on Windows PowerShell 5.1) ---
$UI = if ($Lang -ne "auto") { $Lang } elseif ($PSUICulture -like "id*") { "id" } else { "en" }
$Msg = @{
  id = @{
    removing = "Menghapus Senandung"
    purged = "Pengaturan ikut dihapus"
    uninstalled = "Selesai. Folder lirik (~\lyrics) tidak dihapus."
    installing = "Memasang Senandung {0}"
    no_python = "Python 3.10+ tidak ditemukan. Pasang dari python.org atau: winget install Python.Python.3.12"
    no_script = "senandung.py tidak ada di arsip installer."
    make_venv = "Membuat lingkungan Python di {0}"
    venv_failed = "Gagal membuat venv."
    dl_mods = "Mengunduh modul (PySide6-Essentials dll.; mohon tunggu)"
    pip_failed = "pip gagal. Periksa internet; PySide6 butuh Python 3.10-3.13 (64-bit)."
    import_failed = "Modul terpasang tetapi tidak bisa diimpor."
    build_exe = "Membuat Senandung.exe dengan PyInstaller (beberapa menit)"
    trimming = "Memangkas file yang tidak diperlukan"
    exe_size = "Ukuran folder exe: {0} MB"
    exe_failed = "Build .exe gagal; memakai mode Python biasa (tetap berfungsi penuh)."
    autostart_on = "Autostart aktif"
    done = "Selesai! Senandung {0} terpasang."
    run_hint = "  Jalankan  : cari 'Senandung' di Start Menu"
    preview_lbl = "  Pratinjau : "
    close_hint = "  Close     : tombol close menyembunyikan ke system tray; muncul lagi saat lagu berganti"
    uninstall_lbl = "  Hapus     : "
    log_lbl = "  Log       : "
    locked = "Folder belum bisa dihapus (masih dipakai). Tutup Senandung lalu jalankan uninstall lagi."
    apps_entry = "Terdaftar di Settings > Apps (bisa di-uninstall dari sana)"
    apps_failed = "Gagal mendaftar ke daftar Apps: {0}"
    no_selfcopy = "Skrip dijalankan tanpa berkas (mis. lewat iex), jadi uninstaller tidak bisa disimpan."
  }
  en = @{
    removing = "Removing Senandung"
    purged = "Settings were removed too"
    uninstalled = "Done. The lyrics folder (~\lyrics) was kept."
    installing = "Installing Senandung {0}"
    no_python = "Python 3.10+ not found. Install it from python.org or: winget install Python.Python.3.12"
    no_script = "senandung.py is missing from the installer archive."
    make_venv = "Creating Python environment in {0}"
    venv_failed = "Could not create the venv."
    dl_mods = "Downloading modules (PySide6-Essentials etc.; please wait)"
    pip_failed = "pip failed. Check your internet connection; PySide6 needs Python 3.10-3.13 (64-bit)."
    import_failed = "The modules installed but cannot be imported."
    build_exe = "Building Senandung.exe with PyInstaller (a few minutes)"
    trimming = "Trimming files that are not needed"
    exe_size = "Exe folder size: {0} MB"
    exe_failed = "The .exe build failed; using the regular Python mode (fully functional)."
    autostart_on = "Autostart enabled"
    done = "Done! Senandung {0} is installed."
    run_hint = "  Run       : find 'Senandung' in the Start Menu"
    preview_lbl = "  Preview   : "
    close_hint = "  Close     : the close button hides to the system tray; it reappears when the song changes"
    uninstall_lbl = "  Uninstall : "
    log_lbl = "  Log       : "
    locked = "The folder could not be removed (still in use). Close Senandung and run uninstall again."
    apps_entry = "Registered in Settings > Apps (you can uninstall from there)"
    apps_failed = "Could not register in the Apps list: {0}"
    no_selfcopy = "The script ran without a file (e.g. via iex), so the uninstaller could not be saved."
  }
}
function T($key) {
  $s = $Msg[$UI][$key]
  if ($args.Count -gt 0) { $s = $s -f $args }
  return $s
}

function Stop-Running {
  Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*senandung.py*" -or $_.ExecutablePath -like "*\senandung\dist\Senandung\Senandung.exe" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

function Find-Python {
  $cands = @( @{ exe = "py"; pre = @("-3") }, @{ exe = "python"; pre = @() } )
  foreach ($c in $cands) {
    if (-not (Get-Command $c.exe -ErrorAction SilentlyContinue)) { continue }
    try {
      & $c.exe @($c.pre) -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>$null
      if ($LASTEXITCODE -eq 0) { return $c }
    } catch {}
  }
  return $null
}

function Remove-Prefix {
  # Coba beberapa kali: setelah proses dihentikan, Windows kadang butuh jeda untuk melepas kunci file.
  for ($i = 0; $i -lt 8; $i++) {
    if (-not (Test-Path -LiteralPath $Prefix)) { return $true }
    Remove-Item -LiteralPath $Prefix -Recurse -Force -ErrorAction SilentlyContinue
    if (-not (Test-Path -LiteralPath $Prefix)) { return $true }
    Start-Sleep -Milliseconds 700
  }
  return (-not (Test-Path -LiteralPath $Prefix))
}

function Do-Uninstall {
  # Bila dijalankan dari dalam folder pemasangan (uninstall.ps1), salin dulu ke TEMP dan jalankan dari sana
  # supaya folder pemasangan bisa dihapus utuh.
  $self = $PSCommandPath
  if ($self -and -not $env:SENANDUNG_RELAUNCHED -and $self.StartsWith($Prefix + "\", [StringComparison]::OrdinalIgnoreCase)) {
    $tmp = Join-Path $env:TEMP "senandung-uninstall.ps1"
    Copy-Item -LiteralPath $self -Destination $tmp -Force
    $env:SENANDUNG_RELAUNCHED = "1"
    $a = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $tmp, "-Uninstall", "-Lang", $UI)
    if ($Purge) { $a += "-Purge" }
    & powershell.exe @a
    exit $LASTEXITCODE
  }

  Say (T removing)
  Stop-Running
  Start-Sleep -Milliseconds 800
  if (-not (Remove-Prefix)) { Warn (T locked); exit 1 }
  Remove-Item -Force $Lnk -ErrorAction SilentlyContinue
  Remove-ItemProperty -Path $RunKey -Name "Senandung" -ErrorAction SilentlyContinue
  Remove-Item -Path $UnKey -Recurse -Force -ErrorAction SilentlyContinue
  if ($Purge) {
    Remove-Item -Recurse -Force "HKCU:\Software\$App" -ErrorAction SilentlyContinue
    Say (T purged)
  }
  Say (T uninstalled)
  if ($env:SENANDUNG_RELAUNCHED) {
    Start-Sleep -Seconds 3          # beri waktu membaca pesan bila jendela dibuka dari daftar Apps
    Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
  }
}

function Register-Uninstaller {
  # Simpan salinan installer ini sebagai uninstall.ps1 lalu daftarkan ke Settings > Apps.
  $src = $PSCommandPath
  if (-not $src -or -not (Test-Path -LiteralPath $src)) { Warn (T no_selfcopy); return }
  if ($src -ne $UnPs1) { Copy-Item -LiteralPath $src -Destination $UnPs1 -Force }
  $cmd = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$UnPs1`" -Uninstall -Lang $UI"
  $kb = [int][math]::Round(((Get-ChildItem -LiteralPath $Prefix -Recurse -File -ErrorAction SilentlyContinue |
                             Measure-Object Length -Sum).Sum) / 1KB)
  New-Item -Path $UnKey -Force | Out-Null
  $vals = [ordered]@{
    DisplayName = "Senandung"; DisplayVersion = $Version; Publisher = "mazerangga"
    DisplayIcon = $Ico; InstallLocation = $Prefix
    UninstallString = $cmd; QuietUninstallString = $cmd
    URLInfoAbout = "https://github.com/mazerangga/senandung-lirik"
  }
  foreach ($k in $vals.Keys) {
    New-ItemProperty -Path $UnKey -Name $k -Value $vals[$k] -PropertyType String -Force | Out-Null
  }
  foreach ($k in "NoModify", "NoRepair") {
    New-ItemProperty -Path $UnKey -Name $k -Value 1 -PropertyType DWord -Force | Out-Null
  }
  New-ItemProperty -Path $UnKey -Name "EstimatedSize" -Value $kb -PropertyType DWord -Force | Out-Null
  Say (T apps_entry)
}

function Do-Install {
  Say (T installing $Version)
  $sysPy = Find-Python
  if (-not $sysPy) { Die (T no_python) }

  Stop-Running
  New-Item -ItemType Directory -Force -Path $Prefix | Out-Null
  $bytes = [Convert]::FromBase64String(($script:Payload -replace "\s", ""))
  $zip = Join-Path $env:TEMP "senandung-payload.zip"
  [IO.File]::WriteAllBytes($zip, $bytes)
  if (Test-Path (Join-Path $Prefix "assets")) { Remove-Item -Recurse -Force (Join-Path $Prefix "assets") }
  Expand-Archive -LiteralPath $zip -DestinationPath $Prefix -Force
  Remove-Item -Force $zip -ErrorAction SilentlyContinue
  if (-not (Test-Path $Script)) { Die (T no_script) }

  Say (T make_venv $Venv)
  if (Test-Path $Venv) { Remove-Item -Recurse -Force $Venv }
  & $sysPy.exe @($sysPy.pre) -m venv $Venv
  if ($LASTEXITCODE -ne 0) { Die (T venv_failed) }

  Say (T dl_mods)
  & $Py -m pip install --disable-pip-version-check -q @Pkgs
  if ($LASTEXITCODE -ne 0) { Die (T pip_failed) }
  & $Py -c "import PySide6.QtWidgets, pykakasi, pypinyin, korean_romanizer, unidecode; from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager"
  if ($LASTEXITCODE -ne 0) { Die (T import_failed) }

  & $Py $Script --make-icon $Ico

  $target = $Pyw; $args2 = "`"$Script`""
  if ($BuildExe) {
    Say (T build_exe)
    & $Py -m pip install --disable-pip-version-check -q pyinstaller
    $pi = @("--noconfirm", "--clean", "--windowed", "--name", "Senandung", "--icon", $Ico,
            "--collect-data", "pykakasi", "--collect-submodules", "unidecode",
            "--hidden-import", "pypinyin", "--hidden-import", "korean_romanizer.romanizer",
            "--exclude-module", "PySide6.QtQml", "--exclude-module", "PySide6.QtQuick",
            "--exclude-module", "PySide6.QtQuickWidgets", "--exclude-module", "PySide6.QtWebEngineCore",
            "--exclude-module", "PySide6.QtWebEngineWidgets", "--exclude-module", "PySide6.QtWebChannel",
            "--exclude-module", "PySide6.Qt3DCore", "--exclude-module", "PySide6.QtMultimedia",
            "--exclude-module", "PySide6.QtPdf", "--exclude-module", "PySide6.QtCharts",
            "--exclude-module", "PySide6.QtSql", "--exclude-module", "PySide6.QtOpenGL",
            "--exclude-module", "PySide6.QtSvg", "--exclude-module", "PySide6.QtDesigner",
            "--exclude-module", "PySide6.QtTest", "--exclude-module", "PySide6.QtHelp",
            "--exclude-module", "tkinter",
            "--collect-all", "winrt.windows.media.control", "--collect-all", "winrt.windows.foundation",
            "--collect-all", "winrt.windows.foundation.collections", "--collect-all", "winrt.windows.storage.streams",
            "--add-data", ((Join-Path $Prefix "assets") + ";assets"),
            "--distpath", (Join-Path $Prefix "dist"), "--workpath", (Join-Path $Prefix "build"),
            "--specpath", (Join-Path $Prefix "build"), $Script)
    & $Py -m PyInstaller @pi
    if ($LASTEXITCODE -eq 0 -and (Test-Path $Exe)) {
      $target = $Exe; $args2 = ""
      Say (T trimming)
      Get-ChildItem -Path $ExeDir -Recurse -Force -ErrorAction SilentlyContinue |
        Where-Object { (-not $_.PSIsContainer -and $_.Name -ieq "opengl32sw.dll") -or
                       ($_.PSIsContainer -and $_.Name -ieq "translations") } |
        ForEach-Object { Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue }
      $mb = [math]::Round(((Get-ChildItem $ExeDir -Recurse -File | Measure-Object Length -Sum).Sum) / 1MB, 1)
      Say (T exe_size $mb)
    }
    else { Warn (T exe_failed) }
  }

  $ws = New-Object -ComObject WScript.Shell
  $s = $ws.CreateShortcut($Lnk)
  $s.TargetPath = $target; $s.Arguments = $args2; $s.WorkingDirectory = $Prefix
  $s.IconLocation = $Ico; $s.Description = "Synced, transparent on-screen lyrics overlay"
  $s.Save()

  try { Register-Uninstaller } catch { Warn (T apps_failed $_.Exception.Message) }

  if ($Autostart) {
    $cmd = if ($args2) { "`"$target`" $args2" } else { "`"$target`"" }
    New-ItemProperty -Path $RunKey -Name "Senandung" -Value $cmd -PropertyType String -Force | Out-Null
    Say (T autostart_on)
  }

  Say (T done $Version)
  Write-Host ""
  Write-Host (T run_hint)
  Write-Host ((T preview_lbl) + "`"$Pyw`" `"$Script`" --demo")
  Write-Host (T close_hint)
  Write-Host ((T uninstall_lbl) + "Settings > Apps > Senandung,  or:  powershell -ExecutionPolicy Bypass -File `"$UnPs1`" -Uninstall")
  Write-Host ((T log_lbl) + "$env:LOCALAPPDATA\senandung.log")
}

# --- muatan: zip berisi senandung.py + assets/icons (base64; diisi oleh tools/build_installers.py) ---
$script:Payload = @'
@@PAYLOAD@@
'@

if ($Uninstall) { Do-Uninstall } else { Do-Install }
