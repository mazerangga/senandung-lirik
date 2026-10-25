"""AIMP (Windows) lewat Remote API-nya sendiri."""
import struct
import sys
from pathlib import PureWindowsPath

from .common import IS_WIN

# AIMP tidak punya dukungan SMTC bawaan, jadi dibaca lewat Remote API-nya sendiri:
# jendela "AIMP2_RemoteInfo" (pesan WM_AIMP_*) + memory-mapped file "AIMP2_RemoteInfo" (metadata).
AIMP_NAME = "AIMP2_RemoteInfo"
WM_AIMP_COMMAND, WM_AIMP_PROPERTY = 0x0400 + 0x75, 0x0400 + 0x77
AIMP_PROP_POSITION, AIMP_PROP_STATE = 0x20, 0x40
AIMP_CMD = {"play-pause": 14, "next": 17, "previous": 18}
_aimp = {}


def _aimp_api():
    if not _aimp:
        import ctypes
        from ctypes import wintypes as w
        u, k = ctypes.WinDLL("user32"), ctypes.WinDLL("kernel32")
        u.FindWindowW.argtypes, u.FindWindowW.restype = [w.LPCWSTR, w.LPCWSTR], w.HWND
        u.SendMessageTimeoutW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM, w.UINT, w.UINT,
                                          ctypes.POINTER(ctypes.c_size_t)]
        u.SendMessageTimeoutW.restype = ctypes.c_ssize_t
        k.OpenFileMappingW.argtypes, k.OpenFileMappingW.restype = [w.DWORD, w.BOOL, w.LPCWSTR], w.HANDLE
        k.MapViewOfFile.argtypes = [w.HANDLE, w.DWORD, w.DWORD, w.DWORD, ctypes.c_size_t]
        k.MapViewOfFile.restype = ctypes.c_void_p
        k.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
        k.CloseHandle.argtypes = [w.HANDLE]
        _aimp.update(c=ctypes, u=u, k=k)
    return _aimp


def _aimp_msg(hwnd, msg, wparam, lparam=0):
    a = _aimp_api()
    res = a["c"].c_size_t(0)
    ok = a["u"].SendMessageTimeoutW(hwnd, msg, wparam, lparam, 0x2, 250, a["c"].byref(res))  # ABORTIFHUNG
    return int(res.value) if ok else None


def parse_aimp_info(raw):
    """Uraikan struct TAIMPRemoteFileInfo dari memory-mapped file AIMP. None bila tidak ada lagu."""
    if len(raw) < 0x58 or struct.unpack_from("<i", raw, 0x04)[0] == 0:
        return None
    dur_ms = struct.unpack_from("<I", raw, 0x10)[0]
    lens = struct.unpack_from("<6I", raw, 0x28)          # album, artist, date, filename, genre, title
    if sum(lens) * 2 > len(raw) - 0x58:
        return None
    parts, pos = [], 0x58
    for n in lens:
        parts.append(raw[pos:pos + n * 2].decode("utf-16-le", "replace"))
        pos += n * 2
    album, artist, _date, fname, _genre, title = parts
    if not title.strip():
        title = PureWindowsPath(fname).stem
    return {"album": album, "artist": artist, "title": title, "length": round(dur_ms / 1000)}


def aimp_read():
    """Info AIMP yang sedang berjalan (dict seperti backend lain) atau None."""
    if not IS_WIN:
        return None
    try:
        a = _aimp_api()
        c, u, k = a["c"], a["u"], a["k"]
        hwnd = u.FindWindowW(AIMP_NAME, None)
        if not hwnd:
            return None
        h = k.OpenFileMappingW(0x4, False, AIMP_NAME)       # FILE_MAP_READ; jangan membuat baru
        if not h:
            return None
        try:
            view = k.MapViewOfFile(h, 0x4, 0, 0, 2048)
            if not view:
                return None
            try:
                raw = c.string_at(view, 2048)
            finally:
                k.UnmapViewOfFile(view)
        finally:
            k.CloseHandle(h)
        info = parse_aimp_info(raw)
        if not info:
            return None
        st = _aimp_msg(hwnd, WM_AIMP_PROPERTY, AIMP_PROP_STATE)          # 0 stop, 1 jeda, 2 putar
        pos = _aimp_msg(hwnd, WM_AIMP_PROPERTY, AIMP_PROP_POSITION) or 0
        return {"state": {2: "Playing", 1: "Paused"}.get(st, "Stopped"), "pos": float(pos),
                "length": info["length"], "clock": True, "artist": info["artist"],
                "title": info["title"], "player": "AIMP"}
    except Exception as e:
        print(f"[senandung] AIMP Remote API: {e}", file=sys.stderr)
        return None


def aimp_command(cmd):
    code = AIMP_CMD.get(cmd)
    hwnd = _aimp_api()["u"].FindWindowW(AIMP_NAME, None) if code else 0
    if hwnd:
        _aimp_msg(hwnd, WM_AIMP_COMMAND, code)
