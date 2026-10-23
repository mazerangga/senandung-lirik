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
- **Romanisasi** lirik Jepang (romaji), Mandarin (pinyin), Korea, dan aksara non-Latin lain: hanya romaji, atau teks asli + romaji.
- **Tampilan bisa diatur**: font, ukuran, warna teks dan highlight, outline, teks gradien, perataan (kiri/tengah/kanan/zigzag), selalu di atas, mode kunci (klik tembus).
- **Geser waktu** (offset) bila lirik terlalu cepat atau lambat.
- **Antarmuka bahasa Indonesia dan Inggris**: mengikuti bahasa sistem secara bawaan, bisa diganti di Pengaturan.
- **Satu instance** saja, ikon system tray (versi tanpa teks supaya jelas di ukuran kecil), dan opsi mulai bersama sistem.

## Bahasa dan teknologi yang digunakan

| Bagian | Bahasa / teknologi |
| --- | --- |
| Aplikasi utama (`senandung.py`) | **Python 3.10+**, antarmuka **PySide6 (Qt 6)** |
| Baca pemutar di Linux | **playerctl** (MPRIS) |
| Baca pemutar di Windows | **Windows Media Session** lewat paket `winrt-*` (plus AIMP Remote API) |
| Sumber lirik | API **LRCLIB** (HTTP + JSON, lewat `urllib` bawaan Python) |
| Romanisasi (opsional) | `pykakasi`, `pypinyin`, `korean-romanizer`, `unidecode` |
| Installer Linux | **Bash** (`install-senandung.sh`) |
| Installer Windows | **PowerShell** (`install-senandung.ps1`) dan **Inno Setup** (`senandung.iss`) |
| Build `.exe` Windows | **PyInstaller** |
| Skrip ikon | Python + **Pillow** + **NumPy** (`tools/make_icons.py`) |
| Pembuat installer | Python (`tools/build_installers.py`), hanya library standar |

## Bahasa antarmuka

Antarmuka tersedia dalam **bahasa Indonesia** dan **Inggris**. Secara bawaan Senandung mengikuti bahasa sistem (lokal Indonesia memakai bahasa Indonesia, selain itu bahasa Inggris). Untuk mengganti, buka **Pengaturan…**, lalu pilih **Bahasa / Language**. Perubahan berlaku begitu kamu menekan OK.

Pesan log (konsol dan berkas log) selalu berbahasa Inggris supaya laporan bug mudah dibagikan.

**Mau menambah bahasa lain?** Terjemahan ada di tabel `STRINGS` di bagian atas `senandung.py`: tambahkan kode bahasa ke `LANGS`, ke daftar bahasa di dialog pengaturan (`SettingsDialog.lang_keys`), lalu isi satu entri untuk setiap kunci. Kunci yang belum diterjemahkan otomatis memakai bahasa Inggris. Pull request dipersilakan.

## Instalasi

File di `packaging/` adalah **template** tanpa isi aplikasi, jadi jangan dijalankan langsung. Ambil installer jadi dari halaman **Releases**, atau buat sendiri dari source:

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

Butuh Python 3.10+ 64-bit (`winget install Python.Python.3.12`). Pemasangan per-user ke `%LOCALAPPDATA%\senandung`, tanpa admin.

```powershell
powershell -ExecutionPolicy Bypass -File install-senandung.ps1
```

Opsi: `-Autostart` (jalan saat login), `-BuildExe` (buat `Senandung.exe` lewat PyInstaller), `-Lang id|en` (bahasa installer; bawaan mengikuti Windows), `-Uninstall` (tambah `-Purge` untuk hapus pengaturan).

Untuk membuat installer `.exe` bergaya wizard: jalankan dulu `-BuildExe`, lalu compile `packaging\windows\senandung.iss` dengan Inno Setup 6.3+. Wizard memberi pilihan bahasa Indonesia atau Inggris. Bila Inno Setup kamu belum punya `Indonesian.isl`, unduh dari [terjemahan tidak resmi](https://jrsoftware.org/files/istrans/) ke folder `Languages` milik Inno; tanpa file itu wizard hanya berbahasa Inggris.

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
- **Folder lirik**: bawaan `~/lyrics`. Berkas bernama `Artis - Judul.lrc`, dan `Artis - Judul.romaji.lrc` untuk romanisasi.
- **Simpan lirik sebagai `.lrc`**: matikan jika tidak ingin menyimpan apa pun ke disk.
- **Romanisasi**: `off`, `romaji`, atau `both`.
- **Geser waktu**: bawaan 500 ms.

Kamu juga bisa menaruh `.lrc` buatan sendiri di folder lirik; berkas lokal selalu dipakai lebih dulu sebelum mencari online.

## Struktur repo

```
senandung-lirik/
├── senandung.py                   # aplikasi utama
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
- **Log di Windows** (saat jalan tanpa konsol): `%LOCALAPPDATA%\senandung.log`.

## Kredit dan catatan

- Lirik tersinkron diambil dari [LRCLIB](https://lrclib.net), layanan terbuka. Lirik adalah hak cipta pemegangnya; aplikasi ini hanya menampilkannya untuk penggunaan pribadi dan tidak menyertakan lirik di repo.
- Dibangun dengan [Qt for Python (PySide6)](https://doc.qt.io/qtforpython-6/).
- Lisensi: [MIT](LICENSE).

## Kontribusi

Issue dan pull request dipersilakan. Sertakan OS, versi Python, nama pemutar, dan keluaran `--list-players` saat melaporkan masalah.
