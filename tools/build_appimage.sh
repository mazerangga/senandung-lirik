#!/usr/bin/env bash
# Bangun AppImage Senandung (Linux x86_64).
#
#   bash tools/build_appimage.sh 1.2          # hasil: dist/Senandung-1.2-x86_64.AppImage
#
# Dipanggil CI (release.yml). Bangun di distro LAMA (ubuntu-22.04) supaya jalan di banyak distro.
# Versi diisi lebih dulu ke senandung.py oleh  python tools/stamp_version.py <versi>  (CI melakukannya).
# AppImage tetap membutuhkan `playerctl` di sistem pengguna (dipakai membaca pemutar).
set -euo pipefail
cd "$(dirname "$0")/.."

VER="${1:?pemakaian: build_appimage.sh <versi>}"
OUT="dist/Senandung-${VER}-x86_64.AppImage"
rm -rf build AppDir "dist/senandung" "$OUT"
mkdir -p dist

python3 -m pip install --quiet pyinstaller PySide6-Essentials pykakasi pypinyin korean-romanizer unidecode

# Qt 6 (xcb) butuh libxcb-cursor0, yang tidak ikut di wheel PySide6 dan tidak ada di semua distro.
XCB_CURSOR="$(ls /usr/lib/x86_64-linux-gnu/libxcb-cursor.so.0 2>/dev/null || true)"
EXTRA=()
[ -n "$XCB_CURSOR" ] && EXTRA+=(--add-binary "$XCB_CURSOR:.")

# Opsi disamakan dengan build Windows (.exe) di release.yml, tanpa winrt dan tanpa --windowed.
python3 -m PyInstaller --noconfirm --clean --onedir --name senandung \
  --collect-data pykakasi --collect-submodules unidecode \
  --hidden-import pypinyin --hidden-import korean_romanizer.romanizer \
  --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick \
  --exclude-module PySide6.QtQuickWidgets --exclude-module PySide6.QtWebEngineCore \
  --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtWebChannel \
  --exclude-module PySide6.Qt3DCore --exclude-module PySide6.QtMultimedia \
  --exclude-module PySide6.QtPdf --exclude-module PySide6.QtCharts \
  --exclude-module PySide6.QtSql --exclude-module PySide6.QtOpenGL \
  --exclude-module PySide6.QtSvg --exclude-module PySide6.QtDesigner \
  --exclude-module PySide6.QtTest --exclude-module PySide6.QtHelp \
  --exclude-module tkinter \
  --add-data "assets:assets" "${EXTRA[@]}" senandung.py

mkdir -p AppDir/usr/bin
cp -r dist/senandung/. AppDir/usr/bin/
cp assets/icons/png/senandung-256.png AppDir/senandung.png

cat > AppDir/senandung.desktop <<DESKTOP
[Desktop Entry]
Type=Application
Name=Senandung
Comment=Synced on-screen lyrics for your desktop
Exec=senandung
Icon=senandung
Categories=AudioVideo;Audio;Player;
StartupNotify=false
DESKTOP

cat > AppDir/AppRun <<'APPRUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/senandung" "$@"
APPRUN
chmod +x AppDir/AppRun

TOOL=build/appimagetool-x86_64.AppImage
if [ ! -x "$TOOL" ]; then
  mkdir -p build
  curl -fsSL -o "$TOOL" https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
  chmod +x "$TOOL"
fi
# --appimage-extract-and-run: runner CI dan container tidak punya FUSE
ARCH=x86_64 "$TOOL" --appimage-extract-and-run AppDir "$OUT"
echo "==> $OUT"
