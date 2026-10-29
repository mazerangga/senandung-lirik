import struct

import pytest

import senandung as S
from players.aimp import parse_aimp_info
from players.common import rank_player, short_name
from romanize import romanize_lines


# ------------------------------------------------------------------ parse_lrc
@pytest.mark.parametrize("line, expected", [
    ("[00:01.50]a", [(1500, "a")]),
    ("[00:01.5]a", [(1500, "a")]),
    ("[00:01.500]a", [(1500, "a")]),
    ("[00:01.05]a", [(1050, "a")]),
    ("[00:01:50]a", [(1500, "a")]),            # pecahan dengan ':'
    ("[00:01,50]a", [(1500, "a")]),            # pecahan dengan ','
    ("[01:02]a", [(62000, "a")]),
    ("[ar:Someone]", []),
    ("[00:03.00][00:10.00]Chorus", [(3000, "Chorus"), (10000, "Chorus")]),
    ("[00:07.1]<00:07.1>Hel<00:07.4>lo", [(7100, "Hello")]),        # tag per kata dibuang
    ("[00:01.00] <00:01.00>word  <00:01.50>level", [(1000, "word level")]),
])
def test_parse_lrc(line, expected):
    assert S.parse_lrc(line) == expected


def test_parse_lrc_sorted():
    assert [t for t, _ in S.parse_lrc("[00:05.00]b\n[00:01.00]a")] == [1000, 5000]


def test_fmt_time_roundtrip():
    for ms in (0, 999, 59995, 3599999):
        assert S.parse_lrc(S.fmt_time(ms) + "x")[0][0] == pytest.approx(ms, abs=10)


# --------------------------------------------------------- judul dan artis
@pytest.mark.parametrize("raw, clean", [
    ("Song (feat. B) - Remastered 2011", "Song"),
    ("Title - Live at X", "Title"),
    ("Song ft. Someone", "Song"),
    ("Hey Jude (Remastered 2015)", "Hey Jude"),
    ("[Live] Title", "Title"),
    ("Love Me (Like You Do)", "Love Me (Like You Do)"),            # kurung bagian judul: dipertahankan
    ("(Don't Fear) The Reaper", "(Don't Fear) The Reaper"),
    ("Mr. Brightside", "Mr. Brightside"),
])
def test_clean_title(raw, clean):
    assert S._clean_title(raw) == clean


@pytest.mark.parametrize("raw, first", [
    ("AC/DC", "AC/DC"),
    ("Simon & Garfunkel", "Simon & Garfunkel"),
    ("Tyler, The Creator", "Tyler, The Creator"),
    ("Earth, Wind & Fire", "Earth, Wind & Fire"),
    ("A, B", "A"),
    ("A; B", "A"),
    ("A / B", "A"),
    ("Artist A feat. B", "Artist A"),
])
def test_first_artist(raw, first):
    assert S._first_artist(raw) == first


# -------------------------------------------------------------- _pick_synced
def _it(title, dur, lyrics="L"):
    return {"trackName": title, "duration": dur, "syncedLyrics": lyrics}


def test_pick_synced_prefers_same_title_and_duration():
    items = [_it("Other", 200, "WRONG"), _it("Song", 300, "FAR"), _it("Song", 201, "RIGHT")]
    assert S._pick_synced(items, "Song", 200) == "RIGHT"


def test_pick_synced_loose_never_returns_other_song():
    assert S._pick_synced([_it("Other", 200, "WRONG")], "Song", 0, loose=True) is None
    assert S._pick_synced([_it("Other", 205, "WRONG")], "Song", 200, loose=True) is None


def test_pick_synced_loose_accepts_similar_title_within_10s():
    items = [_it("Love Me (Like You Do)", 257, "RIGHT")]
    assert S._pick_synced(items, "Love Me", 250, loose=True) == "RIGHT"
    assert S._pick_synced(items, "Love Me", 250, loose=False) is None


def test_pick_synced_skips_unsynced():
    assert S._pick_synced([{"trackName": "Song", "duration": 100, "syncedLyrics": None}], "Song", 100) is None


# ------------------------------------------------------------ file lokal
def make_cfg(tmp_path, **kw):
    return dict(S.DEFAULTS, lyrics_dir=str(tmp_path), save_local=True, **kw)


