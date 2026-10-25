#!/usr/bin/env bash
# Senandung installer - single file, installs into your home directory (~/.local), no root needed
# except to install system packages (playerctl etc.), which are asked about first.
#
#   bash install-senandung.sh                 install
#   bash install-senandung.sh --uninstall     remove (--purge also removes settings)
#   options: --autostart | --no-autostart | --no-system-deps | --yes | --lang id|en | --help
#
# Language of this installer: --lang id|en, or SENANDUNG_LANG=id|en; otherwise it follows $LANG.
set -euo pipefail

APP="senandung"
VERSION="1.0"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
CONF="${XDG_CONFIG_HOME:-$HOME/.config}"
PREFIX="$DATA/$APP"
BIN_DIR="$HOME/.local/bin"
APPS_DIR="$DATA/applications"
HICOLOR="$DATA/icons/hicolor"
ICON_DIR="$HICOLOR/scalable/apps"      # only to clean up the svg icon of old versions
AUTOSTART_DIR="$CONF/autostart"
PIP_PKGS=(PySide6 pykakasi pypinyin korean-romanizer unidecode)

# ------------------------------------------------------------------ language / bahasa
# Pilihan: --lang id|en  >  SENANDUNG_LANG  >  bahasa sistem (LC_ALL / LC_MESSAGES / LANG)
UI=en
for l in "${LC_ALL:-}" "${LC_MESSAGES:-}" "${LANG:-}"; do
  if [ -n "$l" ]; then case "$l" in id*|in_*) UI=id ;; esac; break; fi
done
LANG_ARG="${SENANDUNG_LANG:-}"; prev=""
for a in "$@"; do                                   # baca --lang lebih dulu supaya pesan galat ikut bahasanya
  [ "$prev" = "--lang" ] && LANG_ARG="$a"
  case "$a" in --lang=*) LANG_ARG="${a#--lang=}" ;; esac
  prev="$a"
done
case "$LANG_ARG" in
  id|en) UI="$LANG_ARG" ;;
  "") ;;
  *) printf 'XX  --lang must be id or en / --lang harus id atau en\n' >&2; exit 2 ;;
esac

