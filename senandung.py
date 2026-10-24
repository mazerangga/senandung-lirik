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
import json
import math
import os
import re
import shutil
import struct
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PureWindowsPath

from PySide6.QtCore import (QLocale, QObject, QPointF, QProcess, QRectF, QSettings, Qt,
                            QTimer, Signal, Slot)
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QGuiApplication, QIcon, QImage,
                           QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QCheckBox, QColorDialog, QComboBox, QDialog,
                               QDialogButtonBox, QFileDialog, QFontComboBox, QFormLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMenu, QPushButton,
                               QSpinBox, QSystemTrayIcon, QToolTip, QVBoxLayout, QWidget)

APP_ID = "senandung"
UA = "senandung/1.0 (https://github.com/mazerangga/senandung-lirik)"

DEFAULTS = {
    "mode": "scroll",            # scroll | double
    "language": "auto",          # auto (ikut bahasa sistem) | id | en
    "font_family": "",
    "font_size": 26,
    "text_color": "#ffffff",
    "hl_color": "#1ed760",
    "outline": True,
    "wipe": True,                # efek isi warna per baris (mode dua baris & baris aktif)
    "offset_ms": 500,
    "romaji": "romaji",          # off | romaji | both
    "align": "zigzag",           # left | center | right | zigzag (zigzag = gaya MiniLyrics)
    "players": "spotify,aimp,foobar2000,musicbee,winamp,vlc,mpv,amarok",  # prioritas (urutan)
    "strict_players": False,     # True = hanya pemutar di daftar "players" yang dipakai
    "blacklist": "chrome,chromium,msedge,firefox,brave,opera,vivaldi",    # pemutar yang diabaikan
    "lyrics_dir": "~/lyrics",
    "save_local": True,
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
    "lbl_text_color": {"id": "Warna teks", "en": "Text color"},
    "lbl_hl_color": {"id": "Warna baris aktif", "en": "Active line color"},
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


NON_LATIN = re.compile(
    "[\u0370-\u052f\u0590-\u06ff\u0900-\u0eff\u1100-\u11ff\u3040-\u30ff\u3130-\u318f"
    "\u3400-\u9fff\uac00-\ud7af]")
KANA = re.compile("[\u3040-\u30ff\u31f0-\u31ff]")
HAN = re.compile("[\u3400-\u4dbf\u4e00-\u9fff]")
HANGUL = re.compile("[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]")
OTHER = re.compile("[\u0370-\u03ff\u0400-\u052f\u0590-\u06ff\u0900-\u0dff\u0e00-\u0eff]")
PUNCT = str.maketrans({"，": ",", "。": ".", "、": ",", "！": "!", "？": "?", "：": ":", "；": ";",
                       "（": "(", "）": ")", "　": " "})
_libs = {}


def _lib(name):
    if name not in _libs:
        try:
            if name == "kakasi":
                import pykakasi
                _libs[name] = pykakasi.kakasi()
            elif name == "pinyin":
                from pypinyin import Style, lazy_pinyin
                _libs[name] = (lazy_pinyin, Style)
            elif name == "korean":
                from korean_romanizer.romanizer import Romanizer
                _libs[name] = Romanizer
            else:
                from unidecode import unidecode
                _libs[name] = unidecode
        except Exception as e:
            print(f"[senandung] romanization module '{name}' not available: {e}", file=sys.stderr)
            _libs[name] = None
    return _libs[name]


def _tidy(s):
    s = re.sub(r"\s+", " ", s.translate(PUNCT)).strip()
    s = re.sub(r"\s+([,.!?;:)\]」』”’])", r"\1", s)
    return s[:1].upper() + s[1:] if s else s


def romanize_lines(lines):
    song_ja = any(KANA.search(x) for x in lines)

    def ja(t):
        k = _lib("kakasi")
        return _tidy(" ".join(i["hepburn"] for i in k.convert(t))) if k else ""

    def zh(t):
        p = _lib("pinyin")
        return _tidy(" ".join(p[0](t, style=p[1].TONE))) if p else ""

    def other(t):
        u = _lib("unidecode")
        return _tidy(u(t)) if u else ""

    def ko(t):
        r = _lib("korean")
        if r:
            try:
                return _tidy(r(t).romanize())
            except Exception:
                pass
        return other(t)

    out = []
    for t in lines:
        if KANA.search(t):
            out.append(ja(t))
        elif HAN.search(t):
            out.append(ja(t) if song_ja else zh(t))
        elif HANGUL.search(t):
            out.append(ko(t))
        elif OTHER.search(t):
            out.append(other(t))
        else:
            out.append("")
    return out


def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_online(artist, title, duration_s):
    base = "https://lrclib.net/api/"
    q = urllib.parse.urlencode({"artist_name": artist, "track_name": title})
    try:
        res = http_json(f"{base}get?{q}" + (f"&duration={duration_s}" if duration_s > 0 else ""))
        if res.get("syncedLyrics"):
            return res["syncedLyrics"]
    except Exception as e:
        print(f"[senandung] LRCLIB get: {e}", file=sys.stderr)
    try:
        for item in http_json(f"{base}search?{q}"):
            if item.get("syncedLyrics"):
                return item["syncedLyrics"]
    except Exception as e:
        print(f"[senandung] LRCLIB search: {e}", file=sys.stderr)
    return None


def read_text_file(path):
    """Baca file teks dengan penanganan encoding umum (UTF-8/UTF-8 BOM, UTF-16 BOM, lalu cp1252)."""
    data = Path(path).read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", "replace")
    try:
        return data.decode("utf-8-sig")
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


def load_lyrics(artist, title, duration_s, cfg):
    """Dijalankan di thread terpisah. Mengembalikan list dict {t, text, roman}."""
    folder = Path(os.path.expanduser(cfg["lyrics_dir"]))
    name = lrc_name(artist, title)
    lrc = folder / name
    parsed = []
    
    # 1. Siapkan wadah untuk teks lirik mentah dan nilai offset
    raw_text = ""      
    offset_val = 0     

    if lrc.exists():
        # 2. Tampung ke raw_text dulu agar bisa di-regex nanti
        raw_text = lrc.read_text("utf-8", errors="replace") 
        parsed = parse_lrc(raw_text)
        if parsed:
            print(f"[senandung] lyrics loaded from local file: {lrc.name}")
            
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
        import re
        offset_match = re.search(r'\[offset:([+-]?\d+)\]', raw_text, re.IGNORECASE)
        offset_val = int(offset_match.group(1)) if offset_match else 0

    entries = [{"t": t, "text": x, "roman": ""} for t, x in parsed]

    # 5. Titipkan nilai offset ke baris lirik pertama sebagai metadata rahasia
    if entries:
        entries[0]["_offset"] = offset_val

    # --- Sisa kode romaji di bawah ini tidak berubah ---
    if entries and cfg["romaji"] != "off" and any(NON_LATIN.search(e["text"]) for e in entries):
        rfile = folder / name.replace(".lrc", ".romaji.lrc")
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

    def load(self, key, artist, title, duration_s, cfg):
        def run():
            try:
                self.done.emit(key, load_lyrics(artist, title, duration_s, cfg))
            except Exception as e:  # jangan sampai thread mati diam-diam
                print(f"[senandung] failed to load lyrics: {e}", file=sys.stderr)
                self.done.emit(key, [])
        threading.Thread(target=run, daemon=True).start()


# --------------------------------------------------------------------- pemutar (backend)
IS_WIN = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")


def split_list(text):
    return [x.strip().lower() for x in str(text).split(",") if x.strip()]


def short_name(name):
    """Nama pemutar yang stabil: buang akhiran instance MPRIS (firefox.instance123 -> firefox)."""
    return re.sub(r"\.instance[\d_]+$", "", name.strip().lower())


def rank_player(name, prefer, black, strict):
    """None = pemutar ditolak; selain itu peringkat (makin kecil makin diutamakan).
    Cocok bila nama pemutar MENGANDUNG kata di daftar (huruf besar/kecil tidak berpengaruh)."""
    n = name.lower()
    if any(b in n for b in black):
        return None
    for i, a in enumerate(prefer):
        if a in n:
            return i
    return None if strict else len(prefer)


class LinuxBackend(QObject):
    """Membaca pemutar lewat playerctl (MPRIS)."""
    updated = Signal(object)          # dict info pemutar, atau None bila tidak ada pemutar
    FMT = "{{playerName}}|||{{status}}|||{{position}}|||{{mpris:length}}|||{{artist}}|||{{title}}"

    def __init__(self, get_filter):
        super().__init__()
        self.get_filter = get_filter
        self.player = None
        self.proc = QProcess(self)
        self.proc.finished.connect(self._done)
        self.timer = QTimer(self, interval=300, timeout=self._poll)

    def start(self):
        self.timer.start()

    def stop(self):
        self.timer.stop()

    def _poll(self):
        if self.proc.state() == QProcess.ProcessState.NotRunning:
            self.proc.start("playerctl", ["-a", "metadata", "--format", self.FMT])

    def _done(self):
        out = bytes(self.proc.readAllStandardOutput()).decode("utf-8", "replace")
        prefer, black, strict = self.get_filter()
        best, best_score = None, -1e9
        for line in out.splitlines():
            p = line.split("|||")
            if len(p) < 6:
                continue
            rank = rank_player(p[0], prefer, black, strict)
            if rank is None:
                continue
            score = (1000 if p[1] == "Playing" else 500 if p[1] == "Paused" else 0) - rank
            if score > best_score:
                best, best_score = p, score
        if best is None:
            self.player = None
            self.updated.emit(None)
            return
        name, state, pos, length, artist, title = best
        self.player = name
        clock = True
        try:
            pos_ms = int(pos) / 1000
        except ValueError:
            pos_ms, clock = 0.0, False         # pemutar tidak melaporkan posisi
        try:
            dur = round(int(length) / 1_000_000)
        except ValueError:
            dur = 0
        self.updated.emit({"state": state, "pos": pos_ms, "length": dur, "clock": clock,
                           "artist": artist, "title": title, "player": name})

    def command(self, cmd):                    # previous | play-pause | next
        if self.player:
            QProcess.startDetached("playerctl", ["-p", self.player, cmd])

class LinuxDBusBackend(QObject):
    """Membaca pemutar lewat D-Bus asinkron (MPRIS) dengan kompensasi latensi."""
    updated = Signal(object)

    def __init__(self, get_filter):
        super().__init__()
        from PySide6.QtDBus import QDBusConnection, QDBusServiceWatcher
        self.get_filter = get_filter
        self.player = None
        self.cache = {}
        self.bus = QDBusConnection.sessionBus()
        self._watchers = []

        self.watcher = QDBusServiceWatcher(self)
        self.watcher.setConnection(self.bus)
        self.watcher.setWatchMode(QDBusServiceWatcher.WatchModeFlag.WatchForOwnerChange)
        self.watcher.serviceOwnerChanged.connect(self._on_name_owner)

        self.bus.connect("", "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties", "PropertiesChanged", self._on_prop_changed)
        self.bus.connect("", "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player", "Seeked", self._on_seeked)

        self.timer = QTimer(self, interval=250, timeout=self._emit_updated)
        self.sync_timer = QTimer(self, interval=5000, timeout=self._sync_all)

    def start(self):
        self._full_scan()
        self.timer.start()
        self.sync_timer.start()

    def stop(self):
        self.timer.stop()
        self.sync_timer.stop()

    def command(self, cmd):
        if self.player:
            from PySide6.QtDBus import QDBusMessage
            msg = QDBusMessage.createMethodCall(
                f"org.mpris.MediaPlayer2.{self.player}",
                "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player", cmd)
            self.bus.asyncCall(msg)

    def _full_scan(self):
        from PySide6.QtDBus import QDBusMessage
        msg = QDBusMessage.createMethodCall("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "ListNames")
        reply = self.bus.call(msg)
        if reply.type() == QDBusMessage.MessageType.ReplyMessage:
            for name in reply.arguments()[0]:
                if name.startswith("org.mpris.MediaPlayer2."):
                    self._init_player(name)

    def _init_player(self, bus_name):
        if bus_name not in self.cache:
            self.cache[bus_name] = {"state": "Stopped", "pos": 0.0, "length": 0, "clock": False, "artist": "", "title": "", "stamp": 0.0}
        self._fetch_prop(bus_name, "PlaybackStatus")
        self._fetch_prop(bus_name, "Metadata")
        self._fetch_prop(bus_name, "Position")

    def _fetch_prop(self, bus_name, prop):
        from PySide6.QtDBus import QDBusMessage, QDBusPendingCallWatcher
        msg = QDBusMessage.createMethodCall(bus_name, "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties", "Get")
        msg.setArguments(["org.mpris.MediaPlayer2.Player", prop])
        w = QDBusPendingCallWatcher(self.bus.asyncCall(msg), self)
        w.setProperty("bus_name", bus_name)
        w.setProperty("prop", prop)
        w.setProperty("start_time", time.monotonic())
        w.finished.connect(self._on_async_prop)
        self._watchers.append(w)

    def _sync_all(self):
        for bus_name in list(self.cache.keys()):
            self._fetch_prop(bus_name, "Position")

    @Slot(object)
    def _on_prop_changed(self, msg):
        bus_name = msg.service()
        if not bus_name.startswith("org.mpris.MediaPlayer2."): return
        args = msg.arguments()
        if len(args) < 2: return
        
        if bus_name not in self.cache:
            self._init_player(bus_name)
        props = args[1]
        
        if "PlaybackStatus" in props:
            self.cache[bus_name]["state"] = props["PlaybackStatus"]
            self._fetch_prop(bus_name, "Position")
        if "Metadata" in props:
            self._parse_meta(self.cache[bus_name], props["Metadata"])
            self._fetch_prop(bus_name, "Position")

    @Slot(object)
    def _on_seeked(self, msg):
        bus_name = msg.service()
        if bus_name.startswith("org.mpris.MediaPlayer2."):
            self._fetch_prop(bus_name, "Position")

    @Slot(object)
    def _on_name_owner(self, name, old, new):
        if name.startswith("org.mpris.MediaPlayer2."):
            if new:
                self._init_player(name)
            elif old and name in self.cache:
                del self.cache[name]

    @Slot(object)
    def _on_async_prop(self, watcher):
        self._watchers.remove(watcher)
        watcher.deleteLater()
        from PySide6.QtDBus import QDBusMessage
        reply = watcher.reply()
        bus_name = watcher.property("bus_name")
        prop = watcher.property("prop")
        
        if bus_name not in self.cache or reply.type() == QDBusMessage.MessageType.ErrorMessage:
            if prop == "Position" and bus_name in self.cache:
                self.cache[bus_name]["clock"] = False
            return
            
        c = self.cache[bus_name]
        val = reply.arguments()[0]
        
        if prop == "PlaybackStatus":
            c["state"] = val
        elif prop == "Metadata":
            self._parse_meta(c, val)
        elif prop == "Position":
            rtt = time.monotonic() - watcher.property("start_time")
            c["pos"] = (val / 1000.0) + ((rtt / 2.0) * 1000.0)
            c["stamp"] = time.monotonic()
            c["clock"] = True

    def _parse_meta(self, c, meta):
        c["title"] = str(meta.get("xesam:title", ""))
        artists = meta.get("xesam:artist", [])
        c["artist"] = ", ".join(artists) if isinstance(artists, list) else str(artists)
        c["length"] = round(int(meta.get("mpris:length", 0)) / 1000000.0)

    def _emit_updated(self):
        prefer, black, strict = self.get_filter()
        best, best_score = None, -1e9
        
        for bus_name, c in self.cache.items():
            name = bus_name.replace("org.mpris.MediaPlayer2.", "")
            rank = rank_player(name, prefer, black, strict)
            if rank is None: continue
            
            score = (1000 if c["state"] == "Playing" else 500 if c["state"] == "Paused" else 0) - rank
            if score > best_score:
                best, best_score = bus_name, score
                
        if not best:
            self.player = None
            self.updated.emit(None)
            return
            
        c = self.cache[best]
        self.player = best.replace("org.mpris.MediaPlayer2.", "")
        pos = c["pos"]
        if c["state"] == "Playing" and c["clock"]:
            pos += (time.monotonic() - c["stamp"]) * 1000.0
            
        self.updated.emit({"state": c["state"], "pos": pos, "length": c["length"], "clock": c["clock"],
                           "artist": c["artist"], "title": c["title"], "player": self.player})

# AIMP tidak punya dukungan SMTC bawaan, jadi dibaca lewat Remote API-nya sendiri:
# jendela "AIMP2_RemoteInfo" (pesan WM_AIMP_*) + memory-mapped file "AIMP2_RemoteInfo" (metadata).
AIMP_NAME = "AIMP2_RemoteInfo"
WM_AIMP_COMMAND, WM_AIMP_PROPERTY = 0x0400 + 0x75, 0x0400 + 0x77
AIMP_PROP_POSITION, AIMP_PROP_STATE = 0x20, 0x40
AIMP_CMD = {"play-pause": 14, "next": 17, "previous": 18}
_aimp = {}


def _aimp_api():
    if not _aimp:
        import ctypes
        from ctypes import wintypes as w
        u, k = ctypes.WinDLL("user32"), ctypes.WinDLL("kernel32")
        u.FindWindowW.argtypes, u.FindWindowW.restype = [w.LPCWSTR, w.LPCWSTR], w.HWND
        u.SendMessageTimeoutW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM, w.UINT, w.UINT,
                                          ctypes.POINTER(ctypes.c_size_t)]
        u.SendMessageTimeoutW.restype = ctypes.c_ssize_t
        k.OpenFileMappingW.argtypes, k.OpenFileMappingW.restype = [w.DWORD, w.BOOL, w.LPCWSTR], w.HANDLE
        k.MapViewOfFile.argtypes = [w.HANDLE, w.DWORD, w.DWORD, w.DWORD, ctypes.c_size_t]
        k.MapViewOfFile.restype = ctypes.c_void_p
        k.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
        k.CloseHandle.argtypes = [w.HANDLE]
        _aimp.update(c=ctypes, u=u, k=k)
    return _aimp


def _aimp_msg(hwnd, msg, wparam, lparam=0):
    a = _aimp_api()
    res = a["c"].c_size_t(0)
    ok = a["u"].SendMessageTimeoutW(hwnd, msg, wparam, lparam, 0x2, 250, a["c"].byref(res))  # ABORTIFHUNG
    return int(res.value) if ok else None


def parse_aimp_info(raw):
    """Uraikan struct TAIMPRemoteFileInfo dari memory-mapped file AIMP. None bila tidak ada lagu."""
    if len(raw) < 0x58 or struct.unpack_from("<i", raw, 0x04)[0] == 0:
        return None
    dur_ms = struct.unpack_from("<I", raw, 0x10)[0]
    lens = struct.unpack_from("<6I", raw, 0x28)          # album, artist, date, filename, genre, title
    if sum(lens) * 2 > len(raw) - 0x58:
        return None
    parts, pos = [], 0x58
    for n in lens:
        parts.append(raw[pos:pos + n * 2].decode("utf-16-le", "replace"))
        pos += n * 2
    album, artist, _date, fname, _genre, title = parts
    if not title.strip():
        title = PureWindowsPath(fname).stem
    return {"album": album, "artist": artist, "title": title, "length": round(dur_ms / 1000)}


def aimp_read():
    """Info AIMP yang sedang berjalan (dict seperti backend lain) atau None."""
    if not IS_WIN:
        return None
    try:
        a = _aimp_api()
        c, u, k = a["c"], a["u"], a["k"]
        hwnd = u.FindWindowW(AIMP_NAME, None)
        if not hwnd:
            return None
        h = k.OpenFileMappingW(0x4, False, AIMP_NAME)       # FILE_MAP_READ; jangan membuat baru
        if not h:
            return None
        try:
            view = k.MapViewOfFile(h, 0x4, 0, 0, 2048)
            if not view:
                return None
            try:
                raw = c.string_at(view, 2048)
            finally:
                k.UnmapViewOfFile(view)
        finally:
            k.CloseHandle(h)
        info = parse_aimp_info(raw)
        if not info:
            return None
        st = _aimp_msg(hwnd, WM_AIMP_PROPERTY, AIMP_PROP_STATE)          # 0 stop, 1 jeda, 2 putar
        pos = _aimp_msg(hwnd, WM_AIMP_PROPERTY, AIMP_PROP_POSITION) or 0
        return {"state": {2: "Playing", 1: "Paused"}.get(st, "Stopped"), "pos": float(pos),
                "length": info["length"], "clock": True, "artist": info["artist"],
                "title": info["title"], "player": "AIMP"}
    except Exception as e:
        print(f"[senandung] AIMP Remote API: {e}", file=sys.stderr)
        return None


def aimp_command(cmd):
    code = AIMP_CMD.get(cmd)
    hwnd = _aimp_api()["u"].FindWindowW(AIMP_NAME, None) if code else 0
    if hwnd:
        _aimp_msg(hwnd, WM_AIMP_COMMAND, code)


class WinBackend(QObject):
    """Membaca pemutar lewat Windows Media Session (SMTC) - Spotify, browser, dll.
    Butuh paket: winrt-runtime winrt-Windows.Media.Control winrt-Windows.Foundation
                 winrt-Windows.Foundation.Collections winrt-Windows.Storage.Streams"""
    updated = Signal(object)

    def __init__(self, get_filter):
        super().__init__()
        self.get_filter = get_filter
        self.loop = None
        self.session = None
        self.use_aimp = False
        self._stop = False

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._stop = True

    def _run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._main())
        except Exception as e:
            print(f"[senandung] Windows backend stopped: {e}", file=sys.stderr)

    async def _main(self):
        mgr = None
        try:
            from winrt.windows.media.control import \
                GlobalSystemMediaTransportControlsSessionManager as Manager
            mgr = await Manager.request_async()
        except Exception as e:                   # tanpa winrt tetap bisa membaca AIMP
            print(f"[senandung] winrt module not available: {e}", file=sys.stderr)
        while not self._stop:
            try:
                self.updated.emit(await self.poll(mgr))
            except Exception as e:
                print(f"[senandung] poll SMTC: {e}", file=sys.stderr)
            await asyncio.sleep(0.4)

    async def poll(self, mgr):
        from datetime import datetime, timezone
        prefer, black, strict = self.get_filter()

        def score(state, rank):
            return (1000 if state == "Playing" else 500 if state == "Paused" else 0) - rank

        best, best_score, best_state, best_app = None, -1e9, "", ""
        aimp = None
        rank = rank_player("aimp", prefer, black, strict)
        if rank is not None:                              # AIMP dulu: menang bila nilainya sama
            aimp = aimp_read()
            if aimp:
                best_score = score(aimp["state"], rank)
        for s in (mgr.get_sessions() if mgr else []):
            app = s.source_app_user_model_id or ""
            rank = rank_player(app, prefer, black, strict)
            if rank is None:
                continue
            st = int(s.get_playback_info().playback_status)      # 4 = Playing, 5 = Paused
            state = "Playing" if st == 4 else "Paused" if st == 5 else "Stopped"
            if score(state, rank) > best_score:
                best, best_score, best_state, best_app = s, score(state, rank), state, app
                aimp = None
        self.use_aimp = aimp is not None
        if aimp is not None:
            self.session = None
            return aimp
        if best is None:
            self.session = None
            return None
        self.session = best
        props = await best.try_get_media_properties_async()
        tl = best.get_timeline_properties()
        pos_ms = tl.position.total_seconds() * 1000
        end_s = tl.end_time.total_seconds()
        clock = not (end_s <= 0 and pos_ms <= 0)      # sebagian pemutar tidak memberi timeline
        if best_state == "Playing":                       # posisi dilaporkan saat last_updated_time
            lu = tl.last_updated_time
            if lu.tzinfo is None:
                lu = lu.replace(tzinfo=timezone.utc)
            pos_ms += max(0.0, min(30000.0, (datetime.now(timezone.utc) - lu).total_seconds() * 1000))
        if end_s > 0:
            pos_ms = min(pos_ms, end_s * 1000)
        return {"state": best_state, "pos": pos_ms, "length": round(end_s), "clock": clock,
                "artist": props.artist or "", "title": props.title or "", "player": best_app}

    def command(self, cmd):
        if self.use_aimp:
            aimp_command(cmd)
            return
        s, loop = self.session, self.loop
        if s is None or loop is None:
            return

        async def go():
            if cmd == "previous":
                await s.try_skip_previous_async()
            elif cmd == "next":
                await s.try_skip_next_async()
            else:
                await s.try_toggle_play_pause_async()
        asyncio.run_coroutine_threadsafe(go(), loop)


