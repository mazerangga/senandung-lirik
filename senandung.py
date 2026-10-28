#!/usr/bin/env python3
"""Senandung - synced, transparent on-screen lyrics for your desktop (a lyrics overlay).

Reads the song playing in your media player, fetches time-stamped lyrics (.lrc) and shows them as a
transparent, always-on-top overlay with karaoke-style highlighting. No plugin needed in the player.
Runs on Linux (playerctl / MPRIS) and Windows (Windows Media Session, AIMP Remote API).

Two display modes:
  * scroll : several lines, the active line stays centered and scrolls smoothly
  * double : MiniLyrics style - two alternating lines (top-left / bottom-right), karaoke color fill

Requires  : Python 3.10+, PySide6;  Linux: playerctl;  Windows: winrt-* packages
Players   : auto-detected (Spotify, AIMP, foobar2000, MusicBee, VLC, ...). Set priority and blacklist
            in Settings; --list-players shows which players are visible
Optional  : pykakasi pypinyin korean-romanizer unidecode   (romanization)
Run       : python3 senandung.py            (or --demo for a preview without a player)
            python3 senandung.py --x11      (Linux: via XWayland - remembers position, stays on top)

Controls  : drag = move | drag bottom-right corner = resize | mouse wheel = shift lyric timing
            double-click = switch mode | right-click / tray icon = menu
            right-click menu: Search lyrics online... / Open lyrics file (.lrc)... (auto-renamed)
            X button (or close) = hide to the system tray; reappears automatically on song change
Language  : UI is available in Indonesian and English (follows the system locale; change it in Settings)
"""
import asyncio
import bisect
import hashlib
import json
import math
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PySide6.QtCore import QLocale, QObject, QPointF, QProcess, QRectF, QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (QBrush, QColor, QDesktopServices, QFont, QFontMetricsF, QGuiApplication, QIcon, QImage,
                           QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QCheckBox, QColorDialog, QComboBox, QDialog,
                               QDialogButtonBox, QFileDialog, QFontComboBox, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QProgressBar, QPushButton,
                               QSpinBox, QSystemTrayIcon, QToolTip, QVBoxLayout, QWidget)

APP_ID = "senandung"
APP_VERSION = "dev"          # diisi otomatis dari tag rilis oleh tools/stamp_version.py (CI); "dev" = tanpa cek update
REPO_URL = "https://github.com/mazerangga/senandung-lirik"
LATEST_API = "https://api.github.com/repos/mazerangga/senandung-lirik/releases/latest"
UPDATE_EVERY_S = 24 * 3600   # cek versi baru paling sering sekali sehari
UA = "senandung/1.0 (https://github.com/mazerangga/senandung-lirik)"

DEFAULTS = {
    "mode": "scroll",            # scroll | double
    "language": "auto",          # auto (ikut bahasa sistem) | id | en
    "font_family": "",
    "font_size": 26,
    "text_color": "#ffffff",
    "hl_color": "#1ed760",      # warna font sorot (baris aktif di mode scroll)
    "kara_color": "",           # warna isi karaoke; kosong = ikut hl_color
    "line_spacing": 100,        # jarak antar baris, persen (100 = bawaan)
    "outline": True,
    "wipe": True,                # efek isi warna per baris (mode dua baris & baris aktif)
    "offset_ms": 0,
    "romaji": "romaji",          # off | romaji | both
    "align": "zigzag",           # left | center | right | zigzag (zigzag = gaya MiniLyrics)
    "players": "spotify,aimp,foobar2000,musicbee,winamp,vlc,mpv,amarok",  # prioritas (urutan)
    "strict_players": False,     # True = hanya pemutar di daftar "players" yang dipakai
    "blacklist": "chrome,chromium,msedge,firefox,brave,opera,vivaldi",    # pemutar yang diabaikan
    "lyrics_dir": "~/lyrics",
    "save_local": True,
    "check_updates": True,       # beri tahu bila ada rilis baru di GitHub (hanya memberi tahu, tidak mengunduh)
    "last_update_check": "",     # epoch detik cek terakhir (teks)
    "update_latest": "",         # tag rilis terbaru yang pernah terlihat, mis. v1.2
    "last_browse_dir": "",       # folder terakhir saat memilih file lirik
    "gradient": True,            # teks gradien mengkilap ala MiniLyrics
    "on_top": True,              # selalu di atas (keep above)
    "auto_show": True,           # muncul lagi otomatis saat lagu berganti setelah ditutup ke tray
    "width": 820,                # ukuran mode scroll
    "height": 280,
    "dwidth": 780,               # ukuran mode dua baris
    "dheight": 130,
    "pos_x": -1,                 # posisi jendela (hanya bisa diingat di mode X11/XWayland)
    "pos_y": -1,
}


# --------------------------------------------------------------------- bahasa / language
# Menambah bahasa baru: tambahkan kode bahasa di LANGS, di combo Pengaturan (SettingsDialog.lang_keys),
# lalu isi satu entri per kunci di STRINGS. Kunci yang belum diterjemahkan jatuh ke bahasa Inggris.
LANGS = ("id", "en")
_lang = "en"

STRINGS = {
    # --- toolbar (tooltip)
    "tip_prev": {"id": "Lagu sebelumnya", "en": "Previous track"},
    "tip_play": {"id": "Putar / jeda", "en": "Play / pause"},
    "tip_next": {"id": "Lagu berikutnya", "en": "Next track"},
    "tip_mode": {"id": "Ganti mode scroll / dua baris", "en": "Switch scroll / two-line mode"},
    "tip_lock": {"id": "Kunci (buka kunci lewat menu ikon tray)",
                 "en": "Lock (unlock from the tray icon menu)"},
    "tip_gear": {"id": "Pengaturan", "en": "Settings"},
    "tip_close": {"id": "Sembunyikan ke system tray", "en": "Hide to system tray"},
    # --- pesan singkat di jendela (toast) dan status
    "mode_double": {"id": "Mode dua baris", "en": "Two-line mode"},
    "mode_scroll": {"id": "Mode scroll", "en": "Scroll mode"},
    "no_active_song": {"id": "Tidak ada lagu aktif", "en": "No active song"},
    "no_active_player": {"id": "Tidak ada pemutar aktif", "en": "No active player"},
    "not_lrc": {"id": "Bukan lirik .lrc bertanda waktu ([mm:ss.xx])",
                "en": "Not a timestamped .lrc file ([mm:ss.xx])"},
    "save_failed": {"id": "Gagal menyimpan: {err}", "en": "Could not save: {err}"},
    "read_failed": {"id": "Gagal membaca file: {err}", "en": "Could not read file: {err}"},
    "loading": {"id": "Memuat lirik…", "en": "Loading lyrics…"},
    "searching": {"id": "Mencari lirik…", "en": "Searching for lyrics…"},
    "not_found": {"id": "Lirik tidak ditemukan", "en": "Lyrics not found"},
    "lyrics_replaced": {"id": "Lirik diganti: {name}", "en": "Lyrics replaced: {name}"},
    "lyrics_saved": {"id": "Lirik disimpan: {name}", "en": "Lyrics saved: {name}"},
    "ignored": {"id": "Diabaikan: {name}", "en": "Ignored: {name}"},
    "demo_no_player": {"id": "Mode demo: tidak ada pemutar", "en": "Demo mode: no player"},
    "locked_toast": {"id": "Terkunci: buka lewat menu ikon tray",
                     "en": "Locked: unlock from the tray icon menu"},
    "offset_toast": {"id": "Geser waktu: {v} ms", "en": "Time offset: {v} ms"},
    "offset_saved": {"id": "Geser waktu disimpan: {v} ms", "en": "Time offset saved: {v} ms"},
    "tray_msg": {"id": "Masih berjalan di system tray.", "en": "Still running in the system tray."},
    "tray_msg_auto": {"id": " Akan muncul lagi otomatis saat lagu berganti.",
                      "en": " It will reappear automatically when the song changes."},
    # --- menu klik kanan / tray
    "m_scroll": {"id": "Mode scroll", "en": "Scroll mode"},
    "m_double": {"id": "Mode dua baris", "en": "Two-line mode"},
    "m_lock": {"id": "Kunci (klik tembus)", "en": "Lock (click-through)"},
    "m_top": {"id": "Selalu di atas", "en": "Always on top"},
    "m_auto": {"id": "Muncul otomatis saat lagu berganti", "en": "Reappear when the song changes"},
    "m_boot": {"id": "Mulai bersama Windows", "en": "Start with Windows"},
    "m_ignore_named": {"id": "Abaikan pemutar ini ({name})", "en": "Ignore this player ({name})"},
    "m_ignore": {"id": "Abaikan pemutar saat ini", "en": "Ignore current player"},
    "m_search": {"id": "Cari lirik online…", "en": "Search lyrics online…"},
    "m_browse": {"id": "Buka file lirik (.lrc)…", "en": "Open lyrics file (.lrc)…"},
    "m_settings": {"id": "Pengaturan…", "en": "Settings…"},
    "m_toggle": {"id": "Tampilkan / sembunyikan", "en": "Show / hide"},
    "m_quit": {"id": "Keluar", "en": "Quit"},
    "m_update": {"id": "Versi baru tersedia: {ver} (buka halaman unduh)",
                 "en": "New version available: {ver} (open download page)"},
    "update_toast": {"id": "Versi baru {ver} tersedia, lihat menu ikon tray",
                     "en": "New version {ver} available, see the tray menu"},
    "check_updates": {"id": "Cek versi baru otomatis (1 permintaan ke GitHub per hari)",
                      "en": "Check for new versions automatically (one request to GitHub per day)"},
    # --- dialog Tentang / update
    "m_about": {"id": "Tentang Senandung…", "en": "About Senandung…"},
    "about_title": {"id": "Tentang Senandung", "en": "About Senandung"},
    "about_desc": {
        "id": "Senandung menampilkan lirik tersinkron di layar desktop: overlay transparan bergaya "
              "karaoke yang selalu di atas. Lirik diambil otomatis dari LRCLIB untuk lagu yang sedang "
              "diputar di Spotify, AIMP, foobar2000, MusicBee, VLC, dan pemutar lainnya, tanpa plugin.",
        "en": "Senandung shows synced lyrics on your desktop: a transparent, always-on-top, karaoke-style "
              "overlay. Lyrics are fetched automatically from LRCLIB for the song playing in Spotify, "
              "AIMP, foobar2000, MusicBee, VLC and other players, with no plugin needed."},
    "about_version": {"id": "Versi {v}", "en": "Version {v}"},
    "about_dev": {"id": "dev (build lokal)", "en": "dev (local build)"},
    "about_status_dev": {"id": "Build lokal: pengecekan update dimatikan.",
                         "en": "Local build: update checks are disabled."},
    "about_checking": {"id": "Memeriksa pembaruan…", "en": "Checking for updates…"},
    "about_uptodate": {"id": "Kamu sudah memakai versi terbaru.", "en": "You are up to date."},
    "about_available": {"id": "Versi baru tersedia: {ver}", "en": "New version available: {ver}"},
    "about_check_failed": {"id": "Gagal memeriksa pembaruan: {err}",
                           "en": "Could not check for updates: {err}"},
    "about_check": {"id": "Cek pembaruan", "en": "Check for updates"},
    "about_update_now": {"id": "Update sekarang", "en": "Update now"},
    "about_update_tip_manual": {
        "id": "Instalasi ini tidak bisa update sendiri: tombol membuka halaman unduh.",
        "en": "This install cannot update itself: the button opens the download page."},
    "about_downloading": {"id": "Mengunduh pembaruan… {p}%", "en": "Downloading update… {p}%"},
    "about_update_failed": {"id": "Update gagal: {err}", "en": "Update failed: {err}"},
    # --- dialog pengaturan
    "settings_title": {"id": "Pengaturan Senandung", "en": "Senandung Settings"},
    "lang_auto": {"id": "Otomatis (ikut sistem)", "en": "Automatic (follow system)"},
    "lbl_language": {"id": "Bahasa / Language", "en": "Bahasa / Language"},
    "lbl_mode": {"id": "Mode", "en": "Mode"},
    "mode_item_scroll": {"id": "Scroll", "en": "Scroll"},
    "mode_item_double": {"id": "Dua baris (gaya MiniLyrics)", "en": "Two lines (MiniLyrics style)"},
    "lbl_font": {"id": "Font", "en": "Font"},
    "use_font": {"id": "Pakai font ini (kalau tidak, font sistem)",
                 "en": "Use this font (otherwise the system font)"},
    "lbl_font_size": {"id": "Ukuran font", "en": "Font size"},
    "lbl_text_color": {"id": "Warna font dasar", "en": "Base font color"},
    "lbl_hl_color": {"id": "Warna font sorot (baris aktif)", "en": "Highlight font color (active line)"},
    "lbl_kara_color": {"id": "Warna font karaoke (isi per baris)", "en": "Karaoke font color (per-line fill)"},
    "kara_follow": {"id": "Ikuti warna sorot", "en": "Follow highlight"},
    "kara_follow_tip": {"id": "Kosongkan warna karaoke: pakai warna font sorot",
                        "en": "Clear the karaoke color: use the highlight font color"},
    "lbl_line_spacing": {"id": "Jarak antar baris", "en": "Line spacing"},
    "outline": {"id": "Garis tepi teks", "en": "Text outline"},
    "gradient": {"id": "Teks gradien mengkilap", "en": "Glossy gradient text"},
    "wipe": {"id": "Efek isi warna per baris (karaoke)", "en": "Per-line color fill effect (karaoke)"},
    "on_top": {"id": "Selalu di atas jendela lain (keep above)",
               "en": "Always on top of other windows"},
    "auto_show": {"id": "Muncul lagi otomatis saat lagu berganti (setelah ditutup ke tray)",
                  "en": "Reappear automatically when the song changes (after hiding to tray)"},
    "lbl_align": {"id": "Perataan", "en": "Alignment"},
    "align_left": {"id": "Kiri", "en": "Left"},
    "align_center": {"id": "Tengah", "en": "Center"},
    "align_right": {"id": "Kanan", "en": "Right"},
    "align_zigzag": {"id": "Zigzag (atas kiri, bawah kanan)", "en": "Zigzag (top left, bottom right)"},
    "lbl_romaji": {"id": "Romanisasi", "en": "Romanization"},
    "romaji_off": {"id": "Mati (teks asli)", "en": "Off (original text)"},
    "romaji_only": {"id": "Hanya romaji", "en": "Romanization only"},
    "romaji_both": {"id": "Asli + romaji", "en": "Original + romanization"},
    "lbl_offset": {"id": "Geser waktu", "en": "Time offset"},
    "lbl_players": {"id": "Pemutar prioritas", "en": "Priority players"},
    "players_ph": {"id": "spotify,aimp,foobar2000 (urutan = prioritas)",
                   "en": "spotify,aimp,foobar2000 (order = priority)"},
    "players_tip": {"id": "Pemutar yang diutamakan bila beberapa aktif bersamaan.\n"
                          "Pemutar lain tetap terdeteksi kecuali mode ketat dicentang.",
                    "en": "Preferred players when several are active at once.\n"
                          "Other players are still detected unless strict mode is checked."},
    "strict": {"id": "Hanya pakai pemutar di daftar prioritas (abaikan yang lain)",
               "en": "Only use players in the priority list (ignore the others)"},
    "lbl_blacklist": {"id": "Blacklist pemutar", "en": "Player blacklist"},
    "black_tip": {"id": "Pemutar yang namanya mengandung kata ini tidak akan dibaca.\n"
                        "Pisahkan dengan koma. Lihat nama pemutar: senandung.py --list-players",
                  "en": "Players whose name contains one of these words are never read.\n"
                        "Separate with commas. To see player names: senandung.py --list-players"},
    "lbl_folder": {"id": "Folder lirik", "en": "Lyrics folder"},
    "save_local": {"id": "Simpan lirik sebagai file .lrc", "en": "Save lyrics as .lrc files"},
    # --- dialog cari lirik online
    "search_title": {"id": "Cari lirik online (LRCLIB)", "en": "Search lyrics online (LRCLIB)"},
    "lbl_artist": {"id": "Artis", "en": "Artist"},
    "lbl_title": {"id": "Judul", "en": "Title"},
    "search_btn": {"id": "Cari", "en": "Search"},
    "search_hint": {"id": "Isi artis dan/atau judul, lalu tekan Cari.",
                    "en": "Enter an artist and/or a title, then press Search."},
    "search_need": {"id": "Isi artis dan/atau judul dulu.", "en": "Enter an artist and/or a title first."},
    "searching_dots": {"id": "Mencari…", "en": "Searching…"},
    "search_failed": {"id": "Gagal mencari: {err}", "en": "Search failed: {err}"},
    "found_n": {"id": "{n} lirik tersinkron ditemukan. Klik dua kali untuk memakai.",
                "en": "{n} synced lyrics found. Double-click one to use it."},
    "none_found": {"id": "Tidak ada lirik tersinkron yang cocok.", "en": "No matching synced lyrics found."},
    "use_lyrics": {"id": "Pakai lirik ini", "en": "Use these lyrics"},
    "close": {"id": "Tutup", "en": "Close"},
    # --- dialog buka file lirik
    "browse_title": {"id": "Pilih file lirik untuk: {artist} - {title}",
                     "en": "Choose a lyrics file for: {artist} - {title}"},
    "file_filter": {"id": "Lirik (*.lrc *.txt);;Semua file (*)", "en": "Lyrics (*.lrc *.txt);;All files (*)"},
    # --- baris perintah (--list-players dan pesan galat saat start)
    "playerctl_missing": {"id": "playerctl tidak ditemukan. Pasang dulu (mis. sudo pacman -S playerctl).",
                          "en": "playerctl not found. Please install it first (e.g. sudo pacman -S playerctl)."},
    "unsupported": {"id": "Platform ini belum didukung (hanya Linux dan Windows). Coba --demo untuk pratinjau.",
                    "en": "This platform is not supported yet (Linux and Windows only). Try --demo for a preview."},
    "playerctl_failed": {"id": "playerctl gagal dijalankan: {err}", "en": "Could not run playerctl: {err}"},
    "smtc_unreadable": {"id": "(SMTC tidak bisa dibaca: {err})", "en": "(Could not read SMTC: {err})"},
    "list_only": {"id": "--list-players hanya untuk Linux dan Windows.",
                  "en": "--list-players is only available on Linux and Windows."},
    "no_players": {"id": "Tidak ada pemutar media yang terdeteksi. Putar sebuah lagu lalu coba lagi.",
                   "en": "No media player detected. Play a song and try again."},
    "verdict_used": {"id": "DIPAKAI", "en": "USED"},
    "verdict_black": {"id": "DIABAIKAN (blacklist)", "en": "IGNORED (blacklist)"},
    "verdict_strict": {"id": "DIABAIKAN (mode ketat: tidak ada di daftar prioritas)",
                       "en": "IGNORED (strict mode: not in the priority list)"},
    "priority_line": {"id": "Prioritas : {items}   (ketat: {strict})",
                      "en": "Priority  : {items}   (strict: {strict})"},
    "blacklist_line": {"id": "Blacklist : {items}", "en": "Blacklist : {items}"},
    "yes": {"id": "ya", "en": "yes"},
    "no": {"id": "tidak", "en": "no"},
}