T() {   # T kunci [argumen...]  -> teks sesuai bahasa (pakai printf, placeholder %s)
  local k="$1" s=""; shift
  if [ "$UI" = id ]; then
    case "$k" in
      unknown_opt)   s='Opsi tidak dikenal: %s (coba --help)' ;;
      removing)      s='Menghapus Senandung' ;;
      purged)        s='Pengaturan ikut dihapus' ;;
      uninstalled)   s='Selesai. Folder lirik (~/lyrics) tidak dihapus.' ;;
      installing)    s='Memasang Senandung %s' ;;
      no_python)     s='python3 tidak ditemukan.' ;;
      py_old)        s='Butuh Python 3.10 atau lebih baru (terpasang: %s).' ;;
      ask_sys)       s='Pasang paket sistem (%s) dengan sudo?' ;;
      sys_failed)    s='Pemasangan paket sistem gagal; lanjut, tapi pastikan playerctl terpasang.' ;;
      no_sudo)       s='sudo tidak ada. Jalankan sebagai root: %s' ;;
      unknown_distro) s="Distro tidak dikenali. Pastikan 'playerctl' dan pustaka xcb-cursor terpasang." ;;
      no_playerctl)  s='playerctl belum terpasang - aplikasi membutuhkannya untuk membaca pemutar.' ;;
      bad_archive)   s='Arsip di dalam installer rusak.' ;;
      no_script)     s='senandung.py tidak ada di arsip.' ;;
      no_icons)      s='folder ikon (assets/icons/png) tidak ada di arsip.' ;;
      make_venv)     s='Membuat lingkungan Python di %s' ;;
      venv_failed)   s='Gagal membuat venv (Debian/Ubuntu: pasang python3-venv).' ;;
      dl_mods)       s='Mengunduh modul (PySide6 dll., sekitar 200 MB; mohon tunggu)' ;;
      pip_failed)    s='pip gagal mengunduh modul. Periksa koneksi internet lalu jalankan installer lagi.' ;;
      import_failed) s='Modul Python terpasang tetapi tidak bisa diimpor.' ;;
      ask_autostart) s='Jalankan otomatis saat login?' ;;
      autostart_on)  s='Autostart aktif' ;;
      done)          s='Selesai! Senandung %s terpasang.' ;;
      hint_run)      s="  Jalankan  : senandung          (atau cari 'Senandung' di menu aplikasi)" ;;
      hint_demo)     s='  Pratinjau : senandung --demo   (lirik contoh, tanpa pemutar)' ;;
      hint_close)    s='  Close     : tombol close menyembunyikan ke system tray; muncul lagi saat lagu berganti' ;;
      hint_gnome)    s='  Catatan   : GNOME butuh ekstensi AppIndicator agar ikon tray tampil' ;;
      hint_remove)   s='  Hapus     : bash %s --uninstall' ;;
      path_warn)     s='%s belum ada di PATH; pakai menu aplikasi atau tambahkan ke PATH.' ;;
    esac
  else
    case "$k" in
      unknown_opt)   s='Unknown option: %s (try --help)' ;;
      removing)      s='Removing Senandung' ;;
      purged)        s='Settings were removed too' ;;
      uninstalled)   s='Done. The lyrics folder (~/lyrics) was kept.' ;;
      installing)    s='Installing Senandung %s' ;;
      no_python)     s='python3 not found.' ;;
      py_old)        s='Python 3.10 or newer is required (installed: %s).' ;;
      ask_sys)       s='Install system packages (%s) with sudo?' ;;
      sys_failed)    s='System package install failed; continuing, but make sure playerctl is installed.' ;;
      no_sudo)       s='sudo is not available. Run as root: %s' ;;
      unknown_distro) s="Unrecognized distro. Make sure 'playerctl' and the xcb-cursor library are installed." ;;
      no_playerctl)  s='playerctl is not installed - the app needs it to read your media player.' ;;
      bad_archive)   s='The archive inside the installer is corrupt.' ;;
      no_script)     s='senandung.py is missing from the archive.' ;;
      no_icons)      s='the icon folder (assets/icons/png) is missing from the archive.' ;;
      make_venv)     s='Creating Python environment in %s' ;;
      venv_failed)   s='Could not create the venv (Debian/Ubuntu: install python3-venv).' ;;
      dl_mods)       s='Downloading modules (PySide6 etc., about 200 MB; please wait)' ;;
      pip_failed)    s='pip failed to download the modules. Check your internet connection and run the installer again.' ;;
      import_failed) s='The Python modules installed but cannot be imported.' ;;
      ask_autostart) s='Start automatically at login?' ;;
      autostart_on)  s='Autostart enabled' ;;
      done)          s='Done! Senandung %s is installed.' ;;
      hint_run)      s="  Run       : senandung          (or find 'Senandung' in your application menu)" ;;
      hint_demo)     s='  Preview   : senandung --demo   (sample lyrics, no player needed)' ;;
      hint_close)    s='  Close     : the close button hides to the system tray; it reappears when the song changes' ;;
      hint_gnome)    s='  Note      : GNOME needs the AppIndicator extension to show the tray icon' ;;
      hint_remove)   s='  Uninstall : bash %s --uninstall' ;;
      path_warn)     s='%s is not in your PATH; use the application menu or add it to your PATH.' ;;
    esac
  fi
  # shellcheck disable=SC2059
  printf "$s" "$@"
}

usage() {
  if [ "$UI" = id ]; then cat <<'TXT'
Installer Senandung - satu file, memasang ke direktori pengguna (~/.local), tanpa root
kecuali untuk memasang paket sistem (playerctl dkk.) yang akan ditanyakan dulu.

  bash install-senandung.sh                 pasang
  bash install-senandung.sh --uninstall     hapus (--purge juga hapus pengaturan)
  opsi: --autostart | --no-autostart | --no-system-deps | --yes | --lang id|en | --help

Bahasa installer: --lang id|en, atau SENANDUNG_LANG=id|en; bila tidak diisi, mengikuti $LANG.
TXT
  else cat <<'TXT'
Senandung installer - single file, installs into your home directory (~/.local), no root needed
except to install system packages (playerctl etc.), which are asked about first.

  bash install-senandung.sh                 install
  bash install-senandung.sh --uninstall     remove (--purge also removes settings)
  options: --autostart | --no-autostart | --no-system-deps | --yes | --lang id|en | --help

Installer language: --lang id|en, or SENANDUNG_LANG=id|en; otherwise it follows $LANG.
TXT
  fi
}

