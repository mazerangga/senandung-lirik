"""Pengaturan tes: Qt tanpa layar, QSettings terisolasi, dan root repo di sys.path."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="senandung-test-")   # jangan sentuh konfigurasi asli
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
