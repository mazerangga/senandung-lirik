"""Backend Linux: membaca pemutar lewat playerctl (MPRIS)."""
from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from .common import file_url_to_path, rank_player


class LinuxBackend(QObject):
    """Membaca pemutar lewat playerctl (MPRIS)."""
    updated = Signal(object)          # dict info pemutar, atau None bila tidak ada pemutar
    FMT = "{{playerName}}|||{{status}}|||{{position}}|||{{mpris:length}}|||{{artist}}|||{{title}}|||{{xesam:url}}"

    def __init__(self, get_filter):
        super().__init__()
        self.get_filter = get_filter
        self.player = None
        self.proc = QProcess(self)
        self.proc.finished.connect(self._done)
        self.timer = QTimer(self, interval=500, timeout=self._poll)   # tiap polling = satu proses baru

    def start(self):
        self.timer.start()

    def stop(self):
        self.timer.stop()

    def _poll(self):
        if self.proc.state() == QProcess.ProcessState.NotRunning:
            self.proc.start("playerctl", ["-a", "metadata", "--format", self.FMT])

    def _done(self):
        out = bytes(self.proc.readAllStandardOutput()).decode("utf-8", "replace")
        prefer, black, strict = self.get_filter()
        best, best_score = None, -1e9
        for line in out.splitlines():
            p = line.split("|||")
            if len(p) < 6:
                continue
            rank = rank_player(p[0], prefer, black, strict)
            if rank is None:
                continue
            score = (1000 if p[1] == "Playing" else 500 if p[1] == "Paused" else 0) - rank
            if score > best_score:
                best, best_score = p, score
        if best is None:
            self.player = None
            self.updated.emit(None)
            return
        name, state, pos, length, artist, title = best[:6]
        path = file_url_to_path(best[6]) if len(best) > 6 else ""
        self.player = name
        clock = True
        try:
            pos_ms = int(pos) / 1000
        except ValueError:
            pos_ms, clock = 0.0, False         # pemutar tidak melaporkan posisi
        try:
            dur = round(int(length) / 1_000_000)
        except ValueError:
            dur = 0
        self.updated.emit({"state": state, "pos": pos_ms, "length": dur, "clock": clock,
                           "artist": artist, "title": title, "player": name, "path": path})

    def command(self, cmd):                    # previous | play-pause | next
        if self.player:
            QProcess.startDetached("playerctl", ["-p", self.player, cmd])
