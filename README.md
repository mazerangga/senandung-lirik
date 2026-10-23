<div align="center">

<img src="assets/icons/png/senandung-128.png" alt="Senandung" width="128" height="128">

# Senandung

**Synced, transparent on-screen lyrics for your desktop: a karaoke-style lyrics overlay for Linux and Windows.**

English · [Bahasa Indonesia](README.id.md)

</div>

## What is Senandung?

*Senandung* is an Indonesian word for softly humming or singing along. The app does exactly that for whatever you are listening to: it detects the song playing in your media player, downloads its time-synced lyrics (`.lrc`) and draws them as a **transparent, always-on-top overlay** on your desktop. The current line is highlighted karaoke-style, in time with the music.

It works with the players you already use (Spotify, AIMP, foobar2000, MusicBee, VLC and more) and needs **no plugin inside the player**. Similar in spirit to OSD Lyrics and MiniLyrics, but standalone and cross-platform.

> This project is **not affiliated** with [OSD Lyrics](https://github.com/osdlyrics/osdlyrics) or MiniLyrics. The code and icons in this repository were made independently.

## Features

- **Two display modes**
  - *Scroll*: several lines, the active line stays in the middle and scrolls smoothly.
  - *Two-line* (MiniLyrics style): two alternating lines (top left, bottom right), karaoke color fill on the active line, toolbar appears on hover.
- **Automatic player detection**, with configurable priority and blacklist.
- **Automatic lyrics download** from [LRCLIB](https://lrclib.net), saved as `.lrc` in a local folder so the next play works offline.
- **Search lyrics online…** and **Open lyrics file (.lrc)…** in the right-click menu, for songs whose lyrics were not found or are wrong. A chosen `.lrc` file is copied and renamed to match the song automatically.
- **Romanization** of Japanese (romaji), Chinese (pinyin), Korean and other non-Latin scripts: romanization only, or original text + romanization.
- **Fully customizable look**: font, size, text and highlight colors, outline, gradient text, alignment (left / center / right / zigzag), always on top, lock mode (click-through).
- **Time offset** when lyrics run too early or too late.
- **English and Indonesian interface**: follows your system language by default, switchable in Settings.
- **Single instance**, system tray icon (a text-free version that stays readable at small sizes) and an option to start with the system.

## Languages and technologies

| Part | Language / technology |
| --- | --- |
| Main app (`senandung.py`) | **Python 3.10+**, UI with **PySide6 (Qt 6)** |
| Reading the player on Linux | **playerctl** (MPRIS) |
| Reading the player on Windows | **Windows Media Session** via `winrt-*` packages (plus the AIMP Remote API) |
| Lyrics source | **LRCLIB** API (HTTP + JSON, using Python's built-in `urllib`) |
| Romanization (optional) | `pykakasi`, `pypinyin`, `korean-romanizer`, `unidecode` |
| Linux installer | **Bash** (`install-senandung.sh`) |
| Windows installer | **PowerShell** (`install-senandung.ps1`) and **Inno Setup** (`senandung.iss`) |
| Windows `.exe` build | **PyInstaller** |
| Icon script | Python + **Pillow** + **NumPy** (`tools/make_icons.py`) |
| Installer builder | Python (`tools/build_installers.py`), standard library only |

## Interface language

The interface is available in **English** and **Indonesian**. By default Senandung follows the language of your system (Indonesian locales get Indonesian, everything else gets English). To change it, open **Settings…**, then **Bahasa / Language**. The change applies as soon as you press OK.

Log messages (console and log file) are always in English so bug reports are easy to share.

**Want to add another language?** Translations live in the `STRINGS` table near the top of `senandung.py`: add your language code to `LANGS`, to the language list in the settings dialog (`SettingsDialog.lang_keys`), and fill in one entry per key. Missing keys fall back to English. Pull requests are welcome.

## Installation

The files in `packaging/` are **templates** without the app inside, so do not run them directly. Get a ready-made installer from the **Releases** page, or build it from source:

```bash
pip install pillow numpy             # only needed if the icons are not generated yet
python3 tools/make_icons.py          # generate all icon sizes (once, or when the icon changes)
python3 tools/build_installers.py    # output: dist/install-senandung.sh and dist/install-senandung.ps1 (+ SHA256SUMS)
```

### Linux

The installer installs to `~/.local` without root. Root is only requested (with confirmation) to install system packages such as `playerctl`. Recognized distros: Arch, Debian/Ubuntu, Fedora/RHEL, openSUSE.

```bash
bash install-senandung.sh            # from dist/ or downloaded from Releases
```

Options: `--autostart` | `--no-autostart` | `--no-system-deps` | `--yes` | `--lang id|en` | `--uninstall` (add `--purge` to also remove settings).

The installer's own messages are in English or Indonesian: it follows your `$LANG` by default; force one with `--lang id` or `--lang en` (or `SENANDUNG_LANG=id`).

After installing, run `senandung` from a terminal or the application menu.

### Windows

Requires 64-bit Python 3.10+ (`winget install Python.Python.3.12`). Installs per-user to `%LOCALAPPDATA%\senandung`, no admin rights needed.

```powershell
powershell -ExecutionPolicy Bypass -File install-senandung.ps1
```

Options: `-Autostart` (run at login), `-BuildExe` (build `Senandung.exe` with PyInstaller), `-Lang id|en` (installer language; default follows Windows), `-Uninstall` (add `-Purge` to also remove settings).

To build a wizard-style `.exe` installer: run `-BuildExe` first, then compile `packaging\windows\senandung.iss` with Inno Setup 6.3+. The wizard lets the user pick English or Indonesian. If your Inno Setup does not include `Indonesian.isl`, download it from the [unofficial translations](https://jrsoftware.org/files/istrans/) into Inno's `Languages` folder; without it the wizard is English only.

### Manual (from source)

```bash
python3 -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install PySide6 pykakasi pypinyin korean-romanizer unidecode
# Windows only, additionally:
# pip install winrt-runtime winrt-Windows.Media.Control winrt-Windows.Foundation \
#             winrt-Windows.Foundation.Collections winrt-Windows.Storage.Streams
python3 senandung.py
```

Linux also needs `playerctl` (e.g. `sudo pacman -S playerctl` or `sudo apt install playerctl`).

## Usage

Start your music player (Spotify, AIMP, foobar2000, MusicBee, VLC, and so on), then start Senandung. Lyrics appear as soon as a song plays.

```bash
python3 senandung.py                 # normal run
python3 senandung.py --demo          # preview without a player
python3 senandung.py --x11           # Linux: via XWayland (remembers position, always on top, click-through)
python3 senandung.py --list-players  # show which players are detected
```

| Action | What it does |
| --- | --- |
| Drag the window | Move it |
| Drag the bottom-right corner | Resize |
| Mouse wheel | Shift the lyric timing |
| Double-click | Switch mode (scroll / two-line) |
| Right-click or tray icon | Menu: mode, lock, always on top, search lyrics online, open `.lrc` file, settings, quit |
| X button | Hide to the system tray (reappears when the song changes) |

## Settings

Open them from the right-click menu, **Settings…**. The most useful ones:

- **Language**: Automatic, Bahasa Indonesia or English.
- **Priority players** and **blacklist**: order and list of players (comma separated). Browsers are ignored by default so videos are not mistaken for songs.
- **Lyrics folder**: defaults to `~/lyrics`. Files are named `Artist - Title.lrc`, and `Artist - Title.romaji.lrc` for romanization.
- **Save lyrics as `.lrc`**: turn off if you do not want anything written to disk.
- **Romanization**: `off`, `romaji` or `both`.
- **Time offset**: 500 ms by default.

You can also drop your own `.lrc` files into the lyrics folder; local files are always used before searching online.

## Repository layout

```
senandung-lirik/
├── senandung.py                   # the app
├── assets/icons/
│   ├── source/                    # icon source images (neon)
│   ├── png/senandung-<n>.png      # app icon, 16 ... 512 px
│   ├── tray/senandung-tray-<n>.png   # text-free tray icon, 16 ... 64 px (+ .ico)
│   ├── hicolor/<n>x<n>/apps/      # Linux icon theme layout
│   ├── senandung.ico              # multi-size Windows icon
│   └── senandung.png              # 512 px
├── tools/
│   ├── make_icons.py              # regenerate all icon sizes from one source
│   └── build_installers.py        # fill the installer templates with the latest source + icons
├── packaging/                     # installer TEMPLATES (no payload)
│   ├── linux/install-senandung.sh
│   └── windows/{install-senandung.ps1, senandung.iss}
└── dist/                          # output of build_installers.py (not committed)
```

## Modular icons

All icon sizes are generated from **one source image** in `assets/icons/source/`. To change the icon, replace that image (transparent, square PNG), then:

```bash
pip install pillow
python3 tools/make_icons.py
```

There are two icons:

- **App icon** (`png/`, `hicolor/`, `.ico`): the full artwork including the "MUSIC n LYRICS" text. Used for the window, application menu and shortcuts. Loaded in this order: system icon theme (`senandung`), then `assets/icons/png/`, then a built-in drawn icon as fallback.
- **Tray icon** (`tray/`): only the music note and microphone, no text, because text is unreadable at 16 to 32 px. It is made from `assets/icons/source/tray-source.png` (square, text-free). To change it, replace that file and run `make_icons.py` again. If the file is missing, the tray icon is cropped automatically from the main source image.

After the icons or the code change, run `python3 tools/build_installers.py` so the installers are updated too.

## Troubleshooting

- **"playerctl not found"** (Linux): install `playerctl`.
- **Window cannot stay on top / position is not remembered** (Wayland): run with `--x11`.
- **No tray icon on GNOME**: GNOME needs the AppIndicator extension to show tray icons.
- **Lyrics do not appear**: run `--list-players` to check that your player is detected and not blacklisted. Songs that are not on LRCLIB will not have lyrics; you can provide your own `.lrc`.
- **Log on Windows** (when running without a console): `%LOCALAPPDATA%\senandung.log`.

## Credits and notes

- Synced lyrics come from [LRCLIB](https://lrclib.net), an open service. Lyrics are the property of their copyright holders; this app only displays them for personal use and does not ship any lyrics in the repository.
- Built with [Qt for Python (PySide6)](https://doc.qt.io/qtforpython-6/).
- License: [MIT](LICENSE).

## Contributing

Issues and pull requests are welcome. When reporting a problem, please include your OS, Python version, player name and the output of `--list-players`.
