<div align="center">

<img src="assets/icons/png/senandung-128.png" alt="Senandung" width="128" height="128">

# Senandung

**Lirik lagu tersinkron, transparan, di atas desktop kamu: overlay lirik bergaya karaoke untuk Linux dan Windows.**

[English](README.md) · Bahasa Indonesia

</div>

## Apa itu Senandung?

*Senandung* membaca lagu yang sedang diputar dari pemutar musik kamu, mengunduh lirik berstempel waktu (`.lrc`), lalu menampilkannya sebagai **overlay transparan yang selalu di atas** jendela lain. Baris yang sedang dinyanyikan disorot ala karaoke, mengikuti irama lagu.

Bekerja dengan pemutar yang sudah kamu pakai (Spotify, AIMP, foobar2000, MusicBee, VLC, dan lainnya) dan **tidak perlu plugin di pemutar musik**. Mirip OSD Lyrics dan MiniLyrics, tetapi berdiri sendiri dan lintas platform.

> Proyek ini **tidak berafiliasi** dengan [OSD Lyrics](https://github.com/osdlyrics/osdlyrics) maupun MiniLyrics. Kode dan ikon di repo ini dibuat terpisah.

## Fitur

- **Dua mode tampilan**
  - *Scroll*: beberapa baris, baris aktif di tengah, menggulir halus.
  - *Dua baris* (gaya MiniLyrics): dua baris bergantian (atas kiri, bawah kanan), warna karaoke mengisi baris aktif, toolbar muncul saat disorot.
- **Deteksi pemutar otomatis**, dengan prioritas dan blacklist yang bisa diatur.
- **Unduh lirik otomatis** dari [LRCLIB](https://lrclib.net), disimpan sebagai `.lrc` di folder lokal sehingga lagu berikutnya langsung muncul tanpa internet.
- **Cari lirik online…** dan **Buka file lirik (.lrc)…** dari menu klik kanan, untuk lagu yang liriknya tidak ketemu otomatis atau salah. File `.lrc` yang dipilih otomatis disalin dengan nama sesuai lagu.
- **Romanisasi** lirik Jepang (romaji), Mandarin (pinyin), Korea, dan aksara non-Latin lain seperti Cyrillic, Yunani, Ibrani, dan Thai: hanya romaji, atau teks asli + romaji. Arab, Persia, dan Urdu sengaja ditampilkan dengan aksara aslinya (lihat [Romanisasi](#romanisasi)).
- **Tampilan bisa diatur**: font, ukuran, warna teks dan highlight, outline, teks gradien, perataan (kiri/tengah/kanan/zigzag), selalu di atas, mode kunci (klik tembus).
- **Geser waktu** (offset) bila lirik terlalu cepat atau lambat.
- **Antarmuka bahasa Indonesia dan Inggris**: mengikuti bahasa sistem secara bawaan, bisa diganti di Pengaturan.
- **Satu instance** saja, ikon system tray (versi tanpa teks supaya jelas di ukuran kecil), dan opsi mulai bersama sistem.

## Bahasa dan teknologi yang digunakan

| Bagian | Bahasa / teknologi |
| --- | --- |
| Aplikasi utama (`senandung.py`) | **Python 3.10+**, antarmuka **PySide6 (Qt 6)** |
| Backend pemutar (`players/`) | Paket Python, satu modul per platform: `linux.py`, `windows.py`, `aimp.py` |
| Baca pemutar di Linux | **playerctl** (MPRIS) |
| Baca pemutar di Windows | **Windows Media Session** lewat paket `winrt-*` (plus AIMP Remote API) |
| Sumber lirik | API **LRCLIB** (HTTP + JSON, lewat `urllib` bawaan Python) |
| Romanisasi (`romanize/`) | Paket Python, satu modul per bahasa |
| Pustaka romanisasi (opsional) | `pykakasi`, `pypinyin`, `korean-romanizer`, `unidecode` |
| Installer Linux | **Bash** (`install-senandung.sh`) |
| Installer Windows | **PowerShell** (`install-senandung.ps1`) dan **Inno Setup** (`senandung.iss`, menghasilkan Setup `.exe` beserta uninstaller) |
| Build `.exe` Windows | **PyInstaller** (`--onefile`) |
| Skrip ikon | Python + **Pillow** + **NumPy** (`tools/make_icons.py`) |
| Pembuat installer | Python (`tools/build_installers.py`), hanya library standar |
| Rilis otomatis | **GitHub Actions** (`.github/workflows/release.yml`) |

## Bahasa antarmuka

Antarmuka tersedia dalam **bahasa Indonesia** dan **Inggris**. Secara bawaan Senandung mengikuti bahasa sistem (lokal Indonesia memakai bahasa Indonesia, selain itu bahasa Inggris). Untuk mengganti, buka **Pengaturan…**, lalu pilih **Bahasa / Language**. Perubahan berlaku begitu kamu menekan OK.

Pesan log (konsol dan berkas log) selalu berbahasa Inggris supaya laporan bug mudah dibagikan.

**Mau menambah bahasa lain?** Terjemahan ada di tabel `STRINGS` di bagian atas `senandung.py`: tambahkan kode bahasa ke `LANGS`, ke daftar bahasa di dialog pengaturan (`SettingsDialog.lang_keys`), lalu isi satu entri untuk setiap kunci. Kunci yang belum diterjemahkan otomatis memakai bahasa Inggris. Pull request dipersilakan.

## Instalasi

Cara termudah: ambil file jadi dari halaman **Releases**. Setiap rilis berisi:

| File | Untuk |
| --- | --- |
| `Senandung-Setup-<versi>.exe` | Windows, installer bergaya wizard (tanpa perlu Python). Sudah termasuk uninstaller. |
| `install-senandung.ps1` | Windows, installer PowerShell (butuh Python 3.10+). |
| `install-senandung.sh` | Linux. |
| `Senandung.exe` | Windows, aplikasi saja tanpa installer (portabel). |
| `SHA256SUMS` | Checksum untuk `.sh` dan `.ps1`. |

File di `packaging/` adalah **template** tanpa isi aplikasi, jadi jangan dijalankan langsung. Untuk membuat installer sendiri dari source:

```bash
pip install pillow numpy             # hanya perlu bila ikon belum dibuat
python3 tools/make_icons.py          # buat semua ukuran ikon (sekali saja, atau saat ikon berubah)
python3 tools/build_installers.py    # hasil: dist/install-senandung.sh dan dist/install-senandung.ps1 (+ SHA256SUMS)
```

### Linux

Installer memasang ke `~/.local` tanpa root. Root hanya diminta (dengan konfirmasi) untuk memasang paket sistem seperti `playerctl`. Distro yang dikenali: Arch, Debian/Ubuntu, Fedora/RHEL, openSUSE.

```bash
bash install-senandung.sh            # dari dist/ atau hasil unduhan Releases
```

Opsi: `--autostart` | `--no-autostart` | `--no-system-deps` | `--yes` | `--lang id|en` | `--uninstall` (tambah `--purge` untuk menghapus pengaturan juga).

Pesan installer sendiri tersedia dalam bahasa Indonesia atau Inggris: bawaannya mengikuti `$LANG`; paksa dengan `--lang id` atau `--lang en` (atau `SENANDUNG_LANG=id`).

Setelah terpasang, jalankan `senandung` dari terminal atau menu aplikasi.

### Windows

Ada dua cara memasang. Keduanya per-user, tanpa admin.

**Cara 1: Setup `.exe` (paling mudah).** Unduh `Senandung-Setup-<versi>.exe` dari Releases lalu jalankan. Tidak perlu memasang Python. Wizard menyediakan bahasa Indonesia dan Inggris, pilihan mulai otomatis saat login, dan ikon desktop. Aplikasi dipasang ke `%LOCALAPPDATA%\Programs\Senandung` (atau `Program Files` bila kamu memilih mode admin). Karena belum ditandatangani sertifikat code signing, Windows SmartScreen bisa menampilkan peringatan: klik **More info**, lalu **Run anyway**.

**Cara 2: PowerShell.** Butuh Python 3.10+ 64-bit (`winget install Python.Python.3.12`). Dipasang ke `%LOCALAPPDATA%\senandung`.

```powershell
powershell -ExecutionPolicy Bypass -File install-senandung.ps1
```

Opsi: `-Autostart` (jalan saat login), `-BuildExe` (buat `Senandung.exe` lewat PyInstaller), `-Lang id|en` (bahasa installer; bawaan mengikuti Windows), `-Uninstall` (tambah `-Purge` untuk hapus pengaturan).

**Uninstall di Windows.** Untuk kedua cara, buka **Settings > Apps > Installed apps**, pilih **Senandung**, lalu **Uninstall** (juga tersedia di Control Panel > Programs and Features).

- Pemasangan lewat Setup `.exe`: uninstaller-nya `unins000.exe` di folder pemasangan, dibuat otomatis oleh Inno Setup. Pengaturan aplikasi (registri `HKCU\Software\Senandung`) tidak ikut dihapus.
- Pemasangan lewat `.ps1`: installer menyimpan salinan dirinya sebagai `%LOCALAPPDATA%\senandung\uninstall.ps1`, jadi berkas installer asli tidak perlu disimpan. Tanpa lewat Apps, jalankan `powershell -ExecutionPolicy Bypass -File "%LOCALAPPDATA%\senandung\uninstall.ps1" -Uninstall` (tambah `-Purge` untuk menghapus pengaturan). Folder lirik tidak ikut dihapus. Fitur ini hanya ada pada pemasangan yang dibuat dengan installer `.ps1` terbaru; pemasangan lama dihapus dengan `install-senandung.ps1 -Uninstall`.
- Jangan memasang dengan kedua cara sekaligus. Bila ingin pindah cara, uninstall dulu yang lama supaya tidak muncul dua entri Senandung di daftar Apps.

**Membuat installer Windows sendiri.** Jalankan dulu `-BuildExe`, lalu compile `packaging\windows\senandung.iss` dengan Inno Setup 6.3+. Wizard memberi pilihan bahasa Indonesia atau Inggris. Bila Inno Setup kamu belum punya `Indonesian.isl`, unduh dari [terjemahan tidak resmi](https://jrsoftware.org/files/istrans/) ke folder `Languages` milik Inno; tanpa file itu wizard hanya berbahasa Inggris. Versi dan jalur file bisa diatur lewat variabel lingkungan `SENANDUNG_VERSION`, `SENANDUNG_EXE`, `SENANDUNG_ICON`, dan `SENANDUNG_OUT` (dipakai oleh GitHub Actions).

### Manual (dari source)

```bash
python3 -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install PySide6 pykakasi pypinyin korean-romanizer unidecode
# Windows saja, tambahan:
# pip install winrt-runtime winrt-Windows.Media.Control winrt-Windows.Foundation \
#             winrt-Windows.Foundation.Collections winrt-Windows.Storage.Streams
python3 senandung.py
```

Linux juga perlu `playerctl` (mis. `sudo pacman -S playerctl` atau `sudo apt install playerctl`).

Jalankan dari folder repo: `senandung.py` membutuhkan folder `romanize/` dan `players/` di sebelahnya, jadi menyalin `senandung.py` saja ke tempat lain tidak akan berfungsi.

## Cara pakai

Jalankan pemutar musik (Spotify, AIMP, foobar2000, MusicBee, VLC, dan sebagainya), lalu jalankan Senandung. Lirik muncul begitu lagu diputar.

```bash
python3 senandung.py                 # jalan normal
python3 senandung.py --demo          # pratinjau tanpa pemutar
python3 senandung.py --x11           # Linux: lewat XWayland (posisi diingat, selalu di atas, klik tembus)
python3 senandung.py --list-players  # tampilkan pemutar yang terdeteksi
```

| Aksi | Fungsi |
| --- | --- |
| Seret jendela | Pindahkan |
| Seret pojok kanan-bawah | Ubah ukuran |
| Roda mouse | Geser waktu lirik |
| Klik dua kali | Ganti mode (scroll / dua baris) |
| Klik kanan atau ikon tray | Menu: mode, kunci, selalu di atas, cari lirik online, buka file `.lrc`, pengaturan, keluar |
| Tombol X | Sembunyikan ke system tray (muncul lagi saat lagu berganti) |

## Pengaturan

Buka lewat menu klik kanan, **Pengaturan…**. Beberapa yang paling sering dipakai:

- **Bahasa**: Otomatis, Bahasa Indonesia, atau English.
- **Pemutar prioritas** dan **blacklist**: urutan dan daftar pemutar (dipisah koma). Secara bawaan browser diabaikan agar video tidak dianggap lagu.
- **Folder lirik**: bawaan `~/lyrics`. Berkas bernama `Artis - Judul.lrc`, dan `Artis - Judul.romaji.v4.lrc` untuk romanisasi yang tersimpan (angka `v4` berubah saat aturan romanisasi berubah; lihat [Romanisasi](#romanisasi)).
- **Simpan lirik sebagai `.lrc`**: matikan jika tidak ingin menyimpan apa pun ke disk.
- **Romanisasi**: `off`, `romaji`, atau `both`.
- **Geser waktu**: bawaan 500 ms.

Kamu juga bisa menaruh `.lrc` buatan sendiri di folder lirik; berkas lokal selalu dipakai lebih dulu sebelum mencari online.

## Romanisasi

Atur **Romanisasi** di Pengaturan ke `romaji` (hanya romaji) atau `both` (teks asli + romaji). Fitur ini opsional: bila pustaka di bawah belum terpasang, barisnya ditampilkan apa adanya.

| Aksara | Modul | Pustaka |
| --- | --- | --- |
| Jepang (kana, dan kanji pada lagu yang berisi kana) | `romanize/japanese.py` | `pykakasi` |
| Mandarin | `romanize/chinese.py` | `pypinyin` |
| Korea | `romanize/korean.py` | `korean-romanizer` |
| Aksara lain (Cyrillic, Yunani, Ibrani, Thai, Devanagari, ...) | `romanize/generic.py` | `unidecode` |

**Arab, Persia, dan Urdu tidak diromanisasi, dan itu disengaja.** Teks Arab sehari-hari tidak menuliskan vokal pendek, sehingga program hanya bisa menebaknya dan tebakannya sering salah. Barisnya ditampilkan dengan aksara aslinya.

**Romanisasi yang tersimpan.** Romanisasi sebuah lagu disimpan di samping liriknya sebagai `Artis - Judul.romaji.v<N>.lrc`. `<N>` adalah `ROMAN_VERSION` di `romanize/__init__.py`. Bila keluaran sebuah romanizer berubah, naikkan angka itu agar berkas lama tidak dipakai lagi. Berkas dari versi sebelumnya (`*.romaji.lrc`) tidak dibaca lagi dan boleh dihapus.

**Menambah aksara atau bahasa.**

1. Tambahkan pola deteksi di `romanize/scripts.py`.
2. Buat `romanize/<bahasa>.py` berisi fungsi yang menerima teks dan mengembalikan teks romanisasinya. Muat pustaka opsional lewat `lazy()` dari `romanize/common.py`, supaya pustaka yang belum terpasang tidak membuat aplikasi crash.
3. Daftarkan di `romanize_lines()` pada `romanize/__init__.py`.
4. Naikkan `ROMAN_VERSION`.
5. Bila butuh pustaka baru, tambahkan ke baris `pip install` dan `--hidden-import` di `.github/workflows/release.yml` (serta ke opsi PyInstaller di `install-senandung.ps1`).

## Merilis versi baru (untuk maintainer)

Rilis dibuat otomatis oleh GitHub Actions (`.github/workflows/release.yml`) setiap kali tag berawalan `v` di-push:

```bash
git push                         # pastikan semua perubahan sudah di GitHub
git tag v1.0.1
git push origin v1.0.1           # memicu build dan rilis
```

Workflow membuat installer `.sh` dan `.ps1`, membangun `Senandung.exe` (PyInstaller `--onefile`), mengompilasi `Senandung-Setup-<versi>.exe` (Inno Setup), lalu mengunggah semuanya ke halaman Releases. Nomor versi pada Setup `.exe` diambil dari nama tag.

Catatan:

- GitHub Actions memakai **commit yang ditunjuk tag**. Bila memperbaiki kode setelah tag dibuat, tag lama tetap memakai kode lama dan tombol *Re-run* tidak membantu. Pindahkan tag ke commit baru:
  ```bash
  git tag -d v1.0.1
  git push origin :refs/tags/v1.0.1
  git tag v1.0.1
  git push origin v1.0.1
  ```
  Bila rilis dengan tag itu sudah terlanjur ada di halaman Releases, hapus dulu rilisnya.
- Perbarui nomor versi di `$Version` pada `packaging/windows/install-senandung.ps1` dan bawaan `AppVersion` di `senandung.iss` agar sama dengan tag.
- Cek build installer secara lokal sebelum tag: `python3 tools/build_installers.py`.
- Commit dan push **semua** folder baru (`romanize/`, `players/`) sebelum membuat tag; tag pada commit yang belum memuatnya menghasilkan aplikasi yang tidak bisa jalan.
- Folder paket Python baru di samping `senandung.py` harus didaftarkan di dua tempat, kalau tidak aplikasi hasil install gagal dengan `ModuleNotFoundError`: `APP_PACKAGES` di `tools/build_installers.py`, dan baris `for pkg in ...` di `packaging/linux/install-senandung.sh`. Installer `.ps1` dan PyInstaller mengambil paket dengan sendirinya.

## Struktur repo

```
senandung-lirik/
├── senandung.py                   # aplikasi: antarmuka, pengaturan, pemuatan lirik, main
├── romanize/                      # romanisasi, satu modul per bahasa
│   ├── __init__.py                # romanize_lines() + ROMAN_VERSION (versi cache)
│   ├── scripts.py                 # deteksi aksara (kana, han, hangul, arab, ...)
│   ├── common.py                  # fungsi bersama (tidy, muat pustaka sesuai kebutuhan)
│   ├── japanese.py                # Jepang    -> romaji  (pykakasi)
│   ├── chinese.py                 # Mandarin  -> pinyin  (pypinyin)
│   ├── korean.py                  # Korea     -> romanisasi (korean-romanizer)
│   └── generic.py                 # aksara lain (unidecode)
├── players/                       # backend pemutar
│   ├── __init__.py                # make_backend(): memilih backend sesuai OS
│   ├── common.py                  # penanda platform, urutan prioritas / blacklist
│   ├── linux.py                   # playerctl + D-Bus (MPRIS)
│   ├── windows.py                 # Windows Media Session (SMTC)
│   └── aimp.py                    # AIMP Remote API
├── .github/workflows/release.yml  # rilis otomatis saat tag v* di-push
├── .gitattributes                 # menyeragamkan ujung baris (LF/CRLF)
├── assets/icons/
│   ├── source/                    # gambar sumber ikon (neon)
│   ├── png/senandung-<n>.png      # ikon aplikasi, 16 ... 512 px
│   ├── tray/senandung-tray-<n>.png   # ikon tray tanpa teks, 16 ... 64 px (+ .ico)
│   ├── hicolor/<n>x<n>/apps/      # susunan tema ikon Linux
│   ├── senandung.ico              # ikon Windows multi-ukuran
│   └── senandung.png              # 512 px
├── tools/
│   ├── make_icons.py              # buat ulang semua ukuran ikon dari satu sumber
│   └── build_installers.py        # isi template installer dengan source + ikon terbaru
├── packaging/                     # TEMPLATE installer (tanpa payload)
│   ├── linux/install-senandung.sh
│   └── windows/{install-senandung.ps1, senandung.iss}
└── dist/                          # hasil build_installers.py (tidak di-commit)
```

## Ikon modular

Semua ukuran ikon dibuat dari **satu gambar sumber** di `assets/icons/source/`. Untuk mengganti ikon, timpa gambar itu (PNG transparan, persegi), lalu:

```bash
pip install pillow
python3 tools/make_icons.py
```

Ada dua ikon:

- **Ikon aplikasi** (`png/`, `hicolor/`, `.ico`): gambar penuh dengan tulisan "MUSIC n LYRICS". Dipakai untuk jendela, menu aplikasi, dan shortcut. Memuat dengan urutan: tema ikon sistem (`senandung`), lalu `assets/icons/png/`, lalu ikon gambar-kode bawaan sebagai cadangan.
- **Ikon tray** (`tray/`): hanya not musik dan mikrofon, tanpa teks, karena tulisan tidak terbaca di 16 sampai 32 px. Dibuat dari `assets/icons/source/tray-source.png` (gambar persegi tanpa teks). Untuk menggantinya, timpa file itu lalu jalankan `make_icons.py` lagi. Bila file itu dihapus, ikon tray dipotong otomatis dari gambar sumber utama.

Setelah ikon atau kode berubah, jalankan `python3 tools/build_installers.py` supaya installer ikut diperbarui.

## Pemecahan masalah

- **"playerctl tidak ditemukan"** (Linux): pasang `playerctl`.
- **Jendela tidak bisa selalu di atas / posisi tidak diingat** (Wayland): jalankan dengan `--x11`.
- **Ikon tray tidak muncul di GNOME**: GNOME butuh ekstensi AppIndicator agar ikon tray tampil.
- **Lirik tidak muncul**: cek `--list-players` apakah pemutar terdeteksi dan tidak masuk blacklist. Lagu yang tidak ada di LRCLIB tidak akan punya lirik; kamu bisa menyediakan `.lrc` sendiri.
- **`ModuleNotFoundError: No module named 'romanize'` (atau `players`)**: folder itu harus berada di samping `senandung.py`. Saat menjalankan dari source, mulai dari folder repo dan jangan menyalin `senandung.py` saja.
- **Baris Arab tidak ada romanisasinya**: itu disengaja (lihat [Romanisasi](#romanisasi)).
- **Romanisasi terlihat usang atau salah**: hapus berkas `*.romaji.v*.lrc` lagu itu di folder lirik; berkas dibuat ulang saat lagu diputar berikutnya.
- **Log di Windows** (saat jalan tanpa konsol): `%LOCALAPPDATA%\senandung.log`.
- **SmartScreen memperingatkan saat membuka Setup `.exe`** (Windows): berkas belum ditandatangani. Klik **More info**, lalu **Run anyway**.
- **"running scripts is disabled on this system"** (Windows): jalankan `.ps1` dengan `powershell -ExecutionPolicy Bypass -File ...`.
- **Uninstall `.ps1` berhenti dengan "Folder belum bisa dihapus"** (Windows): Senandung masih berjalan. Keluar dari ikon tray, lalu ulangi.
- **GitHub Actions gagal atau rilis tidak terbentuk**: buka tab *Actions*, lihat langkah yang berwarna merah. Pastikan tag menunjuk commit yang sudah berisi perbaikan (lihat *Merilis versi baru*).

## Kredit dan catatan

- Lirik tersinkron diambil dari [LRCLIB](https://lrclib.net), layanan terbuka. Lirik adalah hak cipta pemegangnya; aplikasi ini hanya menampilkannya untuk penggunaan pribadi dan tidak menyertakan lirik di repo.
- Dibangun dengan [Qt for Python (PySide6)](https://doc.qt.io/qtforpython-6/).
- Pengembangan dibantu asisten AI ([Claude](https://www.anthropic.com/claude) dari Anthropic) untuk penulisan kode, installer, dan dokumentasi. Seluruh hasilnya ditinjau dan diuji oleh pemelihara repo.
- Lisensi: [MIT](LICENSE).

## Kontribusi

Issue dan pull request dipersilakan. Sebagian besar perubahan bersifat lokal: romanisasi ada di `romanize/`, backend pemutar di `players/` (lihat *Struktur repo*). Sertakan OS, versi Python, nama pemutar, dan keluaran `--list-players` saat melaporkan masalah.
