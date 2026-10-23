#!/usr/bin/env python3
"""Buat set ikon modular dari gambar sumber.

    pip install pillow numpy
    python3 tools/make_icons.py

Sumber    : assets/icons/source/neon-music-and-lyrics.png  (PNG transparan, persegi)
Hasil     : assets/icons/png/senandung-<ukuran>.png          ikon aplikasi, 16 ... 512
            assets/icons/hicolor/<n>x<n>/apps/senandung.png  susunan tema ikon Linux
            assets/icons/senandung.ico / senandung.png      ikon Windows / master 512 px
            assets/icons/tray/senandung-tray-<ukuran>.png    ikon tray tanpa teks (16 ... 64)
            assets/icons/tray/senandung-tray.ico

Ikon tray dibuat otomatis dengan menyisakan not musik + mikrofon dari gambar sumber
(teks dan pita lirik dibuang). Bila kamu punya gambar tray sendiri, simpan sebagai
assets/icons/source/tray-source.png (persegi, tanpa teks); skrip akan memakainya
sebagai pengganti pemotongan otomatis.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
ICONS = ROOT / "assets" / "icons"
SOURCE = ICONS / "source" / "neon-music-and-lyrics.png"
TRAY_SOURCE = ICONS / "source" / "tray-source.png"
NAME = "senandung"
SIZES = (16, 24, 32, 48, 64, 96, 128, 256, 512)
ICO_SIZES = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]
TRAY_SIZES = (16, 22, 24, 32, 48, 64)

# --- pemotongan otomatis ikon tray (koordinat piksel pada gambar sumber 1254 x 1254) ---
CROP_BOX = (300, 270, 1040, 930)        # area sekitar not + mikrofon
TRAY_BG = (4, 6, 18, 255)               # latar gelap, senada dengan ikon utama
BORDER = ((44, 255, 107), (25, 200, 255), (192, 75, 255))   # hijau -> cyan -> ungu


def square_crop(im: Image.Image, margin: float = 0.02) -> Image.Image:
    """Pangkas area transparan di tepi, lalu jadikan persegi dengan sedikit margin."""
    box = im.getchannel("A").getbbox()
    if box:
        im = im.crop(box)
    side = round(max(im.size) * (1 + margin * 2))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2), im)
    return canvas


def _keep_mask(size, ox, oy):
    """Mask area yang dipertahankan: not + mikrofon (tanpa teks dan pita lirik)."""
    def pts(p):
        return [(x + ox, y + oy) for x, y in p]

    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    d.polygon(pts([(180, 20), (720, 20), (720, 280), (640, 280), (640, 430),
                   (400, 430), (400, 625), (180, 625)]), fill=255)
    d.rectangle([30 + ox, 430 + oy, 200 + ox, 625 + oy], fill=255)      # kepala not
    d.ellipse([490 + ox, 70 + oy, 718 + ox, 290 + oy], fill=255)        # kepala mikrofon
    for cut in ([(650, 0), (760, 0), (760, 110), (650, 110)],           # sisa huruf judul
                [(205, 112), (480, 25), (480, 0), (150, 0), (150, 112)],  # tepi atas pita kiri
                [(575, 320), (760, 320), (760, 680), (390, 680), (410, 560)]):  # pita kanan bawah
        d.polygon(pts(cut), fill=0)
    return m.filter(ImageFilter.GaussianBlur(9))


def _gradient(size):
    w, h = size
    t = (np.add.outer(np.arange(h), np.arange(w)) / (w + h - 2)).clip(0, 1)
    out = np.zeros((h, w, 3), np.float32)
    for ch in range(3):
        out[..., ch] = np.interp(t, (0, .5, 1), [c[ch] for c in BORDER])
    return Image.fromarray(out.astype("uint8"), "RGB")


def make_tray_master(side: int = 1024) -> Image.Image:
    """Ikon tray: not + mikrofon di atas kotak membulat gelap dengan bingkai neon."""
    if TRAY_SOURCE.is_file():
        return square_crop(Image.open(TRAY_SOURCE).convert("RGBA"), 0).resize((side, side), Image.LANCZOS)

    src = Image.open(SOURCE).convert("RGBA")
    ox, oy = CROP_BOX[:2]
    # mask ditulis dalam koordinat crop; digeser ke koordinat gambar sumber
    keep = _keep_mask(src.size, ox, oy)
    src.putalpha(ImageChops.multiply(src.getchannel("A"), keep))
    art = Image.new("RGBA", src.size, TRAY_BG)
    art.alpha_composite(src)
    art = art.crop(CROP_BOX)

    # kanvas persegi berisi gambar yang diperbesar + bingkai
    inner = int(side * .90)
    scale = min(inner / art.width, inner / art.height)
    art = art.resize((round(art.width * scale), round(art.height * scale)), Image.LANCZOS)
    canvas = Image.new("RGBA", (side, side), TRAY_BG)
    canvas.alpha_composite(art, ((side - art.width) // 2, (side - art.height) // 2))

    radius, ring = int(side * .2), max(3, int(side * .045))
    round_mask = Image.new("L", (side, side), 0)
    ImageDraw.Draw(round_mask).rounded_rectangle([0, 0, side - 1, side - 1], radius, fill=255)
    ring_mask = Image.new("L", (side, side), 0)
    rd = ImageDraw.Draw(ring_mask)
    rd.rounded_rectangle([0, 0, side - 1, side - 1], radius, fill=255)
    rd.rounded_rectangle([ring, ring, side - 1 - ring, side - 1 - ring], radius - ring, fill=0)
    canvas.paste(_gradient((side, side)), (0, 0), ring_mask)
    canvas.putalpha(round_mask)
    return canvas


def main():
    master = square_crop(Image.open(SOURCE).convert("RGBA"))
    (ICONS / "png").mkdir(parents=True, exist_ok=True)
    for s in SIZES:
        img = master.resize((s, s), Image.LANCZOS)
        img.save(ICONS / "png" / f"{NAME}-{s}.png", optimize=True)
        d = ICONS / "hicolor" / f"{s}x{s}" / "apps"
        d.mkdir(parents=True, exist_ok=True)
        img.save(d / f"{NAME}.png", optimize=True)
    master.resize((256, 256), Image.LANCZOS).save(ICONS / f"{NAME}.ico", sizes=ICO_SIZES)
    master.resize((512, 512), Image.LANCZOS).save(ICONS / f"{NAME}.png", optimize=True)

    tray = make_tray_master()
    (ICONS / "tray").mkdir(parents=True, exist_ok=True)
    for s in TRAY_SIZES:
        tray.resize((s, s), Image.LANCZOS).save(ICONS / "tray" / f"{NAME}-tray-{s}.png", optimize=True)
    tray.resize((256, 256), Image.LANCZOS).save(
        ICONS / "tray" / f"{NAME}-tray.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print(f"Selesai: {len(SIZES)} ukuran ikon aplikasi + {len(TRAY_SIZES)} ukuran ikon tray di {ICONS}")


if __name__ == "__main__":
    main()
