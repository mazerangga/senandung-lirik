"""Romanisasi lirik: satu modul per bahasa, dispatcher di sini.

  japanese.py  Jepang  -> romaji        (pykakasi)
  chinese.py   Mandarin -> pinyin       (pypinyin)
  korean.py    Korea   -> romanisasi    (korean-romanizer)
  (Arab/Persia/Urdu sengaja TIDAK diromanisasi: tanpa harakat, vokal tidak bisa ditebak dengan andal;
   barisnya tampil dengan aksara aslinya)
  generic.py   aksara lain              (unidecode)

Menambah bahasa baru: buat <bahasa>.py berisi fungsi (str) -> str, tambah deteksi aksaranya di
scripts.py, lalu daftarkan di romanize_lines() di bawah. Naikkan ROMAN_VERSION bila hasil berubah.
"""
from .chinese import romanize_zh
from .generic import romanize_generic
from .japanese import romanize_ja
from .korean import romanize_ko
from .scripts import ARABIC, HAN, HANGUL, KANA, NON_LATIN, OTHER  # noqa: F401 (NON_LATIN dipakai pemanggil)

# Naikkan angka ini setiap hasil romanisasi berubah, supaya cache lama (*.romaji.vN.lrc) tidak dipakai lagi.
ROMAN_VERSION = 4


def romanize_lines(lines):
    """list[str] -> list[str] (string kosong = baris tidak perlu romanisasi)."""
    song_ja = any(KANA.search(x) for x in lines)    # lagu Jepang: kanji dibaca sebagai Jepang, bukan Mandarin
    out = []
    for t in lines:
        if KANA.search(t):
            out.append(romanize_ja(t))
        elif HAN.search(t):
            out.append(romanize_ja(t) if song_ja else romanize_zh(t))
        elif HANGUL.search(t):
            out.append(romanize_ko(t))
        elif ARABIC.search(t):                      # Arab: biarkan aksara aslinya (jangan ke unidecode)
            out.append("")
        elif OTHER.search(t):
            out.append(romanize_generic(t))
        else:
            out.append("")
    return out
