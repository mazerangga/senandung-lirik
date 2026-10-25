"""Hal yang dipakai semua backend pemutar: platform, filter prioritas/blacklist."""
import re
import sys

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