def system_lang():
    """Bahasa sistem -> 'id' bila lokal Indonesia, selain itu 'en'."""
    return "id" if QLocale.system().name().lower().startswith(("id", "in_")) else "en"


def set_language(pref):
    """pref: 'auto' | 'id' | 'en'. Nilai tak dikenal dianggap 'auto'."""
    global _lang
    _lang = pref if pref in LANGS else system_lang()


def tr(key, **kw):
    entry = STRINGS[key]
    text = entry.get(_lang) or entry["en"]
    return text.format(**kw) if kw else text


# --------------------------------------------------------------------- konfigurasi
class Cfg:
    def __init__(self):
        self.s = QSettings(APP_ID, APP_ID)

    def get(self, key):
        d = DEFAULTS[key]
        t = bool if isinstance(d, bool) else int if isinstance(d, int) else str
        return self.s.value(key, d, type=t)

    def set(self, key, value):
        self.s.setValue(key, value)

    def snapshot(self):
        return {k: self.get(k) for k in DEFAULTS}


# --------------------------------------------------------------------- lirik & romanisasi
def parse_lrc(text):
    out = []
    rx = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")
    for line in text.splitlines():
        times = [int(m.group(1)) * 60000 + round(float(m.group(2)) * 1000) for m in rx.finditer(line)]
        body = re.sub(r"\[[^\]]*\]", "", line).strip()
        out += [(t, body) for t in times]
    out.sort(key=lambda x: x[0])
    return out


def fmt_time(ms):
    cs = round(ms / 10)
    return f"[{cs // 6000:02d}:{cs % 6000 // 100:02d}.{cs % 100:02d}]"


def lrc_name(artist, title):
    n = re.sub(r"[\/\\:*?\"<>|\r\n\t]", " ", f"{artist} - {title}")
    n = re.sub(r"\s+", " ", n).strip()[:150].strip()
    return n + ".lrc"


from romanize import NON_LATIN, ROMAN_VERSION  # noqa: E402  (paket romanize/)
from romanize import romanize_lines as _romanize_inproc  # noqa: E402


def romanize_lines(lines):
    """Romanisasi di proses anak sekali-pakai. pykakasi (~100 MB) dan pypinyin (~50 MB) memuat
    kamus besar yang tidak pernah dilepas ke OS; dengan proses anak, memori kembali begitu selesai.
    Hasilnya sudah di-cache ke berkas .romaji.vN.lrc, jadi biaya start proses hanya sekali per lagu."""
    import subprocess
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--romanize-worker"]
    else:
        cmd = [sys.executable, str(Path(__file__).resolve()), "--romanize-worker"]
    kw = {"creationflags": 0x08000000} if sys.platform == "win32" else {}   # CREATE_NO_WINDOW
    try:
        r = subprocess.run(cmd, input=json.dumps(lines).encode("utf-8"), capture_output=True,
                           timeout=120, **kw)
        if r.returncode == 0:
            res = json.loads(r.stdout.decode("utf-8"))
            if isinstance(res, list) and len(res) == len(lines):
                return res
        print(f"[senandung] romanize worker failed (rc={r.returncode}): "
              f"{r.stderr.decode('utf-8', 'replace')[-300:]}", file=sys.stderr)
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        print(f"[senandung] romanize worker error: {e}", file=sys.stderr)
    return _romanize_inproc(lines)            # cadangan: di proses utama (lebih boros memori)


def _romanize_worker():
    """Mode --romanize-worker: baca JSON list[str] dari stdin, tulis JSON list[str] ke stdout."""
    fin = open(0, "rb", closefd=False)        # fd langsung: sys.stdin/stdout bisa None di exe --windowed
    fout = open(1, "wb", closefd=False)
    lines = json.loads(fin.read().decode("utf-8"))
    fout.write(json.dumps(_romanize_inproc(lines), ensure_ascii=False).encode("utf-8"))
    fout.flush()


def romaji_name(lrc_filename):
    """Nama file cache romanisasi; memuat ROMAN_VERSION supaya cache lama otomatis tidak dipakai."""
    return lrc_filename.replace(".lrc", f".romaji.v{ROMAN_VERSION}.lrc")


def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


TAG_RE = re.compile(r"[vV]?\d+(?:\.\d+)*")


def parse_ver(s):
    """'v1.2.0' -> (1, 2). Nol di belakang dibuang supaya 1.1 == 1.1.0."""
    if not TAG_RE.fullmatch((s or "").strip()):
        return ()
    v = [int(x) for x in s.strip().lstrip("vV").split(".")]
    while len(v) > 1 and v[-1] == 0:
        v.pop()
    return tuple(v)


def is_newer(latest, current):
    a, b = parse_ver(latest), parse_ver(current)
    return bool(a) and bool(b) and a > b


class UpdateChecker(QObject):
    """Memberi tahu bila ada rilis lebih baru. Hanya MEMBERI TAHU: tidak mengunduh atau memasang apa pun;
    klik pada menu membuka halaman rilis di browser. Paling sering sekali sehari, di thread terpisah,
    gagal diam-diam (offline, batas API, belum ada rilis)."""
    checked = Signal(str, str)           # tag, url dari GitHub (dikirim ke thread utama)
    failed = Signal(str)                 # pesan galat (hanya didengar dialog Tentang)

    def start(self, cfg, force=False):
        """force=True: cek sekarang juga (dari dialog Tentang), tanpa batas sekali sehari dan
        tanpa melihat pengaturan cek otomatis, karena pengguna memintanya sendiri."""
        if APP_VERSION == "dev" or (not force and not cfg.get("check_updates")):
            return
        if not force:
            try:
                last = float(cfg.get("last_update_check") or 0)
            except ValueError:
                last = 0.0
            if time.time() - last < UPDATE_EVERY_S:
                return

        def run():
            try:
                d = http_json(LATEST_API)
                self.checked.emit(str(d.get("tag_name", "")), str(d.get("html_url", "")))
            except Exception as e:
                print(f"[senandung] update check skipped: {e}", file=sys.stderr)
                self.failed.emit(str(e))
        threading.Thread(target=run, daemon=True).start()