def make_backend(get_filter):
    if IS_LINUX:
        # playerctl dipakai sebagai backend utama. Backend D-Bus (LinuxDBusBackend) di PySide6
        # melempar TypeError saat start (bus.connect) dan tidak bisa membaca metadata, jadi hanya
        # dipakai sebagai cadangan bila playerctl tidak ada.
        if shutil.which("playerctl"):
            return LinuxBackend(get_filter)
        try:
            from PySide6.QtDBus import QDBusConnection
            if QDBusConnection.sessionBus().isConnected():
                return LinuxDBusBackend(get_filter)
        except Exception as e:
            print(f"[senandung] D-Bus backend unavailable: {e}", file=sys.stderr)
        print("[senandung] ERROR: playerctl not found and D-Bus backend unavailable.", file=sys.stderr)
        return None
    if IS_WIN:
        return WinBackend(get_filter)
    return None


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
        if self.can_place and cfg.get("pos_x") >= 0:
            self.move(cfg.get("pos_x"), cfg.get("pos_y"))

        self.lyrics = []
        self.times = []
        self.idx = -1
        self.idx_changed = 0.0
        self.scroll = 0.0
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

        self.backend = None
        self.tick_timer = QTimer(self, interval=33, timeout=self.tick)
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
            lrc.write_text(raw.rstrip("\n") + "\n", "utf-8")
            (folder / name.replace(".lrc", ".romaji.lrc")).unlink(missing_ok=True)  # buat ulang
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
        self.cur = {"artist": artist, "title": title, "length": info["length"]} \
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
            self.loader.load(key, artist, title, info["length"], self.s)

    def on_lyrics(self, key, entries):
        if key != self.track_key:
            return
        self.lyrics = entries
        self.times = [e["t"] for e in entries]
        self.idx, self.scroll = -1, 0.0
        self.note = "" if entries else tr("not_found")
        # --- [TAMBAHKAN PENANGKAPAN OFFSET DI SINI] ---
        # Tarik nilai offset dari lirik pertama, default 0 jika tidak ada
        self.local_offset = entries[0].get("_offset", 0) if entries else 0
        # ----------------------------------------------

    # ---- waktu
    def pos_ms(self):
        now = time.monotonic() * 1000
        p = self.base_pos + (now - self.base_stamp) if self.play_state == "Playing" else self.base_pos
        p += getattr(self, "local_offset", 0)
        return p % 42000 if self.demo else p

    def tick(self):
        if self.lyrics:
            new = bisect.bisect_right(self.times, self.pos_ms()) - 1
            if new != self.idx:
                self.idx, self.idx_changed = new, time.monotonic() * 1000
            target = max(self.idx, 0)
            d = target - self.scroll
            self.scroll = target if abs(d) > 8 else self.scroll + d * 0.28
        if self.isVisible() and (self.lyrics or self.hover or self.toast or self.note):
            self.update()

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

    def _brush(self, color, top, bottom):
        if not self.s["gradient"]:
            return QBrush(color)
        g = QLinearGradient(0, top, 0, bottom)           # efek mengkilap ala MiniLyrics
        g.setColorAt(0.0, color.lighter(118))
        g.setColorAt(0.5, color)
        g.setColorAt(1.0, color.darker(125))
        return QBrush(g)

    def _draw(self, p, text, yc, color, opa, align, wipe=0.0, scale=1.0):
        """Gambar satu baris (muat otomatis ke lebar jendela) berpusat vertikal di yc."""
        margin = 18
        maxw = self.width() - 2 * margin
        font = self._font(scale)
        fm = QFontMetricsF(font)
        w = fm.horizontalAdvance(text)
        if w > maxw:                                   # kecilkan font agar muat
            font.setPointSizeF(max(5.0, font.pointSizeF() * maxw / w))
            fm = QFontMetricsF(font)
            w = fm.horizontalAdvance(text)
        x = margin if align == "left" else self.width() - margin - w if align == "right" \
            else (self.width() - w) / 2
        base = yc + (fm.ascent() - fm.descent()) / 2
        top, bottom = base - fm.ascent(), base + fm.descent()
        path = QPainterPath()
        path.addText(x, base, font, text)
        p.setOpacity(opa)
        if self.s["outline"]:
            p.strokePath(path, QPen(QColor(0, 0, 0, 215), max(2.0, font.pointSizeF() / 7),
                                    Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                                    Qt.PenJoinStyle.RoundJoin))
        p.fillPath(path, self._brush(color, top, bottom))
        if wipe > 0:
            p.save()
            p.setClipRect(QRectF(x - 2, top - 4, w * min(wipe, 1.0) + 2, fm.height() + 8))
            p.fillPath(path, self._brush(QColor(self.s["hl_color"]), top, bottom))
            p.restore()
        p.setOpacity(1.0)
        return fm.height()

    def _row_h(self):
        h = QFontMetricsF(self._font()).height() * 1.32
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
            gap = QFontMetricsF(self._font(fit)).height() * 0.52
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
            t = max(0.0, 1.0 - d)                                    # 1 = tepat di tengah
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
        fit = min(1.0, slot_h / self._row_h())                       # otomatis kecilkan bila jendela pendek
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
        if not self.lyrics: return
        d = 100 if ev.angleDelta().y() > 0 else -100
        
        # Adjust timer lokal untuk lirik yang sedang berjalan
        self.local_offset = getattr(self, "local_offset", 0) + d
        self.say(tr("offset_toast", v=self.local_offset))
        
        # Notif untuk save (Opsional)
        self.note = tr("offset_save_note") # Buat entry tr ini di STRINGS

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
        for key in ("text_color", "hl_color"):
            b = QPushButton(cfg.get(key))
            b.clicked.connect(lambda _=False, k=key, btn=b: self.pick(k, btn))
            self.colors[key] = (cfg.get(key), b)
            self._paint_btn(b, cfg.get(key))
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
        for label, w in ((tr("lbl_language"), self.lang), (tr("lbl_mode"), self.mode),
                         (tr("lbl_font"), self.font), ("", self.use_font),
                         (tr("lbl_font_size"), self.size), (tr("lbl_text_color"), self.colors["text_color"][1]),
                         (tr("lbl_hl_color"), self.colors["hl_color"][1]), ("", self.outline),
                         ("", self.gradient), ("", self.wipe), ("", self.on_top), ("", self.auto_show),
                         (tr("lbl_align"), self.align), (tr("lbl_romaji"), self.romaji),
                         (tr("lbl_offset"), self.offset), (tr("lbl_players"), self.players),
                         ("", self.strict), (tr("lbl_blacklist"), self.black),
                         (tr("lbl_folder"), self.folder), ("", self.save)):
            form.addRow(label, w)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    @staticmethod
    def _paint_btn(btn, color):
        c = QColor(color)
        fg = "#000" if c.lightness() > 128 else "#fff"
        btn.setStyleSheet(f"background:{color}; color:{fg};")

    def pick(self, key, btn):
        c = QColorDialog.getColor(QColor(self.colors[key][0]), self)
        if c.isValid():
            self.colors[key] = (c.name(), btn)
            btn.setText(c.name())
            self._paint_btn(btn, c.name())

    def save_to_cfg(self):
        c = self.cfg
        c.set("language", self.lang_keys[self.lang.currentIndex()])
        c.set("mode", "scroll" if self.mode.currentIndex() == 0 else "double")
        c.set("font_family", self.font.currentFont().family() if self.use_font.isChecked() else "")
        c.set("font_size", self.size.value())
        for key, (val, _) in self.colors.items():
            c.set(key, val)
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
    m.addAction(tr("m_settings")).triggered.connect(lambda: open_settings(osd))
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
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
