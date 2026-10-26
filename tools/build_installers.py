#!/usr/bin/env python3
"""Bangun installer satu-file (Linux .sh dan Windows .ps1) dari source terbaru.

    python3 tools/build_installers.py              # hasil di dist/
    python3 tools/build_installers.py --out rilis  # folder lain

Installer di packaging/ adalah TEMPLATE tanpa payload. Skrip ini mengambil
  - senandung.py
  - assets/icons/png/*.png (<= 256 px), assets/icons/tray/*.png, assets/icons/senandung.ico
lalu menyisipkannya ke dalam installer sebagai base64:
  - Linux  : tar.gz setelah penanda  __ARCHIVE__
  - Windows: zip di dalam here-string  $script:Payload = @' ... '@

Hasilnya selalu sama untuk masukan yang sama (tanpa cap waktu), jadi aman dibandingkan
lewat SHA256SUMS. Jalankan setiap kali senandung.py atau ikon berubah, sebelum merilis.
Jika ikon belum ada, jalankan dulu:  python3 tools/make_icons.py
"""
import argparse
import base64
import gzip
import hashlib
import io
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = "senandung"
SCRIPT = ROOT / "senandung.py"
APP_PACKAGES = ("romanize", "players")      # paket Python di samping senandung.py
ICONS = ROOT / "assets" / "icons"
SH_TEMPLATE = ROOT / "packaging" / "linux" / "install-senandung.sh"
PS1_TEMPLATE = ROOT / "packaging" / "windows" / "install-senandung.ps1"
PNG_SIZES = (16, 24, 32, 48, 64, 96, 128, 256)     # 512 px tidak dibawa: memperbesar installer
TRAY_SIZES = (16, 22, 24, 32, 48, 64)
SH_MARK = b"\n__ARCHIVE__\n"
SH_VERSION = re.compile(rb'^VERSION="[^"]*"', re.M)
PS1_VERSION = re.compile(rb'\$Version\s*=\s*"[^"]*"')
VERSION_OK = re.compile(r"[0-9A-Za-z][0-9A-Za-z._-]*")   # tag masuk ke skrip shell: batasi karakternya
PS1_PAYLOAD = re.compile(rb"(\$script:Payload\s*=\s*@'(?:\r\n|\n)?)(.*?)((?:\r\n|\n)?'@)", re.S)

def die(msg):
    sys.exit(f"XX  {msg}")


def say(msg):
    print(f"==> {msg}")


def stamp_version(data, pattern, fmt, version):
    """Ganti nomor versi di template. Tanpa versi (build lokal) template dibiarkan apa adanya."""
    if not version:
        return data
    new, n = pattern.subn(lambda _: fmt.format(version).encode(), data, count=1)
    if n != 1:
        die("baris versi tidak ditemukan di template installer")
    return new


def payload_files(with_ico):
    """Daftar (nama di arsip, isi). Urutan tetap supaya hasil deterministik."""
    items = [("senandung.py", SCRIPT.read_bytes())]
    # modul aplikasi ikut dibawa; urutan nama tetap supaya hasil deterministik
    for pkg in APP_PACKAGES:
        items += [(f"{pkg}/{p.name}", p.read_bytes()) for p in sorted((ROOT / pkg).glob("*.py"))]
    wanted = [f"assets/icons/png/{APP}-{n}.png" for n in PNG_SIZES]
    wanted += [f"assets/icons/tray/{APP}-tray-{n}.png" for n in TRAY_SIZES]
    if with_ico:
        wanted.append(f"assets/icons/{APP}.ico")
    missing = [w for w in wanted if not (ROOT / w).is_file()]
    if missing:
        die("ikon belum lengkap (" + ", ".join(missing[:3]) + (" ..." if len(missing) > 3 else "")
            + ").\n    Jalankan dulu: python3 tools/make_icons.py")
    items += [(w, (ROOT / w).read_bytes()) for w in wanted]
    return items


def make_targz(items):
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, compresslevel=9) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as tar:
            for name, data in items:
                ti = tarfile.TarInfo(name)
                ti.size, ti.mtime, ti.mode = len(data), 0, 0o644
                ti.uid = ti.gid = 0
                ti.uname = ti.gname = ""
                tar.addfile(ti, io.BytesIO(data))
    return raw.getvalue()


def make_zip(items):
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in items:
            zi = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, data)
    return raw.getvalue()


def wrap64(data, eol):
    b = base64.b64encode(data)
    return eol.join(b[i:i + 76] for i in range(0, len(b), 76))