def test_load_lyrics_local_file_with_offset(tmp_path):
    (tmp_path / "AC DC - Back In Black.lrc").write_text(
        "[ar:AC/DC]\n[ti:Back In Black]\n[offset:+300]\n[00:01:50]<00:01.5>Back <00:02.0>in black\n[00:05.00]Two\n", "utf-8")
    res = S.load_lyrics("AC/DC", "Back In Black", 255, make_cfg(tmp_path))
    assert [(e["t"], e["text"]) for e in res.entries] == [(1500, "Back in black"), (5000, "Two")]
    assert res.offset == 300 and not res.transient


def test_load_lyrics_offline_is_transient(tmp_path, monkeypatch):
    def boom(url, timeout=15):
        raise OSError("no network")
    monkeypatch.setattr(S, "http_json", boom)
    res = S.load_lyrics("Nobody", "Nothing", 100, make_cfg(tmp_path))
    assert res.entries == [] and res.transient         # jangan di-cache sebagai "tidak ada"


def test_load_lyrics_not_found_is_not_transient(tmp_path, monkeypatch):
    import urllib.error

    def nf(url, timeout=15):
        raise urllib.error.HTTPError(url, 404, "nf", {}, None)
    monkeypatch.setattr(S, "http_json", nf)
    res = S.load_lyrics("Nobody", "Nothing", 100, make_cfg(tmp_path))
    assert res.entries == [] and not res.transient


def test_resolve_lrc_by_tags_and_index_refresh(tmp_path):
    (tmp_path / "x.lrc").write_text("[ar:Queen]\n[ti:Bohemian Rhapsody]\n[00:01.00]a\n", "utf-8")
    assert S.resolve_lrc(tmp_path, "Queen", "Bohemian Rhapsody (Remastered 2011)").name == "x.lrc"
    (tmp_path / "y.lrc").write_text("[ar:Abba]\n[ti:Waterloo]\n[00:01.00]a\n", "utf-8")   # file baru terdeteksi
    assert S.resolve_lrc(tmp_path, "Abba", "Waterloo").name == "y.lrc"
    assert S.resolve_lrc(tmp_path, "Other", "Waterloo").name == S.lrc_name("Other", "Waterloo")


def test_romaji_name_only_replaces_suffix():
    assert S.romaji_name("Foo.lrcx - Bar.lrc") == f"Foo.lrcx - Bar.romaji.v{S.ROMAN_VERSION}.lrc"


# --------------------------------------------------------------- versi/update
@pytest.mark.parametrize("new, cur, newer", [
    ("v1.10.0", "1.9", True), ("v1.2", "1.2.0", False), ("v2.0.0-beta", "1.0", False), ("1.0", "dev", False)])
def test_is_newer(new, cur, newer):
    assert S.is_newer(new, cur) is newer


def test_pick_asset_only_from_this_repo():
    good = {"name": "Senandung-1-x86_64.AppImage", "browser_download_url": S.REPO_URL + "/releases/download/v1/a.AppImage"}
    evil = {"name": "e.AppImage", "browser_download_url": "https://evil.com/releases/download/e.AppImage"}
    lookalike = {"name": "l.AppImage", "browser_download_url": S.REPO_URL + ".evil.com/releases/download/l.AppImage"}
    assert S.pick_asset([evil, lookalike, good], "appimage")[0] == good["browser_download_url"]
    assert S.pick_asset([evil, lookalike], "appimage")[0] in ("", None)


def test_sha_from_sums():
    text = "a" * 64 + "  one.AppImage\n" + "B" * 64 + " *two.exe\nbroken\n" + "c" * 10 + "  short\n"
    assert S.sha_from_sums(text, "one.AppImage") == "a" * 64
    assert S.sha_from_sums(text, "two.exe") == "b" * 64          # huruf besar dinormalkan, '*' (mode biner) dibuang
    assert S.sha_from_sums(text, "short") == "" and S.sha_from_sums(text, "nope") == ""


def test_pick_sums_url_only_from_this_repo():
    ok = {"name": "SHA256SUMS", "browser_download_url": S.REPO_URL + "/releases/download/v1/SHA256SUMS"}
    bad = {"name": "SHA256SUMS", "browser_download_url": "https://evil.com/releases/download/SHA256SUMS"}
    assert S.pick_sums_url([bad, ok]) == ok["browser_download_url"] and S.pick_sums_url([bad]) == ""


