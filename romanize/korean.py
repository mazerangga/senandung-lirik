"""Korea -> romanisasi, lewat korean-romanizer (cadangan: unidecode)."""
from .chinese import romanize_zh
from .common import lazy, tidy
from .generic import romanize_generic
from .scripts import HAN_RUN


def _romanizer():
    from korean_romanizer.romanizer import Romanizer
    return Romanizer


def romanize_ko(text):
    # Baris campur hangul + hanja ("漢字와 한글"): korean-romanizer tidak membaca hanja, jadi bagian hanja
    # diberi bacaan pinyin lebih dulu (pendekatan; bacaan Korea hanja tidak tersedia di pustaka ini).
    if HAN_RUN.search(text):
        text = HAN_RUN.sub(lambda m: f" {romanize_zh(m.group()).lower()} ", text)
    r = lazy("korean", _romanizer)
    if r:
        try:
            return tidy(r(text).romanize())
        except Exception:
            pass
    return romanize_generic(text)
