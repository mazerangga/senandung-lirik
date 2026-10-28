"""Pemutar media: pilih backend sesuai platform."""
import shutil
import sys

from .aimp import aimp_command, aimp_read
from .common import IS_LINUX, IS_WIN, rank_player, short_name, split_list
from .linux import LinuxBackend
from .windows import WinBackend

# Nama yang dipakai senandung.py (dan alat diagnosa); daftar ini juga menandai impor ulang sebagai disengaja.
__all__ = ["IS_LINUX", "IS_WIN", "aimp_command", "aimp_read", "make_backend", "rank_player", "short_name",
           "split_list"]


def make_backend(get_filter):
    if IS_LINUX:
        # playerctl adalah satu-satunya backend Linux. Backend D-Bus asli pernah ada sebagai cadangan, tetapi
        # tidak pernah terpakai (senandung.py berhenti lebih dulu bila playerctl tidak ada) dan tidak berfungsi.
        if shutil.which("playerctl"):
            return LinuxBackend(get_filter)
        print("[senandung] ERROR: playerctl not found.", file=sys.stderr)
        return None
    if IS_WIN:
        return WinBackend(get_filter)
    return None