def test_updates_off(monkeypatch):
    monkeypatch.setattr(S, "APP_VERSION", "dev")
    assert S.updates_off() == "dev"
    monkeypatch.setattr(S, "APP_VERSION", "1.0")
    monkeypatch.delenv("SENANDUNG_DISTRO_PACKAGE", raising=False)
    assert S.updates_off() == ""
    monkeypatch.setenv("SENANDUNG_DISTRO_PACKAGE", "1")
    assert S.updates_off() == "pkg"


# ------------------------------------------------------------------ pemutar
def test_parse_aimp_info():
    parts = ["Alb", "Art", "", "C:\\m\\a.mp3", "", "Ttl"]
    raw = bytearray(0x58)
    struct.pack_into("<i", raw, 4, 1)
    struct.pack_into("<I", raw, 0x10, 180000)
    raw[0x28:0x40] = struct.pack("<6I", *[len(p) for p in parts])
    raw += b"".join(p.encode("utf-16-le") for p in parts)
    info = parse_aimp_info(bytes(raw))
    assert info and info["title"] == "Ttl" and info["artist"] == "Art"


def test_rank_player_and_short_name():
    assert rank_player("spotify", ["vlc", "spotify"], [], False) == 1        # peringkat = urutan di daftar prefer
    assert rank_player("mpv", ["spotify"], [], False) == 1                   # tak ada di prefer: di belakang
    assert rank_player("mpv", ["spotify"], [], True) is None                 # mode ketat: ditolak
    assert rank_player("org.chromium.chromium", ["spotify"], ["chromium"], False) is None   # blacklist
    assert short_name("firefox.instance1234") == "firefox"


# ---------------------------------------------------------------- romanisasi
def test_romanize_mixed_hanja_hangul_romanizes_hangul():
    out = romanize_lines(["漢字와 한글"])[0]
    assert "한" not in out and "글" not in out and out


@pytest.mark.parametrize("text", ["ქართული", "Հայերեն", "Привет", "你好世界", "안녕하세요", "日本語のテキスト"])
def test_romanize_produces_latin(text):
    out = romanize_lines([text])[0]
    assert out and "`" not in out


def test_romanize_latin_is_untouched():
    assert romanize_lines(["Hello world"]) == [""]


# ------------------------------------------------------------------- GUI
@pytest.fixture
def osd():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    S.set_language("en")
    o = S.OSD(S.Cfg(), demo=True)
    yield o
    o.close()
    app.processEvents()


def test_global_offset_is_applied(osd):
    osd.play_state, osd.base_pos, osd.local_offset = "Paused", 1000, 0
    osd.s["offset_ms"] = 0
    base = osd.pos_ms()
    osd.s["offset_ms"] = 500
    assert osd.pos_ms() - base == 500
    osd.local_offset = 100
    assert osd.pos_ms() - base == 600


def test_negative_cache_skips_second_search(osd):
    calls = []
    osd.loader.load = lambda *a, **k: calls.append(a[0])
    osd.track_key = ""
    info = dict(state="Playing", pos=0, length=100, clock=True, artist="X", title="Y", player="p", path="")
    osd.on_info(info)
    osd.on_lyrics("X|Y", S.LyricsResult())
    osd.track_key = ""
    osd.on_info(info)
    assert len(calls) == 1                         # tidak dicari ulang
    osd.on_lyrics("X|Y", S.LyricsResult(transient=True))
    assert "X|Y" not in osd.misses                 # galat jaringan tidak di-cache
    osd.track_key = ""
    osd.on_info(info)
    assert len(calls) == 2


def test_settings_dialog_tolerates_corrupt_values():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    cfg = S.Cfg()
    cfg.set("align", "bogus")
    cfg.set("romaji", "bogus")
    S.SettingsDialog(cfg)                          # tidak boleh melempar ValueError


def test_offscreen_position_is_ignored(osd):
    osd.move(10, 10)
    osd._restore_pos(90000, 90000)
    assert (osd.x(), osd.y()) == (10, 10)
