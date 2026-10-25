"""Jepang -> romaji (Hepburn), lewat pykakasi."""
from .common import lazy, tidy


def _kakasi():
    import pykakasi
    return pykakasi.kakasi()


def romanize_ja(text):
    k = lazy("kakasi", _kakasi)
    return tidy(" ".join(i["hepburn"] for i in k.convert(text))) if k else ""
