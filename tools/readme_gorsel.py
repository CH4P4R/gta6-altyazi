"""README görsellerini üretir (ekransız Qt ile gerçek uygulama ekranları + örnek oyun karesi).

    QT_QPA_PLATFORM=offscreen python tools/readme_gorsel.py

Çıktı: docs/img/*.png. Oyun karesi sentetiktir (gerçek oyun görüntüsü kullanılmaz).
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "docs" / "img"


def make_scene(w: int = 1920, h: int = 1080, seed: int = 7):
    """Gün batımında sahil şehri (tamamen çizim; oyun görüntüsü değil). BGR numpy döndürür."""
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter

    rng = np.random.default_rng(seed)
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    horizon = int(h * 0.62)
    top, mid, low = (34, 16, 74), (214, 72, 120), (255, 170, 92)
    for y in range(horizon):                       # gökyüzü: mor → pembe → turuncu
        t = y / horizon
        a, b, u = (top, mid, t / 0.6) if t < 0.6 else (mid, low, (t - 0.6) / 0.4)
        d.line([(0, y), (w, y)], fill=tuple(int(a[i] + (b[i] - a[i]) * u) for i in range(3)))
    sun = (int(w * 0.62), int(horizon - h * 0.05))
    for r, c in ((170, (255, 196, 120)), (130, (255, 214, 140)), (100, (255, 232, 170))):
        d.ellipse([sun[0] - r, sun[1] - r, sun[0] + r, sun[1] + r], fill=c)
    for y in range(horizon, h):                    # deniz
        t = (y - horizon) / (h - horizon)
        d.line([(0, y), (w, y)], fill=(int(70 - 40 * t), int(40 - 20 * t), int(90 - 40 * t)))
    for i in range(40):                            # güneşin denizdeki yansıması
        yy = horizon + 8 + i * 9
        ww = int(220 * (1 - i / 45)) + rng.integers(-20, 20)
        d.line([(sun[0] - ww, yy), (sun[0] + ww, yy)], fill=(255, 190, 120), width=3)
    x = 0                                          # binalar
    while x < w:
        bw = int(rng.integers(60, 150))
        bh = int(rng.integers(int(h * 0.12), int(h * 0.42)))
        if abs(x + bw / 2 - sun[0]) < 220:
            bh = int(bh * 0.55)
        d.rectangle([x, horizon - bh, x + bw, horizon], fill=(28, 14, 44))
        for wy in range(horizon - bh + 12, horizon - 10, 22):
            for wx in range(x + 10, x + bw - 12, 18):
                if rng.random() < 0.35:
                    d.rectangle([wx, wy, wx + 7, wy + 10], fill=(255, 205, 120))
        x += bw + int(rng.integers(4, 18))
    d.rectangle([0, int(h * 0.80), w, h], fill=(22, 14, 30))                 # yol
    for i in range(0, w, 160):
        d.rectangle([i, int(h * 0.885), i + 80, int(h * 0.893)], fill=(120, 100, 90))
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def demo_images(out: Path) -> None:
    """Önce/sonra: gerçek bölge tespiti ve OCR ile yazıların yeri bulunur, Türkçe gerçek çizim koduyla basılır."""
    import cv2
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter

    from altyazi.config import BolgeCfg, Config
    from altyazi.ocr import Recognizer
    from altyazi.overlay import Painter
    from altyazi.pipeline import Pipeline
    from altyazi.translate import REFINED, Result
    from tests.synth import draw_help_box, draw_subtitle

    tr = {"Hurry up, they are right behind us!": "Acele et, hemen arkamızdalar!",
          "Go to the car.": "Arabaya git.",
          "Press E to enter the vehicle.": "Araca binmek için E'ye bas."}
    frame = make_scene()
    frame = draw_subtitle(frame, ["Hurry up, they are right behind us!"], y_bottom=0.875)
    frame = draw_subtitle(frame, ["Go to the car."], y_bottom=0.95, highlight="car")
    frame = draw_help_box(frame, ["Press E to enter the vehicle."])
    cv2.imwrite(str(out / "demo-once.png"), frame)

    class Eng:
        def submit(self, text, kind, cb, refine=True):  # noqa: ANN001
            cb(Result(tr.get(text, text), "claude", 300, REFINED))

    class Sink:
        def __init__(self):
            self.items = {}

        def show(self, it):  # noqa: ANN001
            self.items[it.zone] = it

        def clear(self, z):  # noqa: ANN001
            self.items.pop(z, None)

    cfg = Config(bolgeler=[BolgeCfg(ad="altyazi", alan=[0.10, 0.74, 0.90, 0.97]),
                           BolgeCfg(ad="yardim", alan=[0.0, 0.0, 0.36, 0.32], tur="arayuz", hizalama="sol",
                                    capa="ust")])
    sink = Sink()
    pipe = Pipeline(cfg, sink, Recognizer(), Eng())
    for i in range(4):
        pipe.process(frame, i * 0.04)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format_RGB888).copy()
    painter = Painter("Inter", False)
    painter.items = dict(sink.items)
    p = QPainter(img)
    painter.paint(p, QRectF(0, 0, img.width(), img.height()))
    p.end()
    img.save(str(out / "demo-sonra.png"))
    print("demo:", sorted(sink.items))


FONT_DIR = "/usr/share/fonts/opentype/inter/"


def _font(name: str, size: int):
    from PIL import ImageFont
    for p in (FONT_DIR + name, "C:/Windows/Fonts/segoeuib.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _rounded(img, radius: int):
    from PIL import Image, ImageDraw
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.size[0] - 1, img.size[1] - 1), radius, fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def comparison(out: Path) -> None:
    """Önce / sonra yan yana, etiketli."""
    from PIL import Image, ImageDraw
    W, pad, lab = 1600, 24, 64
    tw = (W - 3 * pad) // 2
    th = round(tw * 9 / 16)
    img = Image.new("RGB", (W, th + lab + 2 * pad), (20, 15, 29))
    d = ImageDraw.Draw(img)
    f = _font("Inter-ExtraBold.otf", 30)
    for i, (name, text, col) in enumerate((("demo-once.png", "ÖNCE  ·  oyunun kendisi", (220, 215, 235)),
                                           ("demo-sonra.png", "SONRA  ·  GTA6 Altyazı açık", (255, 120, 150)))):
        x = pad + i * (tw + pad)
        shot = Image.open(out / name).convert("RGB").resize((tw, th), Image.LANCZOS)
        img.paste(_rounded(shot, 14), (x, pad + lab), _rounded(shot, 14))
        d.text((x + 4, pad + 12), text, font=f, fill=col)
    img.save(out / "demo-karsilastirma.png", optimize=True)


def banner(out: Path) -> None:
    """README'nin üstündeki tanıtım görseli: marka banner'ı (tools/marka_gorsel.py ile aynı çizim)."""
    import sys as _s
    _s.path.insert(0, str(ROOT / "tools"))
    import marka_gorsel
    marka_gorsel.save(marka_gorsel.banner(1280, 720), out / "banner.png")


def main() -> int:
    os.environ["ALTYAZI_DATA"] = tempfile.mkdtemp(prefix="gorsel-")
    from PySide6.QtWidgets import QApplication

    from altyazi import config as config_mod
    from altyazi.app import AppController
    from altyazi.pipeline import DisplayItem
    from altyazi.ui import theme as T
    from altyazi.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(T.QSS)
    cfg = config_mod.load()
    cfg.sunucu.port = 18799
    cfg.ceviri.claude_anahtar = "sk-ant-ornek"
    AppController.warmup = lambda self: None
    AppController.stop = lambda self, *a, **k: None          # görüntü kaynağı yok: "çalışıyor" durumu bozulmasın
    AppController._auto_source = lambda self, *a, **k: None
    ctl = AppController(cfg)
    win = MainWindow(ctl)
    win.resize(1360, 860)
    win.show()
    OUT.mkdir(parents=True, exist_ok=True)

    def pump(sec: float = 0.3) -> None:
        end = time.time() + sec
        while time.time() < end:
            app.processEvents()
            time.sleep(0.02)

    lines = [
        ("Get in the car, we got company!", "Arabaya bin, misafirlerimiz var!", "claude", 2, 310),
        ("Lose the cops first.", "Önce polisleri ekmemiz lazım.", "claude", 2, 280),
        ("Go to the car.", "Arabaya git.", "paket/gta-v", 2, 41),
        ("Press to enter the vehicle.", "Araca binmek için bas.", "önbellek", 2, 36),
        ("Lucia: Where the hell were you?", "Lucia: Nerede kaldın be?", "claude", 2, 344),
        ("I told you we should've left earlier.", "Sana daha erken çıkalım demiştim.", "claude", 2, 298),
    ]
    for i, (en, tr, src, q, ms) in enumerate(lines, 1):
        it = DisplayItem("altyazi", (0.3, 0.85, 0.7, 0.93), (0.1, 0.76, 0.9, 0.97), 0.03, en, tr, "orta", "alt",
                         255, 1.3, source=src, quality=q, latency_ms=ms, seq=i)
        ctl.show(it)
        pump(0.05)
    ctl.enginesReady.emit({"ocr": "DirectML (GPU)", "hizli": "yerel (GPU)", "kalite": "Claude Opus 5.5 · hızlı mod",
                           "onbellek": 1842, "paket": 212229})
    ctl.sourceStatus.emit(True, "chiaki-ng · PS5")
    ctl.tvStatus.emit("bagli", "TCL Google TV bağlı · 192.168.1.40")
    try:
        ctl._set_state("calisiyor")
    except Exception:  # noqa: BLE001
        pass
    pages = {"home": "uygulama-ana.png", "regions": "uygulama-alanlar.png", "tv": "uygulama-tv.png",
             "translate": "uygulama-ceviri.png", "history": "uygulama-gecmis.png"}
    from tests.synth import draw_help_box, draw_subtitle
    frame = make_scene()
    frame = draw_subtitle(frame, ["Hurry up, they are right behind us!"], y_bottom=0.875)
    frame = draw_subtitle(frame, ["Go to the car."], y_bottom=0.95, highlight="car")
    frame = draw_help_box(frame, ["Press E to enter the vehicle."])
    ctl.frameGrabbed.emit(frame)
    for key, name in pages.items():
        if key not in win.pages:
            continue
        win.go(key)
        pump(0.4)
        try:
            ctl._set_state("calisiyor")
        except Exception:  # noqa: BLE001
            pass
        pump(0.9 if key == "home" else 0.1)      # ana ekranda arka ışığın yanması
        if getattr(win, "toast", None) is not None:
            win.toast.hide()
        pump(0.05)
        win.grab().save(str(OUT / name))
        print("kaydedildi:", name)
    # Rehber sayfası ve sihirbaz
    win.go("guide")
    pump(0.3)
    gp = win.pages["guide"]
    gp.open_key("monitor")
    gp.guide.show_step(1)
    pump(0.3)
    if getattr(win, "toast", None) is not None:
        win.toast.hide()
    win.grab().save(str(OUT / "uygulama-rehber.png"))
    from altyazi.ui.wizard import P_PS5, P_WHERE, Wizard
    wiz = Wizard(ctl)
    wiz.resize(1120, 780)
    wiz.show()
    wiz._go(P_WHERE)
    pump(0.3)
    wiz.grab().save(str(OUT / "sihirbaz-secim.png"))
    wiz._set_where("monitor")
    wiz._go(P_PS5)
    for _ in range(4):
        wiz.next.click()
    pump(0.3)
    wiz.grab().save(str(OUT / "sihirbaz-chiaki.png"))
    wiz.close()
    print("kaydedildi: rehber ve sihirbaz")
    demo_images(OUT)
    comparison(OUT)
    banner(OUT)
    ctl.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
