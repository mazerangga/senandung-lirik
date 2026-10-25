"""Mandarin -> pinyin (dengan tanda nada), lewat pypinyin."""
from .common import lazy, tidy


def _pinyin():
    from pypinyin import Style, lazy_pinyin
    return lazy_pinyin, Style


def romanize_zh(text):
    p = lazy("pinyin", _pinyin)
    return tidy(" ".join(p[0](text, style=p[1].TONE))) if p else ""
