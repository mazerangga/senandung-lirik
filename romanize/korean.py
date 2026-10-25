"""Korea -> romanisasi, lewat korean-romanizer (cadangan: unidecode)."""
from .common import lazy, tidy
from .generic import romanize_generic


def _romanizer():
    from korean_romanizer.romanizer import Romanizer
    return Romanizer


def romanize_ko(text):
    r = lazy("korean", _romanizer)
    if r:
        try:
            return tidy(r(text).romanize())
        except Exception:
            pass
    return romanize_generic(text)
