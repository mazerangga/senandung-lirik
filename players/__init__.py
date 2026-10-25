"""Pemutar media: pilih backend sesuai platform."""
import shutil
import sys

from .aimp import aimp_command, aimp_read  # noqa: F401
from .common import IS_LINUX, IS_WIN, rank_player, short_name, split_list  # noqa: F401
from .linux import LinuxBackend, LinuxDBusBackend
from .windows import WinBackend


def make_backend(get_filter):
    if IS_LINUX:
        # playerctl dipakai sebagai backend utama. Backend D-Bus (LinuxDBusBackend) di PySide6
        # melempar TypeError saat start (bus.connect) dan tidak bisa membaca metadata, jadi hanya
        # dipakai sebagai cadangan bila playerctl tidak ada.
        if shutil.which("playerctl"):
            return LinuxBackend(get_filter)
        try:
            from PySide6.QtDBus import QDBusConnection
            if QDBusConnection.sessionBus().isConnected():
                return LinuxDBusBackend(get_filter)
        except Exception as e:
            print(f"[senandung] D-Bus backend unavailable: {e}", file=sys.stderr)
        print("[senandung] ERROR: playerctl not found and D-Bus backend unavailable.", file=sys.stderr)
        return None
    if IS_WIN:
        return WinBackend(get_filter)
    return None