def build_sh(out_dir, version=""):
    tpl = SH_TEMPLATE.read_bytes()
    if tpl.count(SH_MARK) != 1:
        die(f"penanda __ARCHIVE__ harus tepat satu kali di {SH_TEMPLATE.name}")
    head = tpl[: tpl.index(SH_MARK) + len(SH_MARK)]       # buang payload lama bila ada
    head = stamp_version(head, SH_VERSION, 'VERSION="{}"', version)
    out = out_dir / SH_TEMPLATE.name
    out.write_bytes(head + wrap64(make_targz(payload_files(with_ico=False)), b"\n") + b"\n")
    out.chmod(0o755)
    return out


def build_ps1(out_dir, version=""):
    tpl_bytes = PS1_TEMPLATE.read_bytes()
    
    # Cari pola payload secara fleksibel tanpa terikat line-ending yang kaku
    # Kita cari penanda awal dan akhir blok payload
    start_marker = b"$script:Payload = @'"
    end_marker = b"'@"
    
    if tpl_bytes.count(start_marker) != 1 or tpl_bytes.count(end_marker) < 1:
        die(f"blok $script:Payload = @' ... '@ harus tepat satu di {PS1_TEMPLATE.name}")
        
    # Buat payload zip yang akan disisipkan
    body = wrap64(make_zip(payload_files(with_ico=True)), b"\r\n")
    
    # Ganti bagian di antara penanda
    start_idx = tpl_bytes.find(start_marker) + len(start_marker)
    end_idx = tpl_bytes.find(end_marker, start_idx)
    
    # Rakit ulang file ps1 dengan payload baru di tengahnya
    new_ps1_bytes = tpl_bytes[:start_idx] + b"\r\n" + body + b"\r\n" + tpl_bytes[end_idx:]
    new_ps1_bytes = stamp_version(new_ps1_bytes, PS1_VERSION, '$Version = "{}"', version)
    
    out = out_dir / PS1_TEMPLATE.name
    out.write_bytes(new_ps1_bytes)
    return out


def verify(sh, ps1):
    """Bongkar payload dari hasil akhir lalu cocokkan dengan source."""
    want = hashlib.sha256(SCRIPT.read_bytes()).hexdigest()

    data = sh.read_bytes()
    raw = base64.b64decode(data[data.index(SH_MARK) + len(SH_MARK):])
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        names = tar.getnames()
        got = hashlib.sha256(tar.extractfile("senandung.py").read()).hexdigest()
    if got != want or f"assets/icons/png/{APP}-256.png" not in names:
        die("verifikasi payload .sh gagal")

    m = PS1_PAYLOAD.search(ps1.read_bytes())
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(re.sub(rb"\s", b"", m.group(2))))) as z:
        names = z.namelist()
        got = hashlib.sha256(z.read("senandung.py")).hexdigest()
        if z.testzip() is not None or got != want or f"assets/icons/{APP}.ico" not in names:
            die("verifikasi payload .ps1 gagal")

    if shutil.which("bash"):
        if subprocess.run(["bash", "-n", str(sh)]).returncode != 0:
            die("bash -n menemukan kesalahan sintaks pada installer .sh")
    say("verifikasi: isi payload cocok dengan source, sintaks .sh valid")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(ROOT / "dist"), help="folder hasil (bawaan: dist/)")
    ap.add_argument("--version", default=os.environ.get("SENANDUNG_VERSION", ""),
                    help="nomor versi untuk installer (mis. 1.2; awalan 'v' dibuang). "
                         "Bawaan: env SENANDUNG_VERSION, atau biarkan seperti di template")
    ap.add_argument("--no-verify", action="store_true", help="lewati verifikasi payload")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as tmp:           # cek sintaks tanpa menulis __pycache__
        try:
            py_compile.compile(str(SCRIPT), cfile=str(Path(tmp) / "x.pyc"), doraise=True)
        except py_compile.PyCompileError as e:
            die(f"senandung.py bermasalah, installer tidak dibuat:\n{e}")

    version = args.version.strip().lstrip("vV")
    if version and not VERSION_OK.fullmatch(version):
        die(f"nomor versi tidak valid: {args.version!r}")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    sh, ps1 = build_sh(out_dir, version), build_ps1(out_dir, version)
    if not args.no_verify:
        verify(sh, ps1)

    if version:
        say(f"versi installer: {version}")
    sums = []
    for f in (sh, ps1):
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        sums.append(f"{h}  {f.name}")
        say(f"{f.relative_to(ROOT) if f.is_relative_to(ROOT) else f}  ({f.stat().st_size / 1024:.0f} KB)")
    (out_dir / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
