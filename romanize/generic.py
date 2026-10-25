"""Aksara lain (Yunani, Cyrillic, Ibrani, Devanagari, Thai, dst) -> unidecode."""
from .common import lazy, tidy


def _unidecode():
    from unidecode import unidecode
    return unidecode


def romanize_generic(text):
    u = lazy("unidecode", _unidecode)
    return tidy(u(text)) if u else ""