ACTION=install; PURGE=0; ASSUME_YES=0; AUTOSTART=ask; SYSDEPS=1
while [ $# -gt 0 ]; do
  case "$1" in
    --uninstall) ACTION=uninstall ;;
    --purge) PURGE=1 ;;
    -y|--yes) ASSUME_YES=1 ;;
    --autostart) AUTOSTART=yes ;;
    --no-autostart) AUTOSTART=no ;;
    --no-system-deps) SYSDEPS=0 ;;
    --lang) [ $# -gt 1 ] && shift ;;               # nilainya sudah dibaca di atas
    --lang=*) ;;
    -h|--help) usage; exit 0 ;;
    *) printf '\033[1;31mXX\033[0m  %s\n' "$(T unknown_opt "$1")" >&2; exit 2 ;;
  esac
  shift
done

say()  { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m  %s\n' "$*" >&2; }
die()  { printf '\033[1;31mXX\033[0m  %s\n' "$*" >&2; exit 1; }
ask() {   # ask "question" y|n   -> status 0 if the answer is yes (y / j accepted)
  if [ "$ASSUME_YES" = 1 ] || [ ! -t 0 ]; then [ "$2" = y ]; return; fi
  local a; read -r -p "$1 [$([ "$2" = y ] && echo Y/n || echo y/N)] " a || a=""
  a="${a:-$2}"; [[ "$a" =~ ^[YyJj] ]]
}

refresh_caches() {
  command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS_DIR" 2>/dev/null || true
  command -v kbuildsycoca6 >/dev/null 2>&1 && kbuildsycoca6 >/dev/null 2>&1 || true
  command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -f -t "$HICOLOR" 2>/dev/null || true
}

# ------------------------------------------------------------------ uninstall
if [ "$ACTION" = uninstall ]; then
  say "$(T removing)"
  pkill -f "$PREFIX/senandung.py" 2>/dev/null || true
  rm -rf "$PREFIX"
  rm -f "$BIN_DIR/$APP" "$APPS_DIR/$APP.desktop" "$AUTOSTART_DIR/$APP.desktop" "$ICON_DIR/$APP.svg"
  rm -f "$HICOLOR"/*/apps/"$APP.png"
  [ "$PURGE" = 1 ] && rm -rf "$CONF/$APP" && say "$(T purged)"
  refresh_caches
  say "$(T uninstalled)"
  exit 0
fi

# ------------------------------------------------------------------ checks
say "$(T installing "$VERSION")"
command -v python3 >/dev/null 2>&1 || die "$(T no_python)"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' \
  || die "$(T py_old "$(python3 -V 2>&1)")"

# ------------------------------------------------------------------ system packages
if [ "$SYSDEPS" = 1 ]; then
  ID_LIKE_ALL=""; [ -r /etc/os-release ] && ID_LIKE_ALL="$(. /etc/os-release; echo "${ID:-} ${ID_LIKE:-}")"
  CMD=()
  case " $ID_LIKE_ALL " in
    *" arch "*)                  CMD=(pacman -S --needed --noconfirm playerctl xcb-util-cursor) ;;
    *" debian "*|*" ubuntu "*)   CMD=(apt-get install -y playerctl libxcb-cursor0 python3-venv) ;;
    *" fedora "*|*" rhel "*)     CMD=(dnf install -y playerctl xcb-util-cursor) ;;
    *" suse "*|*" opensuse "*)   CMD=(zypper --non-interactive install playerctl libxcb-cursor0) ;;
  esac
  if [ "${#CMD[@]}" -gt 0 ]; then
    if ask "$(T ask_sys "${CMD[*]: -3}")" y; then
      if command -v sudo >/dev/null 2>&1; then
        sudo "${CMD[@]}" || warn "$(T sys_failed)"
      else
        warn "$(T no_sudo "${CMD[*]}")"
      fi
    fi
  else
    warn "$(T unknown_distro)"
  fi
fi
command -v playerctl >/dev/null 2>&1 || warn "$(T no_playerctl)"

# ------------------------------------------------------------------ extract files from inside the installer
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
awk '/^__ARCHIVE__$/{f=1;next} f' "$0" | base64 -d | tar xz -C "$TMP" || die "$(T bad_archive)"
[ -f "$TMP/senandung.py" ] || die "$(T no_script)"
for pkg in romanize players; do [ -f "$TMP/$pkg/__init__.py" ] || die "$(T no_script)"; done
[ -d "$TMP/assets/icons/png" ] || die "$(T no_icons)"

# ------------------------------------------------------------------ Python environment
mkdir -p "$PREFIX" "$BIN_DIR" "$APPS_DIR" "$ICON_DIR"
say "$(T make_venv "$PREFIX/venv")"
rm -rf "$PREFIX/venv"
python3 -m venv "$PREFIX/venv" || die "$(T venv_failed)"
say "$(T dl_mods)"
"$PREFIX/venv/bin/pip" install --disable-pip-version-check -q "${PIP_PKGS[@]}" \
  || die "$(T pip_failed)"
"$PREFIX/venv/bin/python" -c 'import PySide6.QtWidgets, pykakasi, pypinyin, korean_romanizer, unidecode' \
  || die "$(T import_failed)"

# ------------------------------------------------------------------ app files
pkill -f "$PREFIX/senandung.py" 2>/dev/null || true     # stop an older running version
install -m 0644 "$TMP/senandung.py" "$PREFIX/senandung.py"
for pkg in romanize players; do rm -rf "$PREFIX/$pkg"; cp -r "$TMP/$pkg" "$PREFIX/$pkg"; done
rm -rf "$PREFIX/assets"; mkdir -p "$PREFIX/assets"
cp -r "$TMP/assets/icons" "$PREFIX/assets/icons"
rm -f "$ICON_DIR/$APP.svg"      # an old svg icon would override the PNGs if left behind
for f in "$PREFIX"/assets/icons/png/"$APP"-*.png; do
  n="${f##*-}"; n="${n%.png}"
  install -Dm 0644 "$f" "$HICOLOR/${n}x${n}/apps/$APP.png"
done

cat > "$BIN_DIR/$APP" <<EOS
#!/bin/sh
# Default: run through XWayland (--x11) so the position is remembered and "always on top" works.
# Native Wayland:  SENANDUNG_NATIVE=1 senandung
if [ -n "\${SENANDUNG_NATIVE:-}" ]; then
  exec "$PREFIX/venv/bin/python" "$PREFIX/senandung.py" "\$@"
fi
exec "$PREFIX/venv/bin/python" "$PREFIX/senandung.py" --x11 "\$@"
EOS
chmod +x "$BIN_DIR/$APP"

cat > "$APPS_DIR/$APP.desktop" <<EOS
[Desktop Entry]
Type=Application
Name=Senandung
GenericName=Lyrics overlay
GenericName[id]=Overlay lirik
Comment=Synced, transparent on-screen lyrics overlay for your desktop
Comment[id]=Lirik tersinkron transparan di desktop
Keywords=lyrics;lrc;karaoke;overlay;osd;
Exec=$BIN_DIR/$APP
Icon=$APP
Terminal=false
Categories=AudioVideo;Audio;Player;
StartupWMClass=$APP
EOS

if [ "$AUTOSTART" = ask ]; then ask "$(T ask_autostart)" n && AUTOSTART=yes || AUTOSTART=no; fi
if [ "$AUTOSTART" = yes ]; then
  mkdir -p "$AUTOSTART_DIR"; cp "$APPS_DIR/$APP.desktop" "$AUTOSTART_DIR/$APP.desktop"
  say "$(T autostart_on)"
fi
refresh_caches

say "$(T done "$VERSION")"
echo
T hint_run; echo
T hint_demo; echo
T hint_close; echo
T hint_gnome; echo
T hint_remove "$(basename "$0")"; echo
case ":$PATH:" in *":$BIN_DIR:"*) ;; *) warn "$(T path_warn "$BIN_DIR")" ;; esac
exit 0
__ARCHIVE__
