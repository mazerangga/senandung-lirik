"""Backend Windows: Windows Media Session (SMTC) + AIMP."""
import asyncio
import sys
import threading
import time

from PySide6.QtCore import QObject, Signal

from .aimp import aimp_command, aimp_read
from .common import rank_player


class WinBackend(QObject):
    """Membaca pemutar lewat Windows Media Session (SMTC) - Spotify, browser, dll.
    Butuh paket: winrt-runtime winrt-Windows.Media.Control winrt-Windows.Foundation
                 winrt-Windows.Foundation.Collections winrt-Windows.Storage.Streams"""
    updated = Signal(object)

    def __init__(self, get_filter):
        super().__init__()
        self.get_filter = get_filter
        self.loop = None
        self.session = None
        self.use_aimp = False
        self._stop = False

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._stop = True

    def _run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._main())
        except Exception as e:
            print(f"[senandung] Windows backend stopped: {e}", file=sys.stderr)

    async def _main(self):
        mgr = None
        try:
            from winrt.windows.media.control import \
                GlobalSystemMediaTransportControlsSessionManager as Manager
            mgr = await Manager.request_async()
        except Exception as e:                   # tanpa winrt tetap bisa membaca AIMP
            print(f"[senandung] winrt module not available: {e}", file=sys.stderr)
        last_msg, last_log = "", 0.0
        while not self._stop:
            try:
                self.updated.emit(await self.poll(mgr))
                last_msg = ""
            except Exception as e:
                # Galat yang sama berulang tiap 0,4 dtk akan membanjiri senandung.log: catat saat pesan baru
                # muncul, lalu paling sering sekali per menit.
                msg, now = str(e), time.monotonic()
                if msg != last_msg or now - last_log > 60:
                    print(f"[senandung] poll SMTC: {msg}", file=sys.stderr)
                    last_msg, last_log = msg, now
            await asyncio.sleep(0.4)

    async def poll(self, mgr):
        from datetime import datetime, timezone
        prefer, black, strict = self.get_filter()

        def score(state, rank):
            return (1000 if state == "Playing" else 500 if state == "Paused" else 0) - rank

        best, best_score, best_state, best_app = None, -1e9, "", ""
        aimp = None
        rank = rank_player("aimp", prefer, black, strict)
        if rank is not None:                              # AIMP dulu: menang bila nilainya sama
            aimp = aimp_read()
            if aimp:
                best_score = score(aimp["state"], rank)
        for s in (mgr.get_sessions() if mgr else []):
            app = s.source_app_user_model_id or ""
            rank = rank_player(app, prefer, black, strict)
            if rank is None:
                continue
            st = int(s.get_playback_info().playback_status)      # 4 = Playing, 5 = Paused
            state = "Playing" if st == 4 else "Paused" if st == 5 else "Stopped"
            if score(state, rank) > best_score:
                best, best_score, best_state, best_app = s, score(state, rank), state, app
                aimp = None
        self.use_aimp = aimp is not None
        if aimp is not None:
            self.session = None
            return aimp
        if best is None:
            self.session = None
            return None
        self.session = best
        props = await best.try_get_media_properties_async()
        tl = best.get_timeline_properties()
        pos_ms = tl.position.total_seconds() * 1000
        end_s = tl.end_time.total_seconds()
        clock = not (end_s <= 0 and pos_ms <= 0)      # sebagian pemutar tidak memberi timeline
        if best_state == "Playing":                       # posisi dilaporkan saat last_updated_time
            lu = tl.last_updated_time
            if lu.tzinfo is None:
                lu = lu.replace(tzinfo=timezone.utc)
            pos_ms += max(0.0, min(30000.0, (datetime.now(timezone.utc) - lu).total_seconds() * 1000))
        if end_s > 0:
            pos_ms = min(pos_ms, end_s * 1000)
        return {"state": best_state, "pos": pos_ms, "length": round(end_s), "clock": clock,
                "artist": props.artist or "", "title": props.title or "", "player": best_app}

    def command(self, cmd):
        if self.use_aimp:
            aimp_command(cmd)
            return
        s, loop = self.session, self.loop
        if s is None or loop is None:
            return

        async def go():
            if cmd == "previous":
                await s.try_skip_previous_async()
            elif cmd == "next":
                await s.try_skip_next_async()
            else:
                await s.try_toggle_play_pause_async()
        asyncio.run_coroutine_threadsafe(go(), loop)
