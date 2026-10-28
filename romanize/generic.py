"""Aksara lain (Yunani, Cyrillic, Ibrani, Devanagari, Thai, dst) -> unidecode."""
import re

from .common import lazy, tidy


def _unidecode():
    from unidecode import unidecode
    return unidecode


def romanize_generic(text):
    u = lazy("unidecode", _unidecode)
    if not u:
        return ""
    s = u(text).replace("`", "")                       # penanda aspirasi unidecode (Georgia) tidak perlu tampil
    return tidy(re.sub(r"(^|\s)'(?=\w)", r"\1", s))    # apostrof awal kata = hentian glotal (Ethiopia), dibuang
