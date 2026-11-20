"""Test için GTA tarzı sahte kare üretici (gürültülü arka plan + konturlu altyazı + sol üst yardım kutusu)."""

from __future__ import annotations

import glob

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def _font(size: int) -> ImageFont.FreeTypeFont:
    for pat in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf",   # macOS
                "/System/Library/Fonts/Supplemental/Verdana Bold.ttf",
                "/usr/share/fonts/**/*Bold*.ttf"):
        for p in glob.glob(pat, recursive=True):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def background(w: int, h: int, seed: int = 0, bright_sky: bool = True) -> np.ndarray:
    rng = np.random.default_rng(seed)
    small = rng.integers(20, 200, (9, 16, 3), dtype=np.uint8)
    bg = cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)
    if bright_sky:  # üst yarı açık mavi/beyazımsı gökyüzü, altta da beyaz bir duvar parçası
        bg[: h // 3] = (235, 225, 215)
        bg[int(h * 0.82):int(h * 0.95), int(w * 0.70):int(w * 0.80)] = (240, 240, 240)
    noise = rng.normal(0, 6, bg.shape)
    return np.clip(bg + noise, 0, 255).astype(np.uint8)


def draw_subtitle(frame: np.ndarray, lines: list[str], size: int = 34, y_bottom: float = 0.93,
                  color=(255, 255, 255), highlight: str | None = None) -> np.ndarray:
    h, w = frame.shape[:2]
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(img)
    f = _font(size)
    lh = int(size * 1.25)
    y = int(h * y_bottom) - lh * len(lines)
    for line in lines:
        tw = d.textlength(line, font=f)
        x = (w - tw) / 2
        d.text((x, y), line, font=f, fill=color, stroke_width=3, stroke_fill=(0, 0, 0))
        if highlight and highlight in line:  # vurgulu kelimeyi sarı yeniden çiz
            pre = line[: line.index(highlight)]
            hx = x + d.textlength(pre, font=f)
            d.text((hx, y), highlight, font=f, fill=(255, 200, 40), stroke_width=3, stroke_fill=(0, 0, 0))
        y += lh
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def draw_help_box(frame: np.ndarray, lines: list[str], size: int = 26) -> np.ndarray:
    h, w = frame.shape[:2]
    out = frame.copy()
    x0, y0 = int(w * 0.02), int(h * 0.03)
    bw, bh = int(w * 0.26), int(size * 1.4 * len(lines) + size)
    roi = out[y0:y0 + bh, x0:x0 + bw]
    out[y0:y0 + bh, x0:x0 + bw] = (roi * 0.25).astype(np.uint8)  # yarı saydam siyah kutu
    img = Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(img)
    f = _font(size)
    y = y0 + size // 2
    for line in lines:
        d.text((x0 + size // 2, y), line, font=f, fill=(245, 245, 245))
        y += int(size * 1.4)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def jpeg(frame: np.ndarray, q: int = 70) -> np.ndarray:
    """Remote Play / chiaki sıkıştırma bozulmasını taklit et."""
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, q])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)
