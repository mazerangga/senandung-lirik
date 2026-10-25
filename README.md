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
- **Romanization** of Japanese (romaji), Chinese (pinyin), Korean and other non-Latin scripts such as Cyrillic, Greek, Hebrew and Thai: romanization only, or original text + romanization. Arabic, Persian and Urdu are shown in their original script on purpose (see [Romanization](#romanization)).
- **Fully customizable look**: font, size, text and highlight colors, outline, gradient text, alignment (left / center / right / zigzag), always on top, lock mode (click-through).
- **Time offset** when lyrics run too early or too late.
- **English and Indonesian interface**: follows your system language by default, switchable in Settings.
- **Single instance**, system tray icon (a text-free version that stays readable at small sizes) and an option to start with the system.

## Languages and technologies

| Part | Language / technology |
| --- | --- |
| Main app (`senandung.py`) | **Python 3.10+**, UI with **PySide6 (Qt 6)** |
| Player backends (`players/`) | Python package, one module per platform: `linux.py`, `windows.py`, `aimp.py` |
| Reading the player on Linux | **playerctl** (MPRIS) |
| Reading the player on Windows | **Windows Media Session** via `winrt-*` packages (plus the AIMP Remote API) |
| Lyrics source | **LRCLIB** API (HTTP + JSON, using Python's built-in `urllib`) |
| Romanization (`romanize/`) | Python package, one module per language |
| Romanization libraries (optional) | `pykakasi`, `pypinyin`, `korean-romanizer`, `unidecode` |
| Linux installer | **Bash** (`install-senandung.sh`) |
| Windows installer | **PowerShell** (`install-senandung.ps1`) and **Inno Setup** (`senandung.iss`, produces the Setup `.exe` with its uninstaller) |
| Windows `.exe` build | **PyInstaller** (`--onefile`) |
| Icon script | Python + **Pillow** + **NumPy** (`tools/make_icons.py`) |
| Installer builder | Python (`tools/build_installers.py`), standard library only |
| Automated releases | **GitHub Actions** (`.github/workflows/release.yml`) |

## Interface language

The interface is available in **English** and **Indonesian**. By default Senandung follows the language of your system (Indonesian locales get Indonesian, everything else gets English). To change it, open **Settings…**, then **Bahasa / Language**. The change applies as soon as you press OK.

Log messages (console and log file) are always in English so bug reports are easy to share.

**Want to add another language?** Translations live in the `STRINGS` table near the top of `senandung.py`: add your language code to `LANGS`, to the language list in the settings dialog (`SettingsDialog.lang_keys`), and fill in one entry per key. Missing keys fall back to English. Pull requests are welcome.

## Installation

The easiest way: get the ready-made files from the **Releases** page. Each release contains:

| File | For |
| --- | --- |
| `Senandung-Setup-<version>.exe` | Windows, wizard-style installer (no Python needed). Includes an uninstaller. |
| `install-senandung.ps1` | Windows, PowerShell installer (needs Python 3.10+). |
| `install-senandung.sh` | Linux. |
| `Senandung.exe` | Windows, the app alone with no installer (portable). |
| `SHA256SUMS` | Checksums for the `.sh` and `.ps1`. |

The files in `packaging/` are **templates** without the app inside, so do not run them directly. To build the installers yourself from source:

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

There are two ways to install. Both are per-user and need no admin rights.

**Option 1: Setup `.exe` (easiest).** Download `Senandung-Setup-<version>.exe` from Releases and run it. No Python needed. The wizard offers English and Indonesian, a run-at-login option, and a desktop shortcut. The app installs to `%LOCALAPPDATA%\Programs\Senandung` (or `Program Files` if you choose the admin mode). Because the file is not signed with a code-signing certificate, Windows SmartScreen may show a warning: click **More info**, then **Run anyway**.

**Option 2: PowerShell.** Requires 64-bit Python 3.10+ (`winget install Python.Python.3.12`). Installs to `%LOCALAPPDATA%\senandung`.

```powershell
powershell -ExecutionPolicy Bypass -File install-senandung.ps1
```

Options: `-Autostart` (run at login), `-BuildExe` (build `Senandung.exe` with PyInstaller), `-Lang id|en` (installer language; default follows Windows), `-Uninstall` (add `-Purge` to also remove settings).

**Uninstalling on Windows.** For both options, open **Settings > Apps > Installed apps**, pick **Senandung**, then **Uninstall** (also available in Control Panel > Programs and Features).

- Installed with the Setup `.exe`: the uninstaller is `unins000.exe` in the install folder, generated by Inno Setup. The app's settings (registry `HKCU\Software\Senandung`) are not removed.
- Installed with the `.ps1`: the installer saves a copy of itself as `%LOCALAPPDATA%\senandung\uninstall.ps1`, so you do not need to keep the original installer file. Without going through Apps, run `powershell -ExecutionPolicy Bypass -File "%LOCALAPPDATA%\senandung\uninstall.ps1" -Uninstall` (add `-Purge` to also remove settings). The lyrics folder is kept. This only exists for installs made with the latest `.ps1` installer; older installs are removed with `install-senandung.ps1 -Uninstall`.
- Do not install with both options at once. To switch, uninstall the old one first so Senandung does not appear twice in the Apps list.

**Building the Windows installer yourself.** Run `-BuildExe` first, then compile `packaging\windows\senandung.iss` with Inno Setup 6.3+. The wizard lets the user pick English or Indonesian. If your Inno Setup does not include `Indonesian.isl`, download it from the [unofficial translations](https://jrsoftware.org/files/istrans/) into Inno's `Languages` folder; without it the wizard is English only. The version and file paths can be set through the environment variables `SENANDUNG_VERSION`, `SENANDUNG_EXE`, `SENANDUNG_ICON`, and `SENANDUNG_OUT` (used by GitHub Actions).

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

Run it from the repository folder: `senandung.py` needs the `romanize/` and `players/` folders next to it, so copying `senandung.py` alone to another place will not work.

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
- **Lyrics folder**: defaults to `~/lyrics`. Files are named `Artist - Title.lrc`, and `Artist - Title.romaji.v4.lrc` for the saved romanization (the `v4` changes when the romanization rules change; see [Romanization](#romanization)).
- **Save lyrics as `.lrc`**: turn off if you do not want anything written to disk.
- **Romanization**: `off`, `romaji` or `both`.
- **Time offset**: 500 ms by default.

You can also drop your own `.lrc` files into the lyrics folder; local files are always used before searching online.

## Romanization

Set **Romanization** in Settings to `romaji` (romanization only) or `both` (original text + romanization). It is optional: if a library below is not installed, those lines are simply shown as they are.

| Script | Module | Library |
| --- | --- | --- |
| Japanese (kana, and kanji in songs that contain kana) | `romanize/japanese.py` | `pykakasi` |
| Chinese | `romanize/chinese.py` | `pypinyin` |
| Korean | `romanize/korean.py` | `korean-romanizer` |
| Other scripts (Cyrillic, Greek, Hebrew, Thai, Devanagari, ...) | `romanize/generic.py` | `unidecode` |

**Arabic, Persian and Urdu are not romanized, on purpose.** Everyday Arabic text leaves out the short vowels, so a program can only guess them and the guesses are often wrong. Those lines are shown in their original script instead.

**Saved romanization.** The romanization of a song is saved next to its lyrics as `Artist - Title.romaji.v<N>.lrc`. `<N>` is `ROMAN_VERSION` in `romanize/__init__.py`. When the output of a romanizer changes, raise that number so old saved files are not reused. Files from earlier versions (`*.romaji.lrc`) are no longer read and can be deleted.

**Adding a script or language.**

1. Add a detection pattern to `romanize/scripts.py`.
2. Create `romanize/<language>.py` with a function that takes a text and returns the romanized text. Load optional libraries with `lazy()` from `romanize/common.py`, so a missing library does not crash the app.
3. Register it in `romanize_lines()` in `romanize/__init__.py`.
4. Raise `ROMAN_VERSION`.
5. If it needs a new library, add it to the `pip install` and `--hidden-import` lines in `.github/workflows/release.yml` (and to the PyInstaller options in `install-senandung.ps1`).

## Publishing a new release (for maintainers)

Releases are built automatically by GitHub Actions (`.github/workflows/release.yml`) whenever a tag starting with `v` is pushed:

```bash
git push                         # make sure all changes are on GitHub
git tag v1.0.1
git push origin v1.0.1           # triggers the build and release
```

The workflow builds the `.sh` and `.ps1` installers, builds `Senandung.exe` (PyInstaller `--onefile`), compiles `Senandung-Setup-<version>.exe` (Inno Setup), and uploads everything to the Releases page. The Setup `.exe` takes its version number from the tag name.

Notes:

- GitHub Actions uses the **commit the tag points to**. If you fix the code after creating the tag, the old tag still builds the old code and *Re-run* will not help. Move the tag to the new commit:
  ```bash
  git tag -d v1.0.1
  git push origin :refs/tags/v1.0.1
  git tag v1.0.1
  git push origin v1.0.1
  ```
  If a release for that tag already exists on the Releases page, delete it first.
- Update the version in `$Version` in `packaging/windows/install-senandung.ps1` and the default `AppVersion` in `senandung.iss` so they match the tag.
- Check the installer build locally before tagging: `python3 tools/build_installers.py`.
- Commit and push **all** new folders (`romanize/`, `players/`) before tagging; a tag on a commit without them builds an app that cannot start.
- A new Python package folder next to `senandung.py` must be listed in two places, otherwise the installed app fails with `ModuleNotFoundError`: `APP_PACKAGES` in `tools/build_installers.py`, and the `for pkg in ...` lines in `packaging/linux/install-senandung.sh`. The `.ps1` installer and PyInstaller pick packages up on their own.

## Repository layout

```
senandung-lirik/
├── senandung.py                   # the app: interface, settings, lyrics loading, main
├── romanize/                      # romanization, one module per language
│   ├── __init__.py                # romanize_lines() + ROMAN_VERSION (cache version)
│   ├── scripts.py                 # script detection (kana, han, hangul, arabic, ...)
│   ├── common.py                  # shared helpers (tidy, lazy loading of libraries)
│   ├── japanese.py                # Japanese  -> romaji  (pykakasi)
│   ├── chinese.py                 # Chinese   -> pinyin  (pypinyin)
│   ├── korean.py                  # Korean    -> romanization (korean-romanizer)
│   └── generic.py                 # other scripts (unidecode)
├── players/                       # player backends
│   ├── __init__.py                # make_backend(): picks the backend for your OS
│   ├── common.py                  # platform flags, priority / blacklist ranking
│   ├── linux.py                   # playerctl + D-Bus (MPRIS)
│   ├── windows.py                 # Windows Media Session (SMTC)
│   └── aimp.py                    # AIMP Remote API
├── .github/workflows/release.yml  # automated release when a v* tag is pushed
├── .gitattributes                 # keeps line endings consistent (LF/CRLF)
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
- **`ModuleNotFoundError: No module named 'romanize'` (or `players`)**: those folders must sit next to `senandung.py`. When running from source, start it from the repository folder and do not copy `senandung.py` alone.
- **Arabic lines have no romanization**: this is intentional (see [Romanization](#romanization)).
- **Romanization looks outdated or wrong**: delete the `*.romaji.v*.lrc` file of that song in the lyrics folder; it is created again on the next play.
- **Log on Windows** (when running without a console): `%LOCALAPPDATA%\senandung.log`.
- **SmartScreen warns when opening the Setup `.exe`** (Windows): the file is not signed. Click **More info**, then **Run anyway**.
- **"running scripts is disabled on this system"** (Windows): run the `.ps1` with `powershell -ExecutionPolicy Bypass -File ...`.
- **`.ps1` uninstall stops with "The folder could not be removed"** (Windows): Senandung is still running. Quit it from the tray icon and try again.
- **GitHub Actions fails or no release appears**: open the *Actions* tab and look at the red step. Make sure the tag points to a commit that already has the fix (see *Publishing a new release*).

## Credits and notes

- Synced lyrics come from [LRCLIB](https://lrclib.net), an open service. Lyrics are the property of their copyright holders; this app only displays them for personal use and does not ship any lyrics in the repository.
- Built with [Qt for Python (PySide6)](https://doc.qt.io/qtforpython-6/).
- Developed with the help of an AI assistant ([Claude](https://www.anthropic.com/claude) by Anthropic) for code, installers, and documentation. All output was reviewed and tested by the maintainer.
- License: [GPL-3.0-or-later](LICENSE).

## Contributing

Issues and pull requests are welcome. Most changes are local: romanization lives in `romanize/`, player backends in `players/` (see *Repository layout*). When reporting a problem, please include your OS, Python version, player name and the output of `--list-players`.