# --- update mandiri (tombol "Update sekarang"): hanya untuk AppImage dan Setup .exe Windows.
# Instalasi lain (skrip .sh/.ps1, portable, dari source) cukup membuka halaman rilis.
def install_kind():
    """'appimage' | 'winsetup' | '' (tidak bisa update sendiri)."""
    if IS_LINUX and os.environ.get("APPIMAGE"):
        return "appimage"
    if IS_WIN and getattr(sys, "frozen", False) and (Path(sys.executable).parent / "unins000.exe").is_file():
        return "winsetup"                # dipasang lewat Senandung-Setup-<versi>.exe (Inno Setup)
    return ""


def pick_asset(assets, kind):
    """(url, sha256) berkas rilis yang cocok, hanya dari alamat unduhan repo ini. (None, '') bila tak ada."""
    for a in assets or []:
        name = str(a.get("name", "")).lower()
        url = str(a.get("browser_download_url", ""))
        if not url.startswith(REPO_URL + "/releases/download/"):
            continue
        ok = (name.endswith(".appimage") if kind == "appimage"
              else name.startswith("senandung-setup") and name.endswith(".exe"))
        if ok:
            digest = str(a.get("digest") or "")
            return url, digest[7:] if digest.startswith("sha256:") else ""
    return None, ""


