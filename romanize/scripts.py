"""Deteksi aksara (script) untuk keperluan romanisasi."""
import re

# Semua aksara non-Latin yang mungkin perlu diromanisasi
NON_LATIN = re.compile(
    "[\u0370-\u052f\u0590-\u06ff\u0750-\u077f\u08a0-\u08ff\u0900-\u0eff"
    "\u1100-\u11ff\u3040-\u30ff\u3130-\u318f\u3400-\u9fff\uac00-\ud7af"
    "\ufb50-\ufdff\ufe70-\ufeff]")

KANA = re.compile("[\u3040-\u30ff\u31f0-\u31ff]")
HAN = re.compile("[\u3400-\u4dbf\u4e00-\u9fff]")
HANGUL = re.compile("[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]")

# Arab + Persia/Urdu + presentation forms
ARABIC = re.compile("[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]")

# Sisanya (Yunani, Cyrillic, Ibrani, Devanagari, Thai, dst) -> unidecode.
# Catatan: rentang Arab (0600-06ff) SENGAJA dikeluarkan dari sini.
OTHER = re.compile("[\u0370-\u03ff\u0400-\u052f\u0590-\u05ff\u0900-\u0dff\u0e00-\u0eff]")
