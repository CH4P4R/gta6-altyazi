"""İkon ve kurulum sihirbazı görsellerini üretir (Pillow).

    python packaging/make_assets.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).parent / "assets"
A1, A2 = (255, 79, 163), (255, 159, 67)


def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    names = (["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else
             ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"])
    dirs = ["C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation"]
    for n in names:
        for d in dirs:
            p = Path(d) / n
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def gradient(w: int, h: int, c0, c1, diagonal: bool = True) -> Image.Image:  # noqa: ANN001
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            t = ((x / max(w - 1, 1)) + (y / max(h - 1, 1))) / 2 if diagonal else y / max(h - 1, 1)
            px[x, y] = tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))
    return img


MARKA = Path(__file__).resolve().parents[1] / "altyazi" / "ui" / "marka"


def badge(size: int, text: bool | None = None) -> Image.Image:
    """Uygulama simgesi (tools/marka_gorsel.py çizer). Küçük boyutlarda yazısız sürüm: yazı okunmaz."""
    if text is None:
        text = size >= 200
    src = Image.open(MARKA / ("simge.png" if text else "simge_yazisiz.png")).convert("RGBA")
    return src.resize((size, size), Image.LANCZOS)


def scene(w: int, h: int) -> Image.Image:
    """Vice City gün batımı: degrade gökyüzü, güneş, şehir silueti, palmiyeler."""
    img = gradient(w, h, (8, 22, 66), (28, 92, 214), diagonal=False)
    d = ImageDraw.Draw(img, "RGBA")
    sun = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sun).ellipse((w * 0.15, h * 0.52, w * 0.85, h * 0.52 + w * 0.7), fill=(90, 170, 255, 150))
    img.paste(sun.filter(ImageFilter.GaussianBlur(w * 0.08)), (0, 0), sun.filter(ImageFilter.GaussianBlur(w * 0.08)))
    rnd = random.Random(6)
    x = 0
    while x < w:
        bw = rnd.uniform(w * 0.08, w * 0.2)
        bh = rnd.uniform(0.12, 0.4) * h
        d.rectangle((x, h - bh, x + bw - 2, h), fill=(6, 12, 34, 240))
        for wy in range(int(h - bh + 6), h - 4, max(6, h // 60)):
            if rnd.random() < 0.3:
                wx = x + rnd.uniform(2, max(3, bw - 6))
                d.rectangle((wx, wy, wx + 2, wy + 3), fill=(140, 200, 255, 140))
        x += bw
    for px in (w * 0.18, w * 0.78):
        top = (px + w * 0.04, h * 0.62)
        d.line((px, h, *top), fill=(4, 8, 22), width=max(3, w // 40))
        for dx, dy in ((-0.22, 0.05), (-0.14, -0.04), (0.0, -0.06), (0.14, -0.04), (0.22, 0.05)):
            d.line((*top, top[0] + dx * w, top[1] + dy * h + 6), fill=(4, 8, 22), width=max(2, w // 60))
    return img


def wizard_large(scale: int) -> Image.Image:
    w, h = 164 * scale, 314 * scale
    img = scene(w, h)
    d = ImageDraw.Draw(img, "RGBA")
    b = badge(52 * scale)
    img.paste(b, (16 * scale, 22 * scale), b)
    d.text((16 * scale, 84 * scale), "GTA6", font=font(26 * scale), fill="white")
    d.text((16 * scale, 114 * scale), "Altyazı", font=font(26 * scale), fill="white")
    d.text((17 * scale, 150 * scale), "CANLI TÜRKÇE ÇEVİRİ", font=font(8 * scale), fill=(190, 222, 255))
    return img


def main() -> int:
    OUT.mkdir(exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    small = [badge(s) for s in sizes]                 # 16-128: yazısız; 256: yazılı
    small[-1].save(OUT / "icon.ico", sizes=[(s, s) for s in sizes], append_images=small[:-1])
    badge(256).save(OUT / "icon.png")
    badge(1024).save(OUT / "icon.icns")          # macOS uygulama simgesi
    for scale in (1, 2):
        wizard_large(scale).save(OUT / f"wizard_large_{scale}x.bmp")
        small = Image.new("RGB", (55 * scale, 55 * scale), (8, 20, 56))
        b = badge(47 * scale)
        small.paste(b, (4 * scale, 4 * scale), b)
        small.save(OUT / f"wizard_small_{scale}x.bmp")
    print("Görseller:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