def download_file(url, dest, progress, want_sha=""):
    h = hashlib.sha256()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last = -1
    with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            got += len(chunk)
            pct = min(100, got * 100 // total) if total else 0
            if pct != last:
                last = pct
                progress(pct)
    if want_sha and h.hexdigest() != want_sha.lower():
        raise RuntimeError("checksum mismatch")


class SelfUpdater(QObject):
    progress = Signal(int)
    done = Signal(str, str)              # (galat, path berkas hasil); galat kosong = sukses

    def start(self, kind):
        def run():
            tmp = None
            try:
                url, sha = pick_asset(http_json(LATEST_API).get("assets"), kind)
                if not url:
                    raise RuntimeError("no matching file in the latest release")
                if kind == "appimage":
                    target = Path(os.environ["APPIMAGE"])
                    tmp = target.with_name(target.name + ".new")
                    download_file(url, tmp, self.progress.emit, sha)
                    if tmp.read_bytes()[:4] != b"\x7fELF":
                        raise RuntimeError("downloaded file is not an AppImage")
                    tmp.chmod(0o755)
                    os.replace(tmp, target)          # aman walau AppImage lama sedang berjalan
                    self.done.emit("", str(target))
                else:
                    tmp = Path(tempfile.gettempdir()) / urllib.parse.unquote(url.rsplit("/", 1)[-1])
                    download_file(url, tmp, self.progress.emit, sha)
                    self.done.emit("", str(tmp))
            except Exception as e:
                if tmp is not None and kind == "appimage":
                    tmp.unlink(missing_ok=True)
                self.done.emit(str(e), "")
        threading.Thread(target=run, daemon=True).start()



def _clean_title(title):
    """Buang bagian yang sering membuat pencarian gagal: (feat. ...), [Live], - Remastered, dll."""
    t = re.sub(r"[\(\[（【][^\)\]）】]*[\)\]）】]", " ", title)
    t = re.sub(r"\s+[-–—]\s+(remaster\w*|live|ver\w*|mono|stereo|single|radio|explicit|from)\b.*$", "",
               t, flags=re.IGNORECASE)
    t = re.sub(r"\s+(feat|ft)\.?\s.*$", "", t, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", t).strip() or title


def _first_artist(artist):
    """Artis pertama saja: 'A, B' / 'A & B' / 'A feat. B' -> 'A'."""
    a = re.split(r"\s*(?:,|;|/|&|\bfeat\.?|\bft\.?|、|，)\s*", artist, maxsplit=1, flags=re.IGNORECASE)[0]
    return a.strip() or artist


def _plain(text):
    """Huruf/angka saja, huruf kecil. Hanzi diubah ke pinyin tanpa nada (bila pypinyin ada)."""
    if HAN_RX.search(text):
        try:
            from pypinyin import Style, lazy_pinyin
            text = "".join(lazy_pinyin(text, style=Style.NORMAL))
        except Exception:
            pass
    return re.sub(r"[\W_]+", "", text.lower())


HAN_RX = re.compile("[\u3400-\u4dbf\u4e00-\u9fff]")


def _pick_synced(items, title, duration_s, loose=False):
    """Pilih lirik tersinkron terbaik dari hasil pencarian LRCLIB.
    Urutan: judul sama (pinyin dihitung sama) + durasi cocok -> durasi cocok (<=4 dtk)
    -> bila loose, hasil pertama."""
    items = [it for it in items if it.get("syncedLyrics")]
    if not items:
        return None
    want = _plain(title)

    def dd(it):
        d = it.get("duration") or 0
        return abs(d - duration_s) if duration_s > 0 and d else 9999

    same = [it for it in items if want and _plain(it.get("trackName") or "") == want]
    for pool in (same, items):
        pool = sorted(pool, key=dd)
        if pool and (dd(pool[0]) <= 4 or (pool is same and duration_s <= 0)):
            return pool[0]["syncedLyrics"]
    return items[0]["syncedLyrics"] if loose else None


_meta_cache = {}


def lrc_meta(path):
    """Tag [ar:] dan [ti:] dari kepala file .lrc -> (artis, judul); kosong bila tidak ada.
    Hanya 4 KB awal yang dibaca, hasilnya di-cache selama file tidak berubah."""
    try:
        st = path.stat()
        key = (str(path), st.st_mtime_ns, st.st_size)
        if key in _meta_cache:
            return _meta_cache[key]
        with open(path, "rb") as fh:
            data = fh.read(4096)
        for enc in ("utf-8-sig", "gb18030", "cp1252"):
            try:
                head = data.decode(enc)
                break
            except UnicodeDecodeError:
                head = ""
        ar = re.search(r"^\s*\[ar:([^\]]*)\]", head, re.IGNORECASE | re.MULTILINE)
        ti = re.search(r"^\s*\[ti:([^\]]*)\]", head, re.IGNORECASE | re.MULTILINE)
        _meta_cache[key] = (ar.group(1).strip() if ar else "", ti.group(1).strip() if ti else "")
        return _meta_cache[key]
    except OSError:
        return ("", "")


def add_lrc_tags(raw, artist, title):
    """Tambahkan [ar:] dan [ti:] di kepala teks .lrc bila belum ada (yang sudah ada tidak diubah),
    supaya file tetap dikenali lewat isinya sendiri."""
    def clean(v):
        return re.sub(r"[\[\]\r\n]+", " ", v).strip()
    head = []
    if artist.strip() and not re.search(r"^\s*\[ar:", raw, re.IGNORECASE | re.MULTILINE):
        head.append(f"[ar:{clean(artist)}]")
    if title.strip() and not re.search(r"^\s*\[ti:", raw, re.IGNORECASE | re.MULTILINE):
        head.append(f"[ti:{clean(title)}]")
    return ("\n".join(head) + "\n" + raw) if head else raw


def find_song_lrc(path, artist, title):
    """.lrc di folder file lagu. path = lokasi file lagu dari player ('' bila tidak diketahui)."""
    if not path:
        return None
    try:
        song = Path(path)
        same = song.with_suffix(".lrc")
        if same.is_file():
            return same
        hit = resolve_lrc(song.parent, artist, title)
        return hit if hit.is_file() else None
    except OSError:
        return None


def resolve_lrc(folder, artist, title):
    """File .lrc lokal untuk lagu ini. Urutan: nama persis 'Artis - Judul.lrc'; kalau tidak ada,
    cari di folder berdasarkan nama file DAN tag [ar:]/[ti:] di dalam file (huruf besar/kecil,
    tanda baca, hanzi vs pinyin tidak dipersoalkan). Bila file mencantumkan artis yang berbeda
    dari artis lagu, file itu ditolak. Bila tak ada yang cocok: nama persis."""
    exact = folder / lrc_name(artist, title)
    if exact.exists():
        return exact
    try:
        files = [f for f in folder.glob("*.lrc") if ".romaji" not in f.name.lower()]
    except OSError:
        return exact
    ct, ca, pa_full = _plain(_clean_title(title)), _plain(_first_artist(artist)), _plain(artist)
    if not files or not ct:
        return exact
    best, best_score = None, 0.0
    for f in files:
        m_ar, m_ti = lrc_meta(f)
        ar_first, ar_full = _plain(_first_artist(m_ar)), _plain(m_ar)
        artist_ok = bool((ca and ar_full and ca in ar_full) or (ar_first and pa_full and ar_first in pa_full))
        comparable = not (re.search(r"[^\x00-\x7f]", m_ar) or re.search(r"[^\x00-\x7f]", artist))
        if comparable and ar_full and ca and not artist_ok:
            continue          # file menyebut artis lain (sama-sama huruf Latin): bukan lagu ini
        st, mt = _plain(f.stem), _plain(_clean_title(m_ti)) if m_ti else ""
        if st in (ca + ct, ct + ca):
            score = 3.0
        elif mt and mt == ct:
            score = 2.5                                # judul di dalam file cocok
        elif st == ct:
            score = 2.0
        elif len(ct) >= 4 and (ct in st or (mt and ct in mt)):
            score = 1.0 + (0.5 if ca and ca in st else 0.0)
        else:
            continue
        if artist_ok:
            score += 0.7                               # artis di dalam file ikut cocok
        if score > best_score or (score == best_score and best and f.stat().st_mtime > best.stat().st_mtime):
            best, best_score = f, score
    return best or exact


def fetch_online(artist, title, duration_s):
    base = "https://lrclib.net/api/"
    ctitle, cartist = _clean_title(title), _first_artist(artist)

    # 1. cocok persis (get): nama asli, lalu nama yang sudah dibersihkan
    for a, t in dict.fromkeys([(artist, title), (cartist, ctitle)]):
        q = urllib.parse.urlencode({"artist_name": a, "track_name": t})
        try:
            res = http_json(f"{base}get?{q}" + (f"&duration={duration_s}" if duration_s > 0 else ""))
            if res.get("syncedLyrics"):
                return res["syncedLyrics"]
        except Exception as e:
            print(f"[senandung] LRCLIB get: {e}", file=sys.stderr)

    # 2. pencarian: artis+judul dulu (hasil pertama boleh dipakai), lalu teks bebas
    #    (hasil harus cocok judulnya atau durasinya, supaya tidak salah lagu)
    tries = [({"artist_name": artist, "track_name": title}, True),
             ({"artist_name": cartist, "track_name": ctitle}, True),
             ({"q": f"{cartist} {ctitle}"}, False),
             ({"q": ctitle}, False)]
    seen = set()
    for params, loose in tries:
        key = tuple(sorted(params.items()))
        if key in seen:
            continue
        seen.add(key)
        try:
            found = _pick_synced(http_json(f"{base}search?" + urllib.parse.urlencode(params)),
                                 ctitle, duration_s, loose)
        except Exception as e:
            print(f"[senandung] LRCLIB search: {e}", file=sys.stderr)
            continue
        if found:
            return found
    return None


def read_text_file(path):
    """Baca file teks dengan penanganan encoding umum (UTF-8/UTF-8 BOM, UTF-16 BOM, lalu cp1252)."""
    data = Path(path).read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", "replace")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    try:
        return data.decode("gb18030")            # banyak file .lrc Mandarin lama berbentuk GBK
    except UnicodeDecodeError:
        return data.decode("cp1252", "replace")


def search_lrclib(artist, title):
    """Cari lirik tersinkron di LRCLIB. Mengembalikan list item (hanya yang punya syncedLyrics)."""
    base = "https://lrclib.net/api/search?"
    tries = []
    if artist and title:
        tries.append({"artist_name": artist, "track_name": title})
        tries.append({"q": f"{artist} {title}"})
    else:
        tries.append({"q": artist or title})
    out, seen = [], set()
    for params in tries:
        for it in http_json(base + urllib.parse.urlencode(params)):
            if it.get("syncedLyrics") and it.get("id") not in seen:
                seen.add(it.get("id"))
                out.append(it)
        if out:
            break
    return out[:40]


def load_lyrics(artist, title, duration_s, cfg, path=""):
    """Dijalankan di thread terpisah. Mengembalikan list dict {t, text, roman}."""
    folder = Path(os.path.expanduser(cfg["lyrics_dir"]))
    name = lrc_name(artist, title)
    lrc = folder / name                       # nama baku untuk menyimpan hasil unduhan
    found = resolve_lrc(folder, artist, title)
    # file .lrc di folder lagu (lagu offline): sama nama dengan file lagu, atau cocok lewat nama/tag.
    # Bila ada juga di folder lirik, yang lebih baru dipakai (pilihan manual terakhir menang).
    song_lrc = find_song_lrc(path, artist, title)
    if song_lrc and (not found.exists() or song_lrc.stat().st_mtime > found.stat().st_mtime):
        found = song_lrc
    parsed = []
    
    # 1. Siapkan wadah untuk teks lirik mentah dan nilai offset
    raw_text = ""      
    offset_val = 0     

    if found.exists():
        # 2. Tampung ke raw_text dulu agar bisa di-regex nanti
        raw_text = read_text_file(found)
        parsed = parse_lrc(raw_text)
        if parsed:
            print(f"[senandung] lyrics loaded from local file: {found.name}")
        else:
            print(f"[senandung] local file has no timestamped lines: {found.name}", file=sys.stderr)
            
    if not parsed:
        # 3. Tampung hasil online ke raw_text
        fetched = fetch_online(artist, title, duration_s)
        raw_text = fetched if fetched else ""
        parsed = parse_lrc(raw_text) if raw_text else []
        
        print(f"[senandung] LRCLIB: {len(parsed)} lines for {artist} - {title}")
        if parsed and cfg["save_local"]:
            try:
                folder.mkdir(parents=True, exist_ok=True)
                lrc.write_text(raw_text, "utf-8")
            except OSError as e:
                print(f"[senandung] failed to save: {e}", file=sys.stderr)

    # 4. Cari tag offset dari teks mentah (lokal maupun online)
    if raw_text:
        offset_match = re.search(r'\[offset:([+-]?\d+)\]', raw_text, re.IGNORECASE)
        offset_val = int(offset_match.group(1)) if offset_match else 0

    entries = [{"t": t, "text": x, "roman": ""} for t, x in parsed]

    # 5. Titipkan nilai offset ke baris lirik pertama sebagai metadata rahasia
    if entries:
        entries[0]["_offset"] = offset_val

    # --- Sisa kode romaji di bawah ini tidak berubah ---
    if entries and cfg["romaji"] != "off" and any(NON_LATIN.search(e["text"]) for e in entries):
        rfile = folder / romaji_name(name)
        done = False
        if cfg["save_local"] and rfile.exists():
            rl = parse_lrc(rfile.read_text("utf-8", errors="replace"))
            if len(rl) == len(entries) and all(abs(a["t"] - b[0]) <= 30 for a, b in zip(entries, rl)):
                for e, (_, r) in zip(entries, rl):
                    e["roman"] = "" if r == e["text"] else r
                done = True
                print("[senandung] romanization loaded from local file")
        if not done:
            res = romanize_lines([e["text"] for e in entries])
            for e, r in zip(entries, res):
                e["roman"] = r
            if any(res) and cfg["save_local"]:
                try:
                    rows = [fmt_time(e["t"]) + (e["roman"] or e["text"]) for e in entries]
                    folder.mkdir(parents=True, exist_ok=True)
                    rfile.write_text("\n".join(rows) + "\n", "utf-8")
                except OSError as e:
                    print(f"[senandung] failed to save romanization: {e}", file=sys.stderr)
                    
    return entries


class Loader(QObject):
    done = Signal(str, object)

    def load(self, key, artist, title, duration_s, cfg, path=""):
        def run():
            try:
                self.done.emit(key, load_lyrics(artist, title, duration_s, cfg, path))
            except Exception as e:  # jangan sampai thread mati diam-diam
                print(f"[senandung] failed to load lyrics: {e}", file=sys.stderr)
                self.done.emit(key, [])
        threading.Thread(target=run, daemon=True).start()


# --------------------------------------------------------------------- pemutar (backend: paket players/)
from players import (IS_LINUX, IS_WIN, aimp_read, make_backend, rank_player,  # noqa: E402
                     short_name, split_list)


def list_players():
    """--list-players: tampilkan semua pemutar yang terlihat beserta keputusan filternya."""
    cfg = Cfg()
    prefer, black, strict = (split_list(cfg.get("players")), split_list(cfg.get("blacklist")),
                             cfg.get("strict_players"))
    rows = []                                                   # (nama, status, judul)
    if IS_LINUX:
        import subprocess
        fmt = "{{playerName}}|||{{status}}|||{{artist}}|||{{title}}"
        try:
            out = subprocess.run(["playerctl", "-a", "metadata", "--format", fmt],
                                 capture_output=True, text=True, timeout=5).stdout
        except (OSError, subprocess.SubprocessError) as e:
            sys.exit(tr("playerctl_failed", err=e))
        for line in out.splitlines():
            p = line.split("|||")
            if len(p) >= 4:
                rows.append((p[0], p[1], f"{p[2]} - {p[3]}"))
    elif IS_WIN:
        async def go():
            from winrt.windows.media.control import \
                GlobalSystemMediaTransportControlsSessionManager as Manager
            mgr = await Manager.request_async()
            for s in mgr.get_sessions():
                st = int(s.get_playback_info().playback_status)
                props = await s.try_get_media_properties_async()
                rows.append((s.source_app_user_model_id or "?",
                             {4: "Playing", 5: "Paused"}.get(st, "Stopped"),
                             f"{props.artist} - {props.title}"))
        try:
            asyncio.run(go())
        except Exception as e:
            print(tr("smtc_unreadable", err=e))
        a = aimp_read()
        if a:
            rows.append(("AIMP (Remote API)", a["state"], f"{a['artist']} - {a['title']}"))
    else:
        sys.exit(tr("list_only"))
    if not rows:
        print(tr("no_players"))
    for name, state, track in rows:
        key = "aimp" if name.startswith("AIMP (") else name
        r = rank_player(key, prefer, black, strict)
        if r is not None:
            verdict = tr("verdict_used")
        elif any(b in key.lower() for b in black):
            verdict = tr("verdict_black")
        else:
            verdict = tr("verdict_strict")
        print(f"{verdict:<10} | {name} | {state} | {track}")
    print("\n" + tr("priority_line", items=", ".join(prefer) or "-",
                      strict=tr("yes" if strict else "no")))
    print(tr("blacklist_line", items=", ".join(black) or "-"))



# --------------------------------------------------------------------- jendela OSD
DEMO = [
    (0, "夜に駆ける", "Yoru ni kakeru"), (4000, "沈むように溶けてゆくように", "Shizumu you ni tokete yuku you ni"),
    (9000, "二人だけの空が広がる夜に", "Futari dake no sora ga hirogaru yoru ni"),
    (14000, "「さよなら」だけだった", "\"Sayonara\" dake datta"),
    (19000, "その一言で全てが分かった", "Sono hitokoto de subete ga wakatta"),
    (24000, "日が沈み出した空と君の姿", "Hi ga shizumi dashita sora to kimi no sugata"),
    (29000, "フェンス越しに重なっていた", "Fensu goshi ni kasanatte ita"),
    (34000, "初めて会った日から", "Hajimete atta hi kara"),
]

TB_H = 26                                    # tinggi strip toolbar (mode dua baris menyisakannya)
# Interval tick (ms). Makin besar = makin hemat CPU, animasi makin kurang halus.
TICK_BUSY_MS = 50                            # lagu main / scroll bergerak (~20 fps; 33 = ~30 fps)
TICK_IDLE_MS = 150                           # diam (dijeda / tanpa animasi)
TICK_HIDDEN_MS = 250                         # jendela disembunyikan ke tray: tidak ada yang digambar
FILL_CACHE_BYTES = 24 * 1024 * 1024          # batas memori cache isian teks (pixmap)
TOOLBAR = ["prev", "play", "next", "mode", "lock", "gear", "close"]


class OSD(QWidget):
    def __init__(self, cfg, demo=False):
        super().__init__()
        self.cfg = cfg
        self.demo = demo
        self.s = cfg.snapshot()
        self.setWindowTitle("Senandung")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setMinimumSize(260, 72)
        self.locked = False
        self.quitting = False
        self.hidden_by_user = False
        self.tray = None
        self.tray_menu = None
        self._hint_shown = False
        self._flags()
        self.resize(*self._saved_size(self.s["mode"]))
        # Wayland murni melarang aplikasi menentukan posisi; di X11/XWayland/Windows boleh.
        self.can_place = QGuiApplication.platformName() != "wayland"
        self.pos_timer = QTimer(self, singleShot=True, interval=500, timeout=self.save_pos)
        self.local_offset = 0                                   # geser waktu lagu ini (ms), disimpan di .lrc
        self._offset_pending = None
        self.offset_timer = QTimer(self, singleShot=True, interval=700, timeout=self.save_offset)
        if self.can_place and cfg.get("pos_x") >= 0:
            self.move(cfg.get("pos_x"), cfg.get("pos_y"))

        self.lyrics = []
        self.times = []
        self.idx = -1
        self.idx_changed = 0.0
        self.scroll = 0.0
        self._sig = None                 # ringkasan tampilan terakhir yang digambar (lihat tick)
        self._glyph_cache = {}           # bentuk huruf + garis tepi siap pakai (LRU, lihat _glyphs)
        self._fill_cache = {}            # pixmap isian teks per (glyph, warna) (LRU berbatas byte)
        self._fill_bytes = 0
        self.track_key = ""
        self.last_key = ""
        self.note = ""
        self.play_state = ""
        self.player_name = ""
        self.cur = None                  # {"artist","title","length"} lagu yang sedang terbaca
        self.base_pos = 0.0
        self.base_stamp = 0.0
        self.hover = False
        self.hover_btn = None
        self.toast = ""
        self.toast_until = 0.0

        self.loader = Loader()
        self.loader.done.connect(self.on_lyrics)
        self.update_tag = ""             # rilis lebih baru yang diketahui (kosong = tidak ada)
        self.update_url = ""
        self.updater = UpdateChecker()
        self.updater.checked.connect(self.on_update_checked)

        self.backend = None
        self.tick_timer = QTimer(self, interval=TICK_BUSY_MS, timeout=self.tick)
        self.tick_timer.start()
        if demo:
            self.lyrics = [{"t": t, "text": a, "roman": b} for t, a, b in DEMO]
            self.times = [e["t"] for e in self.lyrics]
            self.play_state = "Playing"
            self.base_stamp = time.monotonic() * 1000
            self.track_key = "demo"
        else:
            self.backend = make_backend(self.player_filter)
            if self.backend:
                self.backend.updated.connect(self.on_info)
                self.backend.start()

    # ---- jendela
    def _flags(self):
        f = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.s["on_top"]:
            f |= Qt.WindowType.WindowStaysOnTopHint
        if self.locked:
            f |= Qt.WindowType.WindowTransparentForInput
        self.setWindowFlags(f)

    def _reflag(self):
        vis = self.isVisible()
        self._flags()
        if vis:
            self.show()

    def set_locked(self, locked):
        self.locked = locked
        self._reflag()

    def set_on_top(self, v):
        self.s["on_top"] = v
        self.cfg.set("on_top", v)
        self._reflag()

    def set_auto_show(self, v):
        self.s["auto_show"] = v
        self.cfg.set("auto_show", v)

    def size_keys(self, mode):
        return ("dwidth", "dheight") if mode == "double" else ("width", "height")

    def _saved_size(self, mode):
        kw, kh = self.size_keys(mode)
        return self.cfg.get(kw), self.cfg.get(kh)

    def save_pos(self):
        self.cfg.set("pos_x", self.x())
        self.cfg.set("pos_y", self.y())

    def save_geom(self):
        if self.can_place:
            self.save_pos()
        kw, kh = self.size_keys(self.s["mode"])
        self.cfg.set(kw, self.width())
        self.cfg.set(kh, self.height())

    def set_mode(self, new):
        if new == self.s["mode"]:
            return
        self.save_geom()                       # ingat ukuran mode lama
        self.s["mode"] = new
        self.cfg.set("mode", new)
        self.resize(*self._saved_size(new))
        self.say(tr("mode_double" if new == "double" else "mode_scroll"))

    def apply_settings(self):
        old_mode, old_top = self.s["mode"], self.s["on_top"]
        kw, kh = self.size_keys(old_mode)
        self.cfg.set(kw, self.width())
        self.cfg.set(kh, self.height())
        self.s = self.cfg.snapshot()
        old_lang = _lang
        set_language(self.s["language"])
        if _lang != old_lang:               # tunda: menu lama bisa saja sedang memanggil kita
            QTimer.singleShot(0, self.rebuild_tray_menu)
        if self.s["mode"] != old_mode:
            self.resize(*self._saved_size(self.s["mode"]))
        if self.s["on_top"] != old_top:
            self._reflag()
        self.track_key = ""          # paksa muat ulang lirik (romaji/folder bisa berubah)
        self.update()

    def start_update_check(self):
        """Tampilkan info rilis baru dari cek sebelumnya (tanpa jaringan), lalu cek lagi bila sudah > 1 hari."""
        old = self.cfg.get("update_latest")
        if is_newer(old, APP_VERSION):
            self.update_tag, self.update_url = old, REPO_URL + "/releases/latest"
        self.updater.start(self.cfg)

    def on_update_checked(self, tag, url):
        if not parse_ver(tag):
            return
        known = self.cfg.get("update_latest")
        self.cfg.set("last_update_check", str(int(time.time())))
        self.cfg.set("update_latest", tag)
        if not is_newer(tag, APP_VERSION):
            self.update_tag = self.update_url = ""
            return
        # hanya buka alamat milik repo ini, apa pun isi jawaban API
        self.update_tag = tag
        self.update_url = url if url.startswith(REPO_URL + "/") else REPO_URL + "/releases/latest"
        if tag != known:                                  # baru ketahuan: beri tahu sekali
            self.say(tr("update_toast", ver=tag), 6.0)

    def open_update_page(self):
        QDesktopServices.openUrl(QUrl(self.update_url or REPO_URL + "/releases/latest"))

    def say(self, text, secs=1.6):
        self.toast, self.toast_until = text, time.monotonic() + secs

    def apply_lrc(self, raw, cur=None):
        """Simpan teks .lrc sebagai file lirik lagu (nama otomatis 'Artis - Judul.lrc',
        menimpa yang lama) lalu muat ulang. cur = lagu saat dialog dibuka."""
        cur = cur or self.cur
        if not cur:
            self.say(tr("no_active_song"))
            return False
        raw = raw.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
        if not parse_lrc(raw):
            self.say(tr("not_lrc"), 3.0)
            return False
        folder = Path(os.path.expanduser(self.s["lyrics_dir"]))
        name = lrc_name(cur["artist"], cur["title"])
        lrc = folder / name
        existed = lrc.exists()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            raw = add_lrc_tags(raw, cur["artist"], cur["title"])
            lrc.write_text(raw.rstrip("\n") + "\n", "utf-8")
            (folder / romaji_name(name)).unlink(missing_ok=True)  # buat ulang
        except OSError as e:
            self.say(tr("save_failed", err=e), 3.0)
            return False
        if f"{cur['artist']}|{cur['title']}" == self.track_key:
            self.track_key = ""                   # paksa muat ulang dari file lokal
            self.note = tr("loading")
        self.say(tr("lyrics_replaced" if existed else "lyrics_saved", name=name), 3.0)
        print(f"[senandung] lyrics {'replaced' if existed else 'saved'}: {lrc}")
        return True

    # ---- tray: sembunyi / tampil
    def show_osd(self):
        self.hidden_by_user = False
        self.show()
        self.raise_()
        self.tick()                              # segera sesuaikan interval + gambar ulang

    def hide_to_tray(self, notify=True):
        self.save_geom()
        self.hidden_by_user = True
        self.hide()
        if notify and self.tray and not self._hint_shown:
            self._hint_shown = True
            extra = tr("tray_msg_auto") if self.s["auto_show"] else ""
            self.tray.showMessage("Senandung", tr("tray_msg") + extra,
                                  QSystemTrayIcon.MessageIcon.Information, 4000)

    def toggle_visible(self):
        if self.isVisible():
            self.hide_to_tray(notify=False)
        else:
            self.show_osd()

    def rebuild_tray_menu(self):
        """Bangun ulang menu tray (dipanggil saat awal dan saat bahasa berubah)."""
        if self.tray:
            self.tray_menu = build_menu(self)
            self.tray.setContextMenu(self.tray_menu)

    def quit_app(self):
        self.quitting = True
        self.save_geom()
        if self.backend:
            self.backend.stop()
        QApplication.quit()

    def closeEvent(self, ev):
        # Tombol close = masuk ke system tray (aplikasi tetap berjalan).
        # Tanpa tray yang tersedia, close benar-benar keluar agar jendela tidak "hilang".
        if self.quitting or not QSystemTrayIcon.isSystemTrayAvailable():
            self.quitting = True
            self.save_geom()
            ev.accept()
            QApplication.quit()
            return
        ev.ignore()
        self.hide_to_tray()

    # ---- pemutar
    def player_filter(self):
        return (split_list(self.s["players"]), split_list(self.s["blacklist"]),
                bool(self.s["strict_players"]))

    def blacklist_current(self):
        """Masukkan pemutar yang sedang terbaca ke blacklist, lalu abaikan mulai sekarang."""
        name = short_name(self.player_name)
        if not name:
            self.say(tr("no_active_player"))
            return
        items = split_list(self.s["blacklist"])
        if name not in items:
            items.append(name)
        value = ",".join(items)
        self.s["blacklist"] = value
        self.cfg.set("blacklist", value)
        self.say(tr("ignored", name=name))
        self.on_info(None)

    def control(self, cmd):
        if self.backend:
            self.backend.command(cmd)
        else:
            self.say(tr("demo_no_player"))

    def on_info(self, info):
        if info is None:
            if self.track_key:
                self.track_key, self.lyrics, self.times, self.idx = "", [], [], -1
            self.play_state, self.last_key, self.note, self.player_name = "", "", "", ""
            self.cur = None
            return
        state, reported = info["state"], info["pos"]
        artist, title = info["artist"], info["title"]
        self.player_name = info.get("player", "")
        self.cur = {"artist": artist, "title": title, "length": info["length"],
                    "path": info.get("path", "")} \
            if title.strip() else None
        now = time.monotonic() * 1000
        prev = self.play_state
        key = f"{artist}|{title}"
        est = self.base_pos + (now - self.base_stamp) if prev == "Playing" else self.base_pos
        if not info.get("clock", True):
            # pemutar tidak melaporkan posisi: hitung sendiri sejak lagu/putaran dimulai
            length_ms = info["length"] * 1000
            restart = key != self.track_key or prev in ("", "Stopped") or \
                (length_ms > 0 and est > length_ms + 2000)
            reported = 0.0 if restart else est
        diff = reported - est
        if prev == "Playing" and state == "Playing" and key == self.track_key and -1500 < diff <= 0:
            pass        # laporan pemutar tertinggal/dibulatkan: jangan mundur
        else:
            self.base_pos, self.base_stamp = reported, now
        self.play_state = state

        # muncul lagi otomatis (setelah ditutup ke tray) saat lagu berganti / mulai diputar
        song_changed = key != self.last_key
        self.last_key = key
        if state == "Playing" and (song_changed or prev != "Playing") \
                and self.hidden_by_user and self.s["auto_show"]:
            self.show_osd()

        if key != self.track_key:
            self.track_key = key
            self.lyrics, self.times, self.idx, self.scroll = [], [], -1, 0.0
            if not title.strip():
                self.note = ""
                return
            self.note = tr("searching")
            print(f"[senandung] track: {artist} - {title}")
            self.loader.load(key, artist, title, info["length"], self.s, info.get("path", ""))

    def on_lyrics(self, key, entries):
        if key != self.track_key:
            return
        self.lyrics = entries
        self.times = [e["t"] for e in entries]
        self.idx, self.scroll = -1, 0.0
        self.note = "" if entries else tr("not_found")
        # offset per lagu dibaca dari tag [offset:N] di file .lrc (lihat load_lyrics)
        self.local_offset = entries[0].get("_offset", 0) if entries else 0

    # ---- waktu
    def pos_ms(self):
        now = time.monotonic() * 1000
        p = self.base_pos + (now - self.base_stamp) if self.play_state == "Playing" else self.base_pos
        p += self.local_offset
        return p % 42000 if self.demo else p

    def tick(self):
        if self.lyrics:
            new = bisect.bisect_right(self.times, self.pos_ms()) - 1
            if new != self.idx:
                self.idx, self.idx_changed = new, time.monotonic() * 1000
            target = max(self.idx, 0)
            d = target - self.scroll
            self.scroll = target if abs(d) > 8 or abs(d) < 0.002 else self.scroll + d * 0.28
        # cepat saat ada yang bergerak (lagu main / scroll belum berhenti), lambat saat diam,
        # dan paling lambat saat jendela disembunyikan (tidak ada yang digambar)
        busy = self.play_state == "Playing" or abs(max(self.idx, 0) - self.scroll) > 0.002
        want = TICK_HIDDEN_MS if not self.isVisible() else TICK_BUSY_MS if busy else TICK_IDLE_MS
        if self.tick_timer.interval() != want:
            self.tick_timer.setInterval(want)
        if self.isVisible() and (self.lyrics or self.hover or self.toast or self.note):
            sig = self._frame_sig()
            if sig != self._sig:                  # sama dengan frame yang sudah tergambar: lewati
                self._sig = sig
                self.update()

    def _frame_sig(self):
        """Ringkasan semua yang memengaruhi gambar. Sama dengan tick sebelumnya = tidak perlu
        menggambar ulang (mis. lagu dijeda, atau baris aktif belum berganti)."""
        wipe = 0
        if self.lyrics and self.s["wipe"] and 0 <= self.idx < len(self.lyrics):
            wipe = int(max(0.0, min(1.0, self._wipe(self.idx))) * 400)
        ramp = min(12, int(max(0.0, time.monotonic() * 1000 - self.idx_changed) / 20))   # 240 ms
        toast = self.toast if time.monotonic() < self.toast_until else ""
        return (id(self.lyrics), self.idx, round(self.scroll, 3), wipe, ramp, self.play_state,
                self.hover, self.hover_btn, self.locked, toast, self.note, bool(self.track_key),
                self.width(), self.height())

    # ---- gambar teks
    def _font(self, scale=1.0):
        f = QFont(self.s["font_family"]) if self.s["font_family"] else QFont()
        f.setPointSizeF(max(5.0, self.s["font_size"] * scale))
        return f

    def _texts(self, e):
        txt = e["text"] or "♪"
        mode, rom = self.s["romaji"], e["roman"]
        if not rom or mode == "off":
            return [txt]
        return [rom] if mode == "romaji" else [txt, rom]

    def _kara(self):
        """Warna isi karaoke; kosong = ikut warna font sorot."""
        return QColor(self.s["kara_color"] or self.s["hl_color"])

    def _spacing(self):
        return max(50, min(250, self.s["line_spacing"])) / 100.0

    def _brush(self, color, top, bottom):
        if not self.s["gradient"]:
            return QBrush(color)
        g = QLinearGradient(0, top, 0, bottom)           # efek mengkilap ala MiniLyrics
        g.setColorAt(0.0, color.lighter(118))
        g.setColorAt(0.5, color)
        g.setColorAt(1.0, color.darker(125))
        return QBrush(g)

    def _glyphs(self, text, font, maxw):
        """Bentuk huruf (QPainterPath) + metrik satu baris, muat otomatis ke lebar maxw.
        Dihitung sekali per (teks, font, ukuran, lebar) lalu dipakai ulang tiap frame.
        Cache LRU kecil: hasilnya memegang pixmap garis tepi."""
        key = (text, self.s["font_family"], round(font.pointSizeF(), 2), round(maxw),
               self.devicePixelRatioF())
        g = self._glyph_cache.pop(key, None)         # pop + simpan lagi = tandai terbaru dipakai
        if g is None:
            fm = QFontMetricsF(font)
            w = fm.horizontalAdvance(text)
            if w > maxw:                             # kecilkan font agar muat
                font.setPointSizeF(max(5.0, font.pointSizeF() * maxw / w))
                fm = QFontMetricsF(font)
                w = fm.horizontalAdvance(text)
            path = QPainterPath()
            path.addText(0, 0, font, text)           # titik asal = garis dasar, sisi kiri
            g = {"path": path, "w": w, "asc": fm.ascent(), "desc": fm.descent(),
                 "h": fm.height(), "size": font.pointSizeF(), "outline": None, "key": key}
            while len(self._glyph_cache) >= 48:
                self._glyph_cache.pop(next(iter(self._glyph_cache)))
        self._glyph_cache[key] = g
        return g

    def _layer_geom(self, g):
        """Geometri pixmap lapisan teks (outline & isian memakai ukuran yang sama):
        (pad, base, lebar, tinggi) dalam piksel logis; base = garis dasar di dalam pixmap."""
        pw = max(2.0, g["size"] / 7)
        pad = int(pw) + 3
        base = int(g["asc"]) + 1 + pad
        return pad, base, int(g["w"]) + 2 * pad + 2, base + int(g["desc"]) + 1 + pad

    def _new_layer(self, g):
        pad, base, wl, hl = self._layer_geom(g)
        dpr = self.devicePixelRatioF()
        pm = QPixmap(int(wl * dpr), int(hl * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        q = QPainter(pm)
        q.setRenderHint(QPainter.RenderHint.Antialiasing)
        q.translate(pad, base)
        return pm, q

    def _outline(self, g):
        """Garis tepi hitam dirender sekali ke pixmap. strokePath dengan antialiasing adalah
        bagian paling mahal (puluhan kali lipat addText); menempel pixmap hampir gratis."""
        if g["outline"] is None:
            pw = max(2.0, g["size"] / 7)
            pm, q = self._new_layer(g)
            q.strokePath(g["path"], QPen(QColor(0, 0, 0, 215), pw, Qt.PenStyle.SolidLine,
                                         Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            q.end()
            pad, base = self._layer_geom(g)[:2]
            g["outline"] = (pm, pad, base)
        return g["outline"]

    def _fill(self, g, color):
        """Isian teks (warna/gradien) dirender sekali ke pixmap lalu dipakai ulang tiap frame.
        fillPath dengan gradien tiap frame adalah sumber CPU terbesar. Cache LRU dibatasi
        FILL_CACHE_BYTES; kuncinya memuat glyph, warna, dan pengaturan gradien."""
        key = (g["key"], color.rgba(), self.s["gradient"])
        pm = self._fill_cache.pop(key, None)             # pop + simpan lagi = tandai terbaru dipakai
        if pm is None:
            pm, q = self._new_layer(g)
            q.fillPath(g["path"], self._brush(color, -g["asc"], g["desc"]))
            q.end()
            self._fill_bytes += pm.width() * pm.height() * 4
            while self._fill_cache and self._fill_bytes > FILL_CACHE_BYTES:
                old = self._fill_cache.pop(next(iter(self._fill_cache)))
                self._fill_bytes -= old.width() * old.height() * 4
        self._fill_cache[key] = pm
        return pm

    def _draw(self, p, text, yc, color, opa, align, wipe=0.0, scale=1.0):
        """Gambar satu baris (muat otomatis ke lebar jendela) berpusat vertikal di yc."""
        margin = 18
        maxw = self.width() - 2 * margin
        g = self._glyphs(text, self._font(scale), maxw)
        w, asc, desc, fh = g["w"], g["asc"], g["desc"], g["h"]
        x = margin if align == "left" else self.width() - margin - w if align == "right" \
            else (self.width() - w) / 2
        ox, oy = round(x), round(yc + (asc - desc) / 2)    # piksel bulat: pixmap tepi = isi, selalu pas
        p.setOpacity(opa)
        pad, base = self._layer_geom(g)[:2]
        if self.s["outline"]:
            p.drawPixmap(ox - pad, oy - base, self._outline(g)[0])
        p.drawPixmap(ox - pad, oy - base, self._fill(g, color))
        if wipe > 0:                             # isi warna karaoke dari kiri sampai posisi wipe
            kara = self._fill(g, self._kara())
            dpr = kara.devicePixelRatioF()
            sw = min(kara.width(), int((pad + w * min(wipe, 1.0)) * dpr + 0.5))
            if sw > 0:
                p.drawPixmap(ox - pad, oy - base, kara, 0, 0, sw, kara.height())
        p.setOpacity(1.0)
        return fh

    def _row_h(self):
        h = QFontMetricsF(self._font()).height() * 1.32 * self._spacing()
        return h * (1.85 if self.s["romaji"] == "both" else 1.0)

    def _wipe(self, i):
        if not self.s["wipe"] or i < 0 or i >= len(self.lyrics):
            return 0.0
        end = self.times[i + 1] if i + 1 < len(self.times) else self.times[i] + 4000
        return (self.pos_ms() - self.times[i]) / max(300, end - self.times[i])

    def _draw_entry(self, p, e, yc, color, opa, align, wipe, fit=1.0):
        texts = self._texts(e)
        if len(texts) == 1:
            self._draw(p, texts[0], yc, color, opa, align, wipe, fit)
        else:
            gap = QFontMetricsF(self._font(fit)).height() * 0.52 * self._spacing()
            self._draw(p, texts[0], yc - gap, color, opa, align, wipe, fit)
            self._draw(p, texts[1], yc + gap, color, opa * 0.85, align, wipe, 0.78 * fit)

    # ---- toolbar (tampil saat kursor di atas jendela)
    def _buttons(self):
        bw, gap, extra = 24, 3, 10
        total = len(TOOLBAR) * bw + (len(TOOLBAR) - 1) * gap + extra
        x = (self.width() - total) / 2
        out = []
        for n in TOOLBAR:
            out.append((n, QRectF(x, 3, bw, TB_H - 6)))
            x += bw + gap + (extra if n == "next" else 0)
        return out

    def _hit(self, pos):
        for n, r in self._buttons():
            if r.contains(pos):
                return n
        return None

    def _draw_toolbar(self, p):
        rects = self._buttons()
        first, last = rects[0][1], rects[-1][1]
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(20, 24, 31, 205))
        p.drawRoundedRect(QRectF(first.left() - 7, 1, last.right() - first.left() + 14, TB_H - 2), 10, 10)
        for n, r in rects:
            if n == self.hover_btn:
                p.setBrush(QColor(255, 255, 255, 50))
                p.drawRoundedRect(r, 6, 6)
            self._icon(p, n, r)

    def _icon(self, p, name, r):
        cx, cy = r.center().x(), r.center().y()
        white = QColor(255, 255, 255, 235)
        p.setPen(QPen(white, 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(white)
        s = 5.5
        if name == "prev":
            p.drawRect(QRectF(cx - s, cy - s, 1.8, 2 * s))
            p.drawPolygon(QPolygonF([QPointF(cx + s, cy - s), QPointF(cx + s, cy + s), QPointF(cx - s + 3, cy)]))
        elif name == "next":
            p.drawRect(QRectF(cx + s - 1.8, cy - s, 1.8, 2 * s))
            p.drawPolygon(QPolygonF([QPointF(cx - s, cy - s), QPointF(cx - s, cy + s), QPointF(cx + s - 3, cy)]))
        elif name == "play":
            if self.play_state == "Playing":
                p.drawRect(QRectF(cx - s + 1, cy - s, 3.2, 2 * s))
                p.drawRect(QRectF(cx + s - 4.2, cy - s, 3.2, 2 * s))
            else:
                p.drawPolygon(QPolygonF([QPointF(cx - s + 1.5, cy - s - 0.5),
                                         QPointF(cx - s + 1.5, cy + s + 0.5), QPointF(cx + s, cy)]))
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            if name == "mode":                               # dua garis = mode dua baris, tiga = scroll
                for y in ((-3, 3) if self.s["mode"] == "double" else (-5, 0, 5)):
                    p.drawLine(QPointF(cx - 6, cy + y), QPointF(cx + 6, cy + y))
            elif name == "lock":
                p.drawRoundedRect(QRectF(cx - 5, cy - 1, 10, 7.5), 1.5, 1.5)
                p.drawArc(QRectF(cx - 3.2, cy - 6.5, 6.4, 9), 0, 180 * 16)
            elif name == "gear":
                p.drawEllipse(QPointF(cx, cy), 3.0, 3.0)
                for k in range(8):
                    a = k * math.pi / 4
                    p.drawLine(QPointF(cx + math.cos(a) * 5, cy + math.sin(a) * 5),
                               QPointF(cx + math.cos(a) * 7, cy + math.sin(a) * 7))
            elif name == "close":
                p.drawLine(QPointF(cx - 4.5, cy - 4.5), QPointF(cx + 4.5, cy + 4.5))
                p.drawLine(QPointF(cx - 4.5, cy + 4.5), QPointF(cx + 4.5, cy - 4.5))

    # ---- paint
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        if self.hover and not self.locked:
            p.setBrush(QColor(0, 0, 0, 80))
            p.setPen(QPen(QColor(255, 255, 255, 60), 1))
            p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 12, 12)
            p.setPen(QPen(QColor(255, 255, 255, 140), 2))             # tanda pojok ubah ukuran
            r = self.rect()
            for k in (6, 12):
                p.drawLine(r.right() - k - 2, r.bottom() - 4, r.right() - 4, r.bottom() - k - 2)
        if self.lyrics:
            if self.s["mode"] == "double":
                self._paint_double(p)
            else:
                self._paint_scroll(p)
        elif self.note and self.track_key:
            self._draw(p, self.note, self.height() / 2 + (TB_H / 2 if self.s["mode"] == "double" else 0),
                       QColor("#ffffff"), 0.75, "center", 0.0, 0.6)
        if self.hover and not self.locked:
            self._draw_toolbar(p)
        if self.toast and time.monotonic() < self.toast_until:
            self._draw(p, self.toast, self.height() - 14, QColor("#ffffff"), 1.0, "center", 0.0, 0.5)
        p.end()

    def _paint_scroll(self, p):
        h, rh = self.height(), self._row_h()
        align = "center" if self.s["align"] == "zigzag" else self.s["align"]
        base, hl = QColor(self.s["text_color"]), QColor(self.s["hl_color"])
        for j in range(max(0, int(self.scroll) - 6), min(len(self.lyrics), int(self.scroll) + 8)):
            d = abs(j - self.scroll)
            yc = h / 2 + (j - self.scroll) * rh
            if yc < -rh or yc > h + rh:
                continue
            t = round(max(0.0, 1.0 - d) * 8) / 8                     # 1 = tepat di tengah (8 langkah: cache isian)
            color = QColor(int(base.red() + (hl.red() - base.red()) * t),
                           int(base.green() + (hl.green() - base.green()) * t),
                           int(base.blue() + (hl.blue() - base.blue()) * t))
            opa = max(0.12, 1.0 / (1.0 + 1.1 * d * d))
            self._draw_entry(p, self.lyrics[j], yc, color, opa, align,
                             self._wipe(j) if j == self.idx else 0.0)

    def _paint_double(self, p):
        """Gaya MiniLyrics: strip toolbar di atas, lalu dua baris bergantian (atas kiri,
        bawah kanan). Baris aktif terisi warna; baris berikutnya redup dan memudar masuk."""
        top = TB_H
        slot_h = (self.height() - top) / 2
        fh = QFontMetricsF(self._font()).height()
        both = self.s["romaji"] == "both"
        need = fh * ((1.04 * self._spacing() + 1.06) if both else 1.25)   # tinggi blok satu entri
        fit = min(1.0, slot_h / need)                                # otomatis kecilkan bila jendela pendek
        base = QColor(self.s["text_color"])
        ramp = min(1.0, (time.monotonic() * 1000 - self.idx_changed) / 240)
        cur = max(self.idx, 0)
        for k in (cur, cur + 1):
            if k >= len(self.lyrics):
                continue
            slot = k % 2                                             # genap di atas, ganjil di bawah
            yc = top + slot_h * (slot + 0.5)
            align = self.s["align"]
            if align == "zigzag":
                align = "left" if slot == 0 else "right"
            active = (k == self.idx)
            if active:
                opa = 0.6 + 0.4 * ramp                               # dari "berikutnya" menjadi aktif
            elif k == cur + 1 and self.idx >= 0:
                opa = 0.6 * ramp                                     # baris baru memudar masuk
            else:
                opa = 0.6
            self._draw_entry(p, self.lyrics[k], yc, base, opa, align,
                             self._wipe(k) if active else 0.0, fit)
            if active and not self.s["wipe"]:                        # tanpa efek isi: warnai penuh
                self._draw_entry(p, self.lyrics[k], yc, QColor(self.s["hl_color"]), 1.0, align, 0.0, fit)

    # ---- interaksi
    def enterEvent(self, _):
        self.hover = True

    def leaveEvent(self, _):
        self.hover, self.hover_btn = False, None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        QToolTip.hideText()
        self.update()

    def mouseMoveEvent(self, ev):
        pos = ev.position()
        name = None if self.locked else self._hit(pos)
        corner = pos.x() > self.width() - 24 and pos.y() > self.height() - 24
        self.setCursor(Qt.CursorShape.PointingHandCursor if name else
                       Qt.CursorShape.SizeFDiagCursor if corner else Qt.CursorShape.ArrowCursor)
        if name != self.hover_btn:
            self.hover_btn = name
            if name:
                QToolTip.showText(ev.globalPosition().toPoint(), tr("tip_" + name), self)
            else:
                QToolTip.hideText()
            self.update()
        super().mouseMoveEvent(ev)

    def mousePressEvent(self, ev):
        if ev.button() != Qt.MouseButton.LeftButton or not self.windowHandle():
            return
        pos = ev.position()
        btn = self._hit(pos)
        if btn:
            self._click(btn)
            return
        corner = pos.x() > self.width() - 24 and pos.y() > self.height() - 24
        if corner:
            self.windowHandle().startSystemResize(Qt.Edge.RightEdge | Qt.Edge.BottomEdge)
        else:
            self.windowHandle().startSystemMove()

    def _click(self, name):
        if name == "prev":
            self.control("previous")
        elif name == "play":
            self.control("play-pause")
        elif name == "next":
            self.control("next")
        elif name == "mode":
            self.toggle_mode()
        elif name == "lock":
            self.say(tr("locked_toast"))
            self.set_locked(True)
        elif name == "gear":
            QTimer.singleShot(0, lambda: open_settings(self))
        elif name == "close":
            self.hide_to_tray()

    def mouseDoubleClickEvent(self, ev):
        if not self._hit(ev.position()):
            self.toggle_mode()

    def wheelEvent(self, ev):
        if not self.lyrics:
            return
        d = 100 if ev.angleDelta().y() > 0 else -100
        self.local_offset += d
        self.say(tr("offset_toast", v=self.local_offset))
        if self.cur:                         # simpan ke file .lrc setelah berhenti memutar roda
            self._offset_pending = (dict(self.cur), f"{self.cur['artist']}|{self.cur['title']}")
            self.offset_timer.start()

    def save_offset(self):
        """Tulis geser waktu lagu ini ke file .lrc sebagai tag [offset:N] supaya diingat
        saat lagu diputar ulang (dibaca kembali oleh load_lyrics)."""
        if not self._offset_pending:
            return
        cur, key = self._offset_pending
        self._offset_pending = None
        off = int(self.local_offset)
        lrc = resolve_lrc(Path(os.path.expanduser(self.s["lyrics_dir"])), cur["artist"], cur["title"])
        try:
            if lrc.exists():
                raw = read_text_file(lrc)
            elif self.s["save_local"] and key == self.track_key and self.lyrics:
                raw = "\n".join(fmt_time(e["t"]) + e["text"] for e in self.lyrics)
            else:
                return
            raw = raw.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
            raw = re.sub(r"(?im)^[ \t]*\[offset:[^\]]*\][ \t]*\n?", "", raw)
            if off:
                raw = f"[offset:{off}]\n" + raw
            lrc.parent.mkdir(parents=True, exist_ok=True)
            lrc.write_text(raw.rstrip("\n") + "\n", "utf-8")
        except OSError as e:
            self.say(tr("save_failed", err=e), 3.0)
            return
        self.say(tr("offset_saved", v=off))
        print(f"[senandung] offset {off} ms saved: {lrc.name}")

    def contextMenuEvent(self, ev):
        build_menu(self).exec(ev.globalPos())

    def toggle_mode(self):
        self.set_mode("double" if self.s["mode"] == "scroll" else "scroll")

    def moveEvent(self, ev):
        if self.can_place:
            self.pos_timer.start()           # simpan posisi setelah selesai digeser
        super().moveEvent(ev)


# --------------------------------------------------------------------- mulai bersama Windows
RUN_KEY = r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run"


def win_autostart_get():
    return QSettings(RUN_KEY, QSettings.Format.NativeFormat).contains("Senandung")


def win_autostart_set(on):
    s = QSettings(RUN_KEY, QSettings.Format.NativeFormat)
    if not on:
        s.remove("Senandung")
        return
    if getattr(sys, "frozen", False):
        cmd = f'"{sys.executable}"'
    else:
        exe = Path(sys.executable)
        pyw = exe.with_name("pythonw.exe")
        cmd = f'"{pyw if pyw.exists() else exe}" "{Path(__file__).resolve()}"'
    s.setValue("Senandung", cmd)


# --------------------------------------------------------------------- pengaturan & menu
class SettingsDialog(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("settings_title"))
        self.cfg = cfg
        form = QFormLayout(self)
        self.lang = QComboBox()
        self.lang_keys = ["auto", "id", "en"]
        self.lang.addItems([tr("lang_auto"), "Bahasa Indonesia", "English"])   # nama bahasa tidak diterjemahkan
        cur = cfg.get("language")
        self.lang.setCurrentIndex(self.lang_keys.index(cur) if cur in self.lang_keys else 0)
        self.mode = QComboBox()
        self.mode.addItems([tr("mode_item_scroll"), tr("mode_item_double")])
        self.mode.setCurrentIndex(0 if cfg.get("mode") == "scroll" else 1)
        self.font = QFontComboBox()
        if cfg.get("font_family"):
            self.font.setCurrentFont(QFont(cfg.get("font_family")))
        self.use_font = QCheckBox(tr("use_font"))
        self.use_font.setChecked(bool(cfg.get("font_family")))
        self.size = QSpinBox(minimum=8, maximum=120, value=cfg.get("font_size"))
        self.colors = {}
        for key in ("text_color", "hl_color", "kara_color"):
            val = cfg.get(key)
            b = QPushButton(val or tr("kara_follow"))
            b.clicked.connect(lambda _=False, k=key, btn=b: self.pick(k, btn))
            self.colors[key] = (val, b)
            self._paint_btn(b, val or cfg.get("hl_color"))
        self.kara_reset = QPushButton("↺")
        self.kara_reset.setToolTip(tr("kara_follow_tip"))
        self.kara_reset.setFixedWidth(32)
        self.kara_reset.clicked.connect(self.reset_kara)
        kara_row = QWidget()
        kl = QHBoxLayout(kara_row)
        kl.setContentsMargins(0, 0, 0, 0)
        kl.addWidget(self.colors["kara_color"][1], 1)
        kl.addWidget(self.kara_reset)
        self.spacing = QSpinBox(minimum=60, maximum=200, singleStep=5, value=cfg.get("line_spacing"))
        self.spacing.setSuffix(" %")
        self.outline = QCheckBox(tr("outline"), checked=cfg.get("outline"))
        self.gradient = QCheckBox(tr("gradient"), checked=cfg.get("gradient"))
        self.wipe = QCheckBox(tr("wipe"), checked=cfg.get("wipe"))
        self.on_top = QCheckBox(tr("on_top"), checked=cfg.get("on_top"))
        self.auto_show = QCheckBox(tr("auto_show"), checked=cfg.get("auto_show"))
        self.align = QComboBox()
        self.align_keys = ["left", "center", "right", "zigzag"]
        self.align.addItems([tr("align_left"), tr("align_center"), tr("align_right"), tr("align_zigzag")])
        self.align.setCurrentIndex(self.align_keys.index(cfg.get("align")))
        self.romaji = QComboBox()
        self.romaji_keys = ["off", "romaji", "both"]
        self.romaji.addItems([tr("romaji_off"), tr("romaji_only"), tr("romaji_both")])
        self.romaji.setCurrentIndex(self.romaji_keys.index(cfg.get("romaji")))
        self.offset = QSpinBox(minimum=-10000, maximum=10000, singleStep=100, value=cfg.get("offset_ms"))
        self.offset.setSuffix(" ms")
        self.players = QLineEdit(cfg.get("players"))
        self.players.setPlaceholderText(tr("players_ph"))
        self.players.setToolTip(tr("players_tip"))
        self.strict = QCheckBox(tr("strict"), checked=cfg.get("strict_players"))
        self.black = QLineEdit(cfg.get("blacklist"))
        self.black.setPlaceholderText("chrome,firefox,msedge")
        self.black.setToolTip(tr("black_tip"))
        self.folder = QLineEdit(cfg.get("lyrics_dir"))
        self.save = QCheckBox(tr("save_local"), checked=cfg.get("save_local"))
        self.updates = QCheckBox(tr("check_updates"), checked=cfg.get("check_updates"))
        for label, w in ((tr("lbl_language"), self.lang), (tr("lbl_mode"), self.mode),
                         (tr("lbl_font"), self.font), ("", self.use_font),
                         (tr("lbl_font_size"), self.size), (tr("lbl_text_color"), self.colors["text_color"][1]),
                         (tr("lbl_hl_color"), self.colors["hl_color"][1]),
                         (tr("lbl_kara_color"), kara_row),
                         (tr("lbl_line_spacing"), self.spacing), ("", self.outline),
                         ("", self.gradient), ("", self.wipe), ("", self.on_top), ("", self.auto_show),
                         (tr("lbl_align"), self.align), (tr("lbl_romaji"), self.romaji),
                         (tr("lbl_offset"), self.offset), (tr("lbl_players"), self.players),
                         ("", self.strict), (tr("lbl_blacklist"), self.black),
                         (tr("lbl_folder"), self.folder), ("", self.save), ("", self.updates)):
            form.addRow(label, w)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    @staticmethod
    def _paint_btn(btn, color):
        c = QColor(color)
        fg = "#000" if (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) > 140 else "#fff"
        btn.setStyleSheet(f"background:{color}; color:{fg};")

    def pick(self, key, btn):
        start = self.colors[key][0] or self.colors["hl_color"][0]
        c = QColorDialog.getColor(QColor(start), self)
        if c.isValid():
            self.colors[key] = (c.name(), btn)
            btn.setText(c.name())
            self._paint_btn(btn, c.name())
            if key == "hl_color" and not self.colors["kara_color"][0]:
                self._paint_btn(self.colors["kara_color"][1], c.name())   # karaoke ikut sorot

    def reset_kara(self):
        btn = self.colors["kara_color"][1]
        self.colors["kara_color"] = ("", btn)
        btn.setText(tr("kara_follow"))
        self._paint_btn(btn, self.colors["hl_color"][0])

    def save_to_cfg(self):
        c = self.cfg
        c.set("language", self.lang_keys[self.lang.currentIndex()])
        c.set("mode", "scroll" if self.mode.currentIndex() == 0 else "double")
        c.set("font_family", self.font.currentFont().family() if self.use_font.isChecked() else "")
        c.set("font_size", self.size.value())
        for key, (val, _) in self.colors.items():
            c.set(key, val)
        c.set("line_spacing", self.spacing.value())
        c.set("outline", self.outline.isChecked())
        c.set("gradient", self.gradient.isChecked())
        c.set("wipe", self.wipe.isChecked())
        c.set("on_top", self.on_top.isChecked())
        c.set("auto_show", self.auto_show.isChecked())
        c.set("align", self.align_keys[self.align.currentIndex()])
        c.set("romaji", self.romaji_keys[self.romaji.currentIndex()])
        c.set("offset_ms", self.offset.value())
        c.set("players", self.players.text())
        c.set("strict_players", self.strict.isChecked())
        c.set("blacklist", self.black.text())
        c.set("lyrics_dir", self.folder.text() or "~/lyrics")
        c.set("save_local", self.save.isChecked())
        c.set("check_updates", self.updates.isChecked())


class LyricsSearchDialog(QDialog):
    found = Signal(object)

    def __init__(self, artist, title, length, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("search_title"))
        self.setMinimumWidth(560)
        self.length = length
        self.chosen = None
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.artist = QLineEdit(artist)
        self.title = QLineEdit(title)
        form.addRow(tr("lbl_artist"), self.artist)
        form.addRow(tr("lbl_title"), self.title)
        lay.addLayout(form)
        self.btn = QPushButton(tr("search_btn"))
        self.btn.setDefault(True)
        self.btn.clicked.connect(self.search)
        self.artist.returnPressed.connect(self.search)
        self.title.returnPressed.connect(self.search)
        lay.addWidget(self.btn)
        self.status = QLabel(tr("search_hint"))
        lay.addWidget(self.status)
        self.list = QListWidget()
        self.list.setMinimumHeight(220)
        self.list.itemDoubleClicked.connect(lambda _: self.accept())
        self.list.currentRowChanged.connect(lambda r: self.ok.setEnabled(r >= 0))
        lay.addWidget(self.list)
        bb = QDialogButtonBox()
        self.ok = bb.addButton(tr("use_lyrics"), QDialogButtonBox.ButtonRole.AcceptRole)
        self.ok.setEnabled(False)
        bb.addButton(tr("close"), QDialogButtonBox.ButtonRole.RejectRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.found.connect(self.on_found)
        QTimer.singleShot(0, self.search)             # langsung cari berdasarkan lagu saat ini

    def search(self):
        a, t = self.artist.text().strip(), self.title.text().strip()
        if not (a or t):
            self.status.setText(tr("search_need"))
            return
        self.btn.setEnabled(False)
        self.list.clear()
        self.status.setText(tr("searching_dots"))

        def run():
            try:
                res = search_lrclib(a, t)
            except Exception as e:
                res = e
            self.found.emit(res)
        threading.Thread(target=run, daemon=True).start()

    def on_found(self, res):
        self.btn.setEnabled(True)
        if isinstance(res, Exception):
            self.status.setText(tr("search_failed", err=res))
            return
        if self.length > 0:                            # yang durasinya paling mirip di atas
            res.sort(key=lambda it: abs((it.get("duration") or 0) - self.length))
        for it in res:
            d = int(it.get("duration") or 0)
            text = (f"{it.get('artistName', '?')} - {it.get('trackName', '?')}"
                    f"   ·   {it.get('albumName') or '-'}   ·   {d // 60}:{d % 60:02d}")
            row = QListWidgetItem(text)
            row.setData(Qt.ItemDataRole.UserRole, it["syncedLyrics"])
            self.list.addItem(row)
        self.status.setText(tr("found_n", n=len(res)) if res else tr("none_found"))
        if res:
            self.list.setCurrentRow(0)

    def accept(self):
        row = self.list.currentItem()
        if row is None:
            return
        self.chosen = row.data(Qt.ItemDataRole.UserRole)
        super().accept()


def open_search(osd):
    cur = osd.cur
    if not cur:
        osd.say(tr("no_active_song"))
        return
    dlg = LyricsSearchDialog(cur["artist"], cur["title"], cur["length"])
    if dlg.exec() and dlg.chosen:
        osd.apply_lrc(dlg.chosen, cur)


def browse_lyrics(osd):
    cur = osd.cur
    if not cur:
        osd.say(tr("no_active_song"))
        return
    start = osd.cfg.get("last_browse_dir") or str(Path.home())
    path, _ = QFileDialog.getOpenFileName(
        None, tr("browse_title", artist=cur["artist"], title=cur["title"]), start,
        tr("file_filter"))
    if not path:
        return
    osd.cfg.set("last_browse_dir", str(Path(path).parent))
    try:
        raw = read_text_file(path)
    except OSError as e:
        osd.say(tr("read_failed", err=e), 3.0)
        return
    osd.apply_lrc(raw, cur)


class AboutDialog(QDialog):
    """Tentang Senandung: deskripsi, versi sekarang, cek pembaruan, dan tombol Update sekarang."""

    def __init__(self, osd):
        super().__init__()
        self.osd = osd
        self.kind = install_kind()
        self.busy = False                # sedang mengunduh: dialog tidak boleh ditutup
        self.checking = False
        self.error = ""
        self.setWindowTitle(tr("about_title"))
        self.setMinimumWidth(440)
        icon = QLabel()
        icon.setPixmap(QApplication.windowIcon().pixmap(72, 72))
        name = QLabel("<h2>Senandung</h2>")
        ver = QLabel(tr("about_version", v=APP_VERSION if APP_VERSION != "dev" else tr("about_dev")))
        desc = QLabel(tr("about_desc"))
        desc.setWordWrap(True)
        links = QLabel(f'<a href="{REPO_URL}">GitHub</a> · <a href="https://lrclib.net">LRCLIB</a> · '
                       f'<a href="{REPO_URL}/blob/main/LICENSE">MIT License</a>')
        links.setOpenExternalLinks(True)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.bar = QProgressBar()
        self.bar.setVisible(False)
        self.btn_check = QPushButton(tr("about_check"))
        self.btn_check.clicked.connect(self.check)
        self.btn_update = QPushButton(tr("about_update_now"))
        self.btn_update.clicked.connect(self.update_now)
        if not self.kind:
            self.btn_update.setToolTip(tr("about_update_tip_manual"))
        self.btn_close = QPushButton(tr("close"))
        self.btn_close.clicked.connect(self.reject)

        lay = QVBoxLayout(self)
        for w in (icon, name, ver):
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(w)
        lay.addWidget(desc)
        links.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(links)
        lay.addWidget(self.status)
        lay.addWidget(self.bar)
        row = QHBoxLayout()
        row.addWidget(self.btn_check)
        row.addStretch(1)
        row.addWidget(self.btn_update)
        row.addWidget(self.btn_close)
        lay.addLayout(row)

        osd.updater.checked.connect(self.on_checked)
        osd.updater.failed.connect(self.on_failed)
        self.updater = SelfUpdater()
        self.updater.progress.connect(self.on_progress)
        self.updater.done.connect(self.on_installed)
        if APP_VERSION != "dev" and not osd.update_tag:
            self.check()                 # versi baru yang sudah diketahui tidak perlu dicek ulang
        self.render()

    def render(self):
        dev = APP_VERSION == "dev"
        newer = bool(self.osd.update_tag) and not dev
        self.btn_check.setEnabled(not dev and not self.busy and not self.checking)
        self.btn_update.setEnabled(newer and not self.busy)
        self.btn_close.setEnabled(not self.busy)
        if self.busy:
            return
        if dev:
            text = tr("about_status_dev")
        elif self.checking:
            text = tr("about_checking")
        elif self.error:
            text = tr("about_check_failed", err=self.error)
        elif newer:
            text = tr("about_available", ver=self.osd.update_tag)
        else:
            text = tr("about_uptodate")
        self.status.setText(text)

    def check(self):
        self.checking, self.error = True, ""
        self.osd.updater.start(self.osd.cfg, force=True)
        self.render()

    def on_checked(self, tag, url):      # OSD.on_update_checked sudah memperbarui osd.update_tag
        self.checking = False
        self.render()

    def on_failed(self, err):
        if self.checking:
            self.checking, self.error = False, err
            self.render()

    def update_now(self):
        if not self.kind:
            self.osd.open_update_page()
            return
        self.busy = True
        self.bar.setValue(0)
        self.bar.setVisible(True)
        self.status.setText(tr("about_downloading", p=0))
        self.render()
        self.updater.start(self.kind)

    def on_progress(self, pct):
        self.bar.setValue(pct)
        self.status.setText(tr("about_downloading", p=pct))

    def on_installed(self, err, path):
        if err:
            self.busy = False
            self.bar.setVisible(False)
            self.render()
            self.status.setText(tr("about_update_failed", err=err))
            return
        # Instance tunggal: aplikasi harus keluar dulu, baru versi baru dijalankan.
        if self.kind == "appimage":
            QProcess.startDetached("sh", ["-c", 'sleep 1; exec "$0"', path])
        else:   # Setup .exe: tutup aplikasi, pasang diam-diam, lalu jalankan lagi (lihat senandung.iss)
            QProcess.startDetached(path, ["/SILENT", "/CLOSEAPPLICATIONS", "/RELAUNCH=1"])
        self.osd.quit_app()

    def reject(self):
        if not self.busy:
            super().reject()

    def done(self, r):
        for sig, slot in ((self.osd.updater.checked, self.on_checked), (self.osd.updater.failed, self.on_failed)):
            try:
                sig.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        super().done(r)


def open_about(osd):
    AboutDialog(osd).exec()


def build_menu(osd):
    m = QMenu()
    a1 = m.addAction(tr("m_scroll"))
    a1.setCheckable(True)
    a2 = m.addAction(tr("m_double"))
    a2.setCheckable(True)
    m.addSeparator()
    lock = m.addAction(tr("m_lock"))
    lock.setCheckable(True)
    top = m.addAction(tr("m_top"))
    top.setCheckable(True)
    auto = m.addAction(tr("m_auto"))
    auto.setCheckable(True)
    boot = None
    if IS_WIN:
        boot = m.addAction(tr("m_boot"))
        boot.setCheckable(True)

    def refresh():
        a1.setChecked(osd.s["mode"] == "scroll")
        a2.setChecked(osd.s["mode"] == "double")
        lock.setChecked(osd.locked)
        top.setChecked(osd.s["on_top"])
        auto.setChecked(osd.s["auto_show"])
        nm = short_name(osd.player_name)
        ign.setText(tr("m_ignore_named", name=nm) if nm else tr("m_ignore"))
        ign.setEnabled(bool(nm))
        upd.setVisible(bool(osd.update_tag))
        upd.setText(tr("m_update", ver=osd.update_tag))
        srch.setEnabled(bool(osd.cur))
        brow.setEnabled(bool(osd.cur))
        if boot:
            boot.setChecked(win_autostart_get())

    a1.triggered.connect(lambda: osd.set_mode("scroll"))
    a2.triggered.connect(lambda: osd.set_mode("double"))
    lock.triggered.connect(lambda v: osd.set_locked(v))
    top.triggered.connect(lambda v: osd.set_on_top(v))
    auto.triggered.connect(lambda v: osd.set_auto_show(v))
    if boot:
        boot.triggered.connect(lambda v: win_autostart_set(v))
    srch = m.addAction(tr("m_search"))
    srch.triggered.connect(lambda: open_search(osd))
    brow = m.addAction(tr("m_browse"))
    brow.triggered.connect(lambda: browse_lyrics(osd))
    m.addSeparator()
    ign = m.addAction(tr("m_ignore"))
    ign.triggered.connect(osd.blacklist_current)
    upd = m.addAction("")
    upd.setVisible(False)
    upd.triggered.connect(osd.open_update_page)
    m.addAction(tr("m_settings")).triggered.connect(lambda: open_settings(osd))
    m.addAction(tr("m_about")).triggered.connect(lambda: open_about(osd))
    m.addAction(tr("m_toggle")).triggered.connect(osd.toggle_visible)
    m.addSeparator()
    m.addAction(tr("m_quit")).triggered.connect(osd.quit_app)
    m.aboutToShow.connect(refresh)
    refresh()
    return m


def open_settings(osd):
    was_locked = osd.locked
    if was_locked:
        osd.set_locked(False)
    dlg = SettingsDialog(osd.cfg)
    if dlg.exec():
        dlg.save_to_cfg()
        osd.apply_settings()
    if was_locked:
        osd.set_locked(True)


# --------------------------------------------------------------------- ikon & main
def make_icon_image(size=256):
    """Ikon aplikasi (sama dengan senandung.svg), digambar dengan kode agar bebas berkas."""
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    k = size / 128

    def rr(x, y, w, h, r, color, op=1.0):
        p.setOpacity(op)
        p.setBrush(QColor(color))
        p.drawRoundedRect(QRectF(x * k, y * k, w * k, h * k), r * k, r * k)
    rr(8, 8, 112, 112, 26, "#14181f")
    rr(26, 40, 76, 12, 6, "#ffffff", .45)
    rr(26, 62, 50, 14, 7, "#1ed760")
    rr(76, 62, 26, 14, 7, "#ffffff")
    rr(26, 86, 64, 12, 6, "#ffffff", .45)
    p.end()
    return img


def load_app_icon():
    """Ikon aplikasi: tema ikon sistem -> berkas di assets/icons/png -> ikon gambar-kode (cadangan)."""
    icon = QIcon.fromTheme(APP_ID)
    if not icon.isNull():
        return icon
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    icon = QIcon()
    for f in sorted((base / "assets" / "icons" / "png").glob(f"{APP_ID}-*.png")):
        icon.addFile(str(f))
    if icon.isNull():
        icon = QIcon(QPixmap.fromImage(make_icon_image(64)))
    return icon


def load_tray_icon(fallback):
    """Ikon system tray tanpa teks (assets/icons/tray); bila tidak ada, pakai ikon aplikasi."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    icon = QIcon()
    for f in sorted((base / "assets" / "icons" / "tray").glob(f"{APP_ID}-tray-*.png")):
        icon.addFile(str(f))
    return fallback if icon.isNull() else icon


def main():
    argv = sys.argv[1:]
    if "--romanize-worker" in argv:                 # proses anak untuk romanisasi (lihat romanize_lines)
        _romanize_worker()
        return
    set_language(Cfg().get("language"))             # bahasa tersimpan, atau ikut sistem
    if "--make-icon" in argv:                       # dipakai installer Windows untuk membuat .ico
        i = argv.index("--make-icon")
        out = argv[i + 1] if i + 1 < len(argv) else "senandung.ico"
        src = Path(__file__).resolve().parent / "assets" / "icons" / "senandung.ico"
        if src.is_file():                           # pakai ikon neon dari assets bila tersedia
            shutil.copyfile(src, out)
            sys.exit(0)
        sys.exit(0 if make_icon_image().save(out) else 1)
    if "--list-players" in argv:                    # diagnosa: pemutar apa saja yang terlihat
        list_players()
        return
    if sys.stderr is None or sys.stdout is None:    # pythonw / exe tanpa konsol: tulis ke berkas log
        try:
            base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
            log = open(base / "senandung.log", "a", encoding="utf-8", buffering=1)
            sys.stdout = sys.stderr = log
        except OSError:
            pass

    demo = "--demo" in argv
    if IS_LINUX:
        if not demo and not shutil.which("playerctl"):
            sys.exit(tr("playerctl_missing"))
        if "--x11" in argv:
            # jalankan lewat XWayland: posisi diingat, "selalu di atas" dan klik tembus berfungsi
            os.environ["QT_QPA_PLATFORM"] = "xcb"
    elif not IS_WIN and not demo:
        sys.exit(tr("unsupported"))

    QGuiApplication.setDesktopFileName(APP_ID)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_ID)
    app.setQuitOnLastWindowClosed(False)

    # satu instance saja: menjalankan lagi akan menampilkan jendela yang sudah ada
    server = None
    sock_name = f"{APP_ID}-{os.environ.get('USER') or os.environ.get('USERNAME') or 'user'}"
    if not demo:
        sock = QLocalSocket()
        sock.connectToServer(sock_name)
        if sock.waitForConnected(300):
            sock.write(b"show")
            sock.flush()
            sock.waitForBytesWritten(300)
            sock.disconnectFromServer()
            print("[senandung] already running; showing the existing window")
            return
        QLocalServer.removeServer(sock_name)
        server = QLocalServer()
        server.listen(sock_name)

    cfg = Cfg()
    osd = OSD(cfg, demo)
    if server:
        server.newConnection.connect(lambda: (server.nextPendingConnection(), osd.show_osd()))
    try:                                            # jangan blokir logout/shutdown karena close = ke tray
        app.commitDataRequest.connect(lambda *_: setattr(osd, "quitting", True))
    except Exception:
        pass
    osd.show()

    icon = load_app_icon()
    app.setWindowIcon(icon)
    tray = QSystemTrayIcon(load_tray_icon(icon), app)
    tray.setToolTip("Senandung")
    osd.tray = tray
    osd.rebuild_tray_menu()                         # menu tray dibangun ulang bila bahasa diganti
    tray.activated.connect(lambda r: osd.toggle_visible()
                           if r == QSystemTrayIcon.ActivationReason.Trigger else None)
    tray.show()
    osd.start_update_check()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
