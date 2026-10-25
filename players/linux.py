"""Backend Linux: playerctl (cadangan) dan D-Bus/MPRIS asinkron."""
import time

from PySide6.QtCore import QObject, QProcess, QTimer, Signal, Slot

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
        self.timer = QTimer(self, interval=300, timeout=self._poll)

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

class LinuxDBusBackend(QObject):
    """Membaca pemutar lewat D-Bus asinkron (MPRIS) dengan kompensasi latensi."""
    updated = Signal(object)

    def __init__(self, get_filter):
        super().__init__()
        from PySide6.QtDBus import QDBusConnection, QDBusServiceWatcher
        self.get_filter = get_filter
        self.player = None
        self.cache = {}
        self.bus = QDBusConnection.sessionBus()
        self._watchers = []

        self.watcher = QDBusServiceWatcher(self)
        self.watcher.setConnection(self.bus)
        self.watcher.setWatchMode(QDBusServiceWatcher.WatchModeFlag.WatchForOwnerChange)
        self.watcher.serviceOwnerChanged.connect(self._on_name_owner)

        self.bus.connect("", "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties", "PropertiesChanged", self._on_prop_changed)
        self.bus.connect("", "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player", "Seeked", self._on_seeked)

        self.timer = QTimer(self, interval=250, timeout=self._emit_updated)
        self.sync_timer = QTimer(self, interval=5000, timeout=self._sync_all)

    def start(self):
        self._full_scan()
        self.timer.start()
        self.sync_timer.start()

    def stop(self):
        self.timer.stop()
        self.sync_timer.stop()

    def command(self, cmd):
        if self.player:
            from PySide6.QtDBus import QDBusMessage
            msg = QDBusMessage.createMethodCall(
                f"org.mpris.MediaPlayer2.{self.player}",
                "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player", cmd)
            self.bus.asyncCall(msg)

    def _full_scan(self):
        from PySide6.QtDBus import QDBusMessage
        msg = QDBusMessage.createMethodCall("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "ListNames")
        reply = self.bus.call(msg)
        if reply.type() == QDBusMessage.MessageType.ReplyMessage:
            for name in reply.arguments()[0]:
                if name.startswith("org.mpris.MediaPlayer2."):
                    self._init_player(name)

    def _init_player(self, bus_name):
        if bus_name not in self.cache:
            self.cache[bus_name] = {"state": "Stopped", "pos": 0.0, "length": 0, "clock": False, "artist": "", "title": "", "path": "", "stamp": 0.0}
        self._fetch_prop(bus_name, "PlaybackStatus")
        self._fetch_prop(bus_name, "Metadata")
        self._fetch_prop(bus_name, "Position")

    def _fetch_prop(self, bus_name, prop):
        from PySide6.QtDBus import QDBusMessage, QDBusPendingCallWatcher
        msg = QDBusMessage.createMethodCall(bus_name, "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties", "Get")
        msg.setArguments(["org.mpris.MediaPlayer2.Player", prop])
        w = QDBusPendingCallWatcher(self.bus.asyncCall(msg), self)
        w.setProperty("bus_name", bus_name)
        w.setProperty("prop", prop)
        w.setProperty("start_time", time.monotonic())
        w.finished.connect(self._on_async_prop)
        self._watchers.append(w)

    def _sync_all(self):
        for bus_name in list(self.cache.keys()):
            self._fetch_prop(bus_name, "Position")

    @Slot(object)
    def _on_prop_changed(self, msg):
        bus_name = msg.service()
        if not bus_name.startswith("org.mpris.MediaPlayer2."): return
        args = msg.arguments()
        if len(args) < 2: return
        
        if bus_name not in self.cache:
            self._init_player(bus_name)
        props = args[1]
        
        if "PlaybackStatus" in props:
            self.cache[bus_name]["state"] = props["PlaybackStatus"]
            self._fetch_prop(bus_name, "Position")
        if "Metadata" in props:
            self._parse_meta(self.cache[bus_name], props["Metadata"])
            self._fetch_prop(bus_name, "Position")

    @Slot(object)
    def _on_seeked(self, msg):
        bus_name = msg.service()
        if bus_name.startswith("org.mpris.MediaPlayer2."):
            self._fetch_prop(bus_name, "Position")

    @Slot(object)
    def _on_name_owner(self, name, old, new):
        if name.startswith("org.mpris.MediaPlayer2."):
            if new:
                self._init_player(name)
            elif old and name in self.cache:
                del self.cache[name]

    @Slot(object)
    def _on_async_prop(self, watcher):
        self._watchers.remove(watcher)
        watcher.deleteLater()
        from PySide6.QtDBus import QDBusMessage
        reply = watcher.reply()
        bus_name = watcher.property("bus_name")
        prop = watcher.property("prop")
        
        if bus_name not in self.cache or reply.type() == QDBusMessage.MessageType.ErrorMessage:
            if prop == "Position" and bus_name in self.cache:
                self.cache[bus_name]["clock"] = False
            return
            
        c = self.cache[bus_name]
        val = reply.arguments()[0]
        
        if prop == "PlaybackStatus":
            c["state"] = val
        elif prop == "Metadata":
            self._parse_meta(c, val)
        elif prop == "Position":
            rtt = time.monotonic() - watcher.property("start_time")
            c["pos"] = (val / 1000.0) + ((rtt / 2.0) * 1000.0)
            c["stamp"] = time.monotonic()
            c["clock"] = True

    def _parse_meta(self, c, meta):
        c["title"] = str(meta.get("xesam:title", ""))
        c["path"] = file_url_to_path(meta.get("xesam:url", ""))
        artists = meta.get("xesam:artist", [])
        c["artist"] = ", ".join(artists) if isinstance(artists, list) else str(artists)
        c["length"] = round(int(meta.get("mpris:length", 0)) / 1000000.0)

    def _emit_updated(self):
        prefer, black, strict = self.get_filter()
        best, best_score = None, -1e9
        
        for bus_name, c in self.cache.items():
            name = bus_name.replace("org.mpris.MediaPlayer2.", "")
            rank = rank_player(name, prefer, black, strict)
            if rank is None: continue
            
            score = (1000 if c["state"] == "Playing" else 500 if c["state"] == "Paused" else 0) - rank
            if score > best_score:
                best, best_score = bus_name, score
                
        if not best:
            self.player = None
            self.updated.emit(None)
            return
            
        c = self.cache[best]
        self.player = best.replace("org.mpris.MediaPlayer2.", "")
        pos = c["pos"]
        if c["state"] == "Playing" and c["clock"]:
            pos += (time.monotonic() - c["stamp"]) * 1000.0
            
        self.updated.emit({"state": c["state"], "pos": pos, "length": c["length"], "clock": c["clock"],
                           "artist": c["artist"], "title": c["title"], "player": self.player,
                           "path": c.get("path", "")})
