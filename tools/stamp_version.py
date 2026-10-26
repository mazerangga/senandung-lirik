#!/usr/bin/env python3
"""Isi APP_VERSION di senandung.py dengan nomor versi (dipakai CI dari nama tag rilis).

    python3 tools/stamp_version.py 1.2      # v1.2 juga boleh; awalan 'v' dibuang

Build lokal tidak perlu menjalankan ini: APP_VERSION = "dev" mematikan cek update.
"""
import re
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "senandung.py"
OK = re.compile(r"\d+(\.\d+)*")          # hanya angka dan titik: nilai ini masuk ke kode Python


def main():
    if len(sys.argv) != 2:
        sys.exit("pemakaian: stamp_version.py <versi>")
    version = sys.argv[1].strip().lstrip("vV")
    if not OK.fullmatch(version):
        sys.exit(f"XX  nomor versi tidak valid: {sys.argv[1]!r} (contoh: 1.2)")
    text = SCRIPT.read_text(encoding="utf-8")
    new, n = re.subn(r'^APP_VERSION = "[^"]*"', f'APP_VERSION = "{version}"', text, count=1, flags=re.M)
    if n != 1:
        sys.exit("XX  baris APP_VERSION tidak ditemukan di senandung.py")
    SCRIPT.write_text(new, encoding="utf-8", newline="")
    print(f"==> APP_VERSION = {version}")


if __name__ == "__main__":
    main()
