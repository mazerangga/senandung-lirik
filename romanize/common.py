"""Utilitas bersama untuk semua romanizer."""
import re
import sys

PUNCT = str.maketrans({"，": ",", "。": ".", "、": ",", "！": "!", "？": "?", "：": ":", "；": ";",
                       "（": "(", "）": ")", "　": " "})
_libs = {}


def lazy(name, loader):
    """Muat pustaka opsional sekali saja. Bila tidak terpasang -> None (romanisasi dilewati)."""
    if name not in _libs:
        try:
            _libs[name] = loader()
        except Exception as e:
            print(f"[senandung] romanization module '{name}' not available: {e}", file=sys.stderr)
            _libs[name] = None
    return _libs[name]


def tidy(s):
    """Rapikan spasi/tanda baca hasil romanisasi dan kapitalkan huruf pertama."""
    s = re.sub(r"\s+", " ", s.translate(PUNCT)).strip()
    s = re.sub(r"\s+([,.!?;:)\]」』”’])", r"\1", s)
    return s[:1].upper() + s[1:] if s else s
