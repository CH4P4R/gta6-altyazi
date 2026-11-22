"""GTA6 Altyazı marka görselleri: simge, büyük simge, logo, rozet, yardımcı (bot), banner'lar, ana ekran sahnesi.

    python tools/marka_gorsel.py            # hepsini üretir ve yerlerine koyar
    python tools/marka_gorsel.py --onizleme # yalnız scratch klasörüne önizleme

Çizim Qt (QPainter) ile yapılır; parlama ve yumuşak gölgeler Pillow'un Gauss bulanıklığıyla. Yazı tipi Inter (OFL),
tools/marka/fonts içinde. Çıktılar depoya eklenir; uygulama derlenirken bu araç çalışmaz.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image, ImageFilter  # noqa: E402
from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (QBrush, QColor, QFont, QFontDatabase, QGuiApplication, QImage, QLinearGradient,  # noqa: E402
                           QPainter, QPainterPath, QPen, QRadialGradient, QTransform)

ROOT = Path(__file__).resolve().parents[1]
FONTS = Path(__file__).parent / "marka" / "fonts"
UI_OUT = ROOT / "altyazi" / "ui" / "marka"

_app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
_FAM: dict[str, str] = {}


def _font(name: str, px: float, letter: float = 0.0) -> QFont:
    if name not in _FAM:
        fid = QFontDatabase.addApplicationFont(str(FONTS / name))
        fams = QFontDatabase.applicationFontFamilies(fid)
        _FAM[name] = fams[0] if fams else "Sans"
    f = QFont(_FAM[name])
    f.setPixelSize(max(1, int(px)))
    style = QFontDatabase.styleString(f)
    if "Black" in name:
        f.setWeight(QFont.Black)
    elif "ExtraBold" in name:
        f.setWeight(QFont.ExtraBold)
    elif "Bold" in name:
        f.setWeight(QFont.Bold)
    elif "SemiBold" in name:
        f.setWeight(QFont.DemiBold)
    f.setItalic("Italic" in name)
    del style
    if letter:
        f.setLetterSpacing(QFont.AbsoluteSpacing, letter)
    f.setHintingPreference(QFont.PreferNoHinting)
    return f


BLACK_IT = "InterDisplay-BlackItalic.otf"
BOLD = "InterDisplay-Bold.otf"
SEMI = "Inter-SemiBold.otf"

# Renkler
NAVY0 = QColor("#1f0c33")
NAVY1 = QColor("#0c0614")
BLUE = QColor("#ff4fa3")
CYAN = QColor("#ff9f43")
RED0 = QColor("#ff2b3a")
RED1 = QColor("#b3081a")


# ----------------------------------------------------------------------------- yardımcılar
def new(w: int, h: int) -> QImage:
    img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    return img


def painter(img: QImage) -> QPainter:
    p = QPainter(img)
    p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
    return p


def to_pil(img: QImage) -> Image.Image:
    img = img.convertToFormat(QImage.Format_RGBA8888)
    return Image.frombuffer("RGBA", (img.width(), img.height()), bytes(img.constBits()), "raw", "RGBA", 0, 1).copy()


def to_qt(im: Image.Image) -> QImage:
    im = im.convert("RGBA")
    data = im.tobytes("raw", "RGBA")
    q = QImage(data, im.width, im.height, im.width * 4, QImage.Format_RGBA8888)
    return q.convertToFormat(QImage.Format_ARGB32_Premultiplied).copy()


def blur(img: QImage, r: float) -> QImage:
    return to_qt(to_pil(img).filter(ImageFilter.GaussianBlur(r)))


def glow(p: QPainter, size: tuple[int, int], draw, radius: float, strength: int = 1,  # noqa: ANN001
         mode=QPainter.CompositionMode_Screen) -> None:  # noqa: ANN001
    """draw(painter) ile çizilen şeklin bulanık parlamasını p'ye ekler."""
    lay = new(*size)
    lp = painter(lay)
    draw(lp)
    lp.end()
    g = blur(lay, radius)
    old = p.compositionMode()
    p.setCompositionMode(mode)
    for _ in range(strength):
        p.drawImage(0, 0, g)
    p.setCompositionMode(old)


def rrect(r: QRectF, rad: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(r, rad, rad)
    return path


def col(c) -> QColor:  # noqa: ANN001
    """'#RRGGBB' ya da CSS gibi '#RRGGBBAA' (Qt kendisi #AARRGGBB okur)."""
    if isinstance(c, str) and len(c) == 9:
        q = QColor(c[:7])
        q.setAlpha(int(c[7:], 16))
        return q
    return QColor(c)


def lin(x0, y0, x1, y1, *stops) -> QLinearGradient:  # noqa: ANN001, ANN002
    g = QLinearGradient(x0, y0, x1, y1)
    for t, c in stops:
        g.setColorAt(t, col(c))
    return g


def text_path(text: str, f: QFont, cx: float, baseline: float) -> QPainterPath:
    path = QPainterPath()
    path.addText(0, 0, f, text)
    b = path.boundingRect()
    return path.translated(cx - b.center().x(), baseline)


# ----------------------------------------------------------------------------- Türk bayrağı (ay yıldız)
def star_path(cx: float, cy: float, r: float, rot: float = -90.0) -> QPainterPath:
    path = QPainterPath()
    for i in range(10):
        rr = r if i % 2 == 0 else r * 0.382
        a = math.radians(rot + i * 36)
        pt = QPointF(cx + rr * math.cos(a), cy + rr * math.sin(a))
        path.moveTo(pt) if i == 0 else path.lineTo(pt)
    path.closeSubpath()
    return path


def crescent_star(p: QPainter, cx: float, cy: float, g: float, color=QColor("white")) -> None:  # noqa: ANN001
    """Bayrak ölçüleri (G = bayrak yüksekliği): dış daire 0.5G, iç daire 0.4G ve 0.0625G sağda, yıldız 0.25G çapında,
    ayın iç dairesinin 1/3G sağında. cx, cy: dış dairenin merkezi."""
    outer = QPainterPath()
    outer.addEllipse(QPointF(cx, cy), g * 0.25, g * 0.25)
    inner = QPainterPath()
    inner.addEllipse(QPointF(cx + g * 0.0625, cy), g * 0.2, g * 0.2)
    moon = outer.subtracted(inner)
    # yıldızın çevrel çemberi iç dairenin merkezinden 1/3 G uzakta başlar (bayrak kanunu ölçüleri)
    star = star_path(cx + g * (0.0625 + 1 / 3 + 0.125), cy, g * 0.125, rot=180)
    p.fillPath(moon.united(star), color)


# ----------------------------------------------------------------------------- kol
def pad_outline(x: float, y: float, w: float) -> QPainterPath:
    """Oyun kolunun dış çizgisi; (x, y) sol üst, genişlik w (yükseklik ~0.66w)."""
    def P(u, v):  # noqa: ANN001, ANN202, N802
        return QPointF(x + u * w, y + v * w)

    def M(u, v):  # noqa: ANN001, ANN202, N802
        return QPointF(x + (1 - u) * w, y + v * w)

    path = QPainterPath(P(0.5, 0.075))
    # sağ yarı
    path.cubicTo(P(0.62, 0.075), P(0.70, 0.035), P(0.79, 0.035))
    path.cubicTo(P(0.88, 0.035), P(0.93, 0.07), P(0.955, 0.15))
    path.cubicTo(P(0.99, 0.27), P(1.02, 0.45), P(0.995, 0.57))
    path.cubicTo(P(0.975, 0.66), P(0.88, 0.68), P(0.84, 0.61))
    path.cubicTo(P(0.80, 0.54), P(0.77, 0.47), P(0.70, 0.45))
    path.cubicTo(P(0.63, 0.43), P(0.57, 0.43), P(0.5, 0.43))
    # sol yarı (ayna)
    path.cubicTo(M(0.57, 0.43), M(0.63, 0.43), M(0.70, 0.45))
    path.cubicTo(M(0.77, 0.47), M(0.80, 0.54), M(0.84, 0.61))
    path.cubicTo(M(0.88, 0.68), M(0.975, 0.66), M(0.995, 0.57))
    path.cubicTo(M(1.02, 0.45), M(0.99, 0.27), M(0.955, 0.15))
    path.cubicTo(M(0.93, 0.07), M(0.88, 0.035), M(0.79, 0.035))
    path.cubicTo(M(0.70, 0.035), M(0.62, 0.075), P(0.5, 0.075))
    path.closeSubpath()
    return path


def draw_pad(p: QPainter, x: float, y: float, w: float, size: tuple[int, int], detail: bool = True) -> None:
    body = pad_outline(x, y, w)
    # gölge
    glow(p, size, lambda q: q.fillPath(body.translated(0, w * 0.03), QColor(0, 0, 0, 200)), w * 0.03,
         mode=QPainter.CompositionMode_SourceOver)
    # gövde: beyaz-gümüş, üstten ışık
    p.fillPath(body, lin(0, y, 0, y + w * 0.66, (0, "#ffffff"), (0.45, "#e9edf3"), (1, "#aab3c2")))
    # yan gölgeler (hacim)
    p.save()
    p.setClipPath(body)
    side = QRadialGradient(QPointF(x + w * 0.5, y + w * 0.2), w * 0.62)
    side.setColorAt(0.55, QColor(0, 0, 0, 0))
    side.setColorAt(1.0, QColor(20, 30, 60, 120))
    p.fillRect(QRectF(x - 10, y - 10, w + 20, w), side)
    # üst kenar parlaması
    hl = QPainterPath()
    hl.addEllipse(QRectF(x + w * 0.12, y + w * 0.02, w * 0.76, w * 0.12))
    p.fillPath(hl, QColor(255, 255, 255, 120))
    # ortadaki siyah gövde
    core = QPainterPath(QPointF(x + w * 0.27, y + w * 0.22))
    core.cubicTo(QPointF(x + w * 0.40, y + w * 0.30), QPointF(x + w * 0.60, y + w * 0.30), QPointF(x + w * 0.73, y + w * 0.22))
    core.cubicTo(QPointF(x + w * 0.78, y + w * 0.36), QPointF(x + w * 0.74, y + w * 0.47), QPointF(x + w * 0.66, y + w * 0.50))
    core.lineTo(QPointF(x + w * 0.34, y + w * 0.50))
    core.cubicTo(QPointF(x + w * 0.26, y + w * 0.47), QPointF(x + w * 0.22, y + w * 0.36), QPointF(x + w * 0.27, y + w * 0.22))
    p.fillPath(core, lin(0, y + w * 0.22, 0, y + w * 0.5, (0, "#2a3140"), (1, "#0b0e15")))
    p.restore()
    p.setPen(QPen(QColor(120, 135, 160, 140), max(1.0, w * 0.004)))
    p.drawPath(body)
    p.setPen(Qt.NoPen)

    # dokunmatik yüzey: kırmızı, üstünde ay yıldız
    tp = QPainterPath(QPointF(x + w * 0.335, y + w * 0.085))
    tp.lineTo(QPointF(x + w * 0.665, y + w * 0.085))
    tp.cubicTo(QPointF(x + w * 0.665, y + w * 0.17), QPointF(x + w * 0.655, y + w * 0.25), QPointF(x + w * 0.63, y + w * 0.275))
    tp.lineTo(QPointF(x + w * 0.37, y + w * 0.275))
    tp.cubicTo(QPointF(x + w * 0.345, y + w * 0.25), QPointF(x + w * 0.335, y + w * 0.17), QPointF(x + w * 0.335, y + w * 0.085))
    tp.closeSubpath()
    glow(p, size, lambda q: q.fillPath(tp, QColor(255, 30, 50, 200)), w * 0.025)
    p.fillPath(tp, lin(0, y + w * 0.085, 0, y + w * 0.275, (0, "#ff3b47"), (0.6, "#e0101f"), (1, "#a10616")))
    p.save()
    p.setClipPath(tp)
    gl = QPainterPath()
    gl.addEllipse(QRectF(x + w * 0.30, y + w * 0.02, w * 0.40, w * 0.12))
    p.fillPath(gl, QColor(255, 255, 255, 60))
    p.restore()
    p.setPen(QPen(QColor(90, 0, 10, 160), max(1.0, w * 0.004)))
    p.drawPath(tp)
    p.setPen(Qt.NoPen)
    g = w * 0.19
    crescent_star(p, x + w * 0.5 - g * 0.198, y + w * 0.18, g)   # ay yıldızın ortası yüzeyin ortasında

    # analog çubuklar
    for u in (0.385, 0.615):
        c = QPointF(x + w * u, y + w * 0.395)
        r = w * 0.068
        ring = QRadialGradient(c, r * 1.25)
        ring.setColorAt(0.75, QColor("#1a1f2b"))
        ring.setColorAt(1.0, QColor("#05070b"))
        p.setBrush(ring)
        p.drawEllipse(c, r * 1.18, r * 1.18)
        cap = QRadialGradient(QPointF(c.x() - r * 0.3, c.y() - r * 0.35), r * 1.2)
        cap.setColorAt(0, QColor("#4b5466"))
        cap.setColorAt(0.6, QColor("#1c212c"))
        cap.setColorAt(1, QColor("#0a0c12"))
        p.setBrush(cap)
        p.drawEllipse(c, r, r)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 40), max(1.0, w * 0.004)))
        p.drawEllipse(c, r * 0.72, r * 0.72)
        p.setPen(Qt.NoPen)

    if not detail:
        return
    # yön tuşları (sol)
    cx, cy, s = x + w * 0.2, y + w * 0.235, w * 0.042
    pen = QPen(QColor("#7d8799"), max(1.0, w * 0.006))
    pen.setJoinStyle(Qt.RoundJoin)
    for ang in (0, 90, 180, 270):
        t = QTransform().translate(cx, cy).rotate(ang)
        arm = QPainterPath()
        arm.addRoundedRect(QRectF(s * 0.35, -s * 0.5, s * 1.25, s), s * 0.3, s * 0.3)
        arm = t.map(arm)
        p.fillPath(arm, lin(0, cy - s, 0, cy + s, (0, "#ffffff"), (1, "#d5dbe5")))
        p.setPen(pen)
        p.drawPath(arm)
        p.setPen(Qt.NoPen)
    # şekil tuşları (sağ): üçgen, daire, çarpı, kare
    cx, cy, d = x + w * 0.8, y + w * 0.235, w * 0.062
    pen = QPen(QColor("#6f7a8e"), max(1.0, w * 0.0055))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    for dx, dy, kind in ((0, -1, "tri"), (1, 0, "o"), (0, 1, "x"), (-1, 0, "sq")):
        c = QPointF(cx + dx * d, cy + dy * d)
        r = w * 0.03
        p.setBrush(lin(0, c.y() - r, 0, c.y() + r, (0, "#ffffff"), (1, "#d3d9e3")))
        p.setPen(QPen(QColor("#9aa4b5"), max(1.0, w * 0.003)))
        p.drawEllipse(c, r, r)
        p.setBrush(Qt.NoBrush)
        p.setPen(pen)
        k = r * 0.5
        if kind == "tri":
            tri = QPainterPath(QPointF(c.x(), c.y() - k))
            tri.lineTo(QPointF(c.x() + k * 0.95, c.y() + k * 0.65))
            tri.lineTo(QPointF(c.x() - k * 0.95, c.y() + k * 0.65))
            tri.closeSubpath()
            p.drawPath(tri)
        elif kind == "o":
            p.drawEllipse(c, k * 0.85, k * 0.85)
        elif kind == "x":
            p.drawLine(QPointF(c.x() - k * 0.75, c.y() - k * 0.75), QPointF(c.x() + k * 0.75, c.y() + k * 0.75))
            p.drawLine(QPointF(c.x() + k * 0.75, c.y() - k * 0.75), QPointF(c.x() - k * 0.75, c.y() + k * 0.75))
        else:
            p.drawRect(QRectF(c.x() - k * 0.75, c.y() - k * 0.75, k * 1.5, k * 1.5))
        p.setPen(Qt.NoPen)


# ----------------------------------------------------------------------------- yörünge halkası
def orbit_path(cx: float, cy: float, rx: float, ry: float, rot: float, a0: float, a1: float) -> QPainterPath:
    path = QPainterPath()
    t = QTransform().translate(cx, cy).rotate(rot)
    n = 80
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pt = t.map(QPointF(rx * math.cos(a), ry * math.sin(a)))
        path.moveTo(pt) if i == 0 else path.lineTo(pt)
    return path


def draw_orbit(p: QPainter, size, cx, cy, rx, ry, rot, a0, a1, width) -> None:  # noqa: ANN001
    path = orbit_path(cx, cy, rx, ry, rot, a0, a1)

    def stroke(q: QPainter, wmul: float, color: QColor) -> None:
        pen = QPen(color, width * wmul)
        pen.setCapStyle(Qt.RoundCap)
        q.strokePath(path, pen)

    glow(p, size, lambda q: stroke(q, 3.0, QColor(255, 90, 165, 255)), width * 2.2, strength=2)
    stroke(p, 1.0, QColor(255, 165, 110))
    stroke(p, 0.4, QColor(255, 242, 228))


# ----------------------------------------------------------------------------- konuşma balonları
def bubble(p: QPainter, r: QRectF, fill, tail_left: bool, label: str, label_color: QColor, size) -> None:  # noqa: ANN001
    rad = r.height() * 0.28
    path = rrect(r, rad)
    tail = QPainterPath()
    if tail_left:
        tail.moveTo(r.left() + r.width() * 0.18, r.bottom() - 2)
        tail.lineTo(r.left() + r.width() * 0.14, r.bottom() + r.height() * 0.32)
        tail.lineTo(r.left() + r.width() * 0.42, r.bottom() - 2)
    else:
        tail.moveTo(r.right() - r.width() * 0.18, r.bottom() - 2)
        tail.lineTo(r.right() - r.width() * 0.14, r.bottom() + r.height() * 0.32)
        tail.lineTo(r.right() - r.width() * 0.42, r.bottom() - 2)
    tail.closeSubpath()
    path = path.united(tail)
    glow(p, size, lambda q: q.fillPath(path.translated(0, r.height() * 0.06), QColor(0, 0, 0, 170)), r.height() * 0.08,
         mode=QPainter.CompositionMode_SourceOver)
    p.fillPath(path, fill)
    p.save()
    p.setClipPath(path)
    hl = QPainterPath()
    hl.addEllipse(QRectF(r.left() - r.width() * 0.1, r.top() - r.height() * 0.55, r.width() * 1.2, r.height() * 0.9))
    p.fillPath(hl, QColor(255, 255, 255, 50))
    p.restore()
    f = _font(BLACK_IT, r.height() * 0.46)
    tp = text_path(label, f, r.center().x(), r.center().y() + r.height() * 0.165)
    p.fillPath(tp, label_color)


# ----------------------------------------------------------------------------- simge
def icon(size: int = 1024, text: bool = True, frame: bool = True) -> QImage:
    S = 1024.0
    img = new(1024, 1024)
    p = painter(img)
    full = (1024, 1024)
    m = 54.0 if frame else 0.0
    box = QRectF(m, m, S - 2 * m, S - 2 * m)
    rad = box.width() * 0.215
    tile = rrect(box, rad)
    if frame:
        # dış mavi parlama
        glow(p, full, lambda q: q.strokePath(tile, QPen(QColor(255, 70, 160), 26)), 22, strength=2,
             mode=QPainter.CompositionMode_SourceOver)
    bg = QRadialGradient(QPointF(S * 0.5, S * 0.40), S * 0.62)
    bg.setColorAt(0.0, QColor("#3d1554"))
    bg.setColorAt(0.55, QColor("#1f0c33"))
    bg.setColorAt(1.0, QColor("#0c0614"))
    p.fillPath(tile, bg)
    p.save()
    p.setClipPath(tile)
    # alt koyu, üst hafif ışık
    p.fillRect(QRectF(0, S * 0.62, S, S * 0.4), lin(0, S * 0.62, 0, S, (0, "#00000000"), (1, "#000000aa")))
    sheen = QPainterPath()
    sheen.addEllipse(QRectF(box.left() - S * 0.2, box.top() - S * 0.55, S * 1.4, S * 0.85))
    p.fillPath(sheen, QColor(255, 255, 255, 14))
    p.restore()
    if frame:
        rim = lin(0, box.top(), 0, box.bottom(), (0, "#ffc27a"), (0.35, "#ff5fa8"), (1, "#a8207a"))
        p.setPen(QPen(QBrush(rim), 16))
        p.drawPath(tile)
        p.setPen(QPen(QColor(255, 255, 255, 70), 3))
        p.drawPath(rrect(box.adjusted(11, 11, -11, -11), rad - 11))
        p.setPen(Qt.NoPen)

    if text:
        pw, px, py = 700.0, (S - 700.0) / 2, 150.0
        ocx, ocy, orx, ory = S / 2, py + pw * 0.33, pw * 0.60, pw * 0.17
    else:
        pw, px, py = 820.0, (S - 820.0) / 2, 250.0
        ocx, ocy, orx, ory = S / 2, py + pw * 0.34, pw * 0.60, pw * 0.17
    rot = -9.0
    # halkanın arka yarısı (kolun arkasında)
    p.save()
    p.setClipPath(tile)
    draw_orbit(p, full, ocx, ocy, orx, ory, rot, 180, 360, pw * 0.012)
    p.restore()
    draw_pad(p, px, py, pw, full, detail=True)
    # ön yarı
    p.save()
    p.setClipPath(tile)
    draw_orbit(p, full, ocx, ocy, orx, ory, rot, 8, 172, pw * 0.012)
    p.restore()
    # balonlar: EN -> TR
    bh = pw * 0.15
    by = py + pw * 0.43
    bubble(p, QRectF(S / 2 - bh * 1.62, by, bh * 1.55, bh), lin(0, by, 0, by + bh, (0, "#ffffff"), (1, "#dfe6f0")),
           True, "EN", QColor("#14213d"), full)
    bubble(p, QRectF(S / 2 + bh * 0.07, by + bh * 0.12, bh * 1.55, bh),
           lin(0, by, 0, by + bh, (0, "#ff5fa8"), (1, "#ff9a3d")), False, "TR", QColor("white"), full)

    if text:
        f = _font(BLACK_IT, 168, letter=2)
        tp = text_path("ALTYAZI", f, S / 2, 832)
        glow(p, full, lambda q: q.fillPath(tp, QColor(255, 80, 165)), 14, strength=1)
        p.setPen(QPen(QColor("#2a0c33"), 14, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(tp)
        p.setPen(Qt.NoPen)
        b = tp.boundingRect()
        p.fillPath(tp, lin(0, b.top(), 0, b.bottom(), (0, "#ffffff"), (0.5, "#e6ecf5"), (0.52, "#b9c4d6"), (1, "#f4f7fb")))
        p.setPen(QPen(QColor(255, 255, 255, 120), 2))
        p.drawPath(tp)
        p.setPen(Qt.NoPen)
        # alt satır
        f2 = _font(BOLD, 40, letter=7)
        cap = text_path("GTA 6  ·  TÜRKÇE", f2, S / 2, 905)
        p.fillPath(cap, QColor("#e8eef8"))
        cb = cap.boundingRect()
        for x0, x1 in ((cb.left() - 110, cb.left() - 26), (cb.right() + 26, cb.right() + 110)):
            p.fillRect(QRectF(x0, 890, x1 - x0, 6), lin(x0, 0, x1, 0, (0, "#ff4fa300"), (0.5, "#ff9f43"), (1, "#ff4fa300"))
                       if x0 < cb.left() else lin(x0, 0, x1, 0, (0, "#ff4fa300"), (0.5, "#ff9f43"), (1, "#ff4fa300")))
    p.end()
    if size != 1024:
        return img.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return img


def rozet(size: int = 512) -> QImage:
    """Yuvarlak kırmızı rozet: ay yıldız, cam parlaklığı. Kaydırmalı düğmenin topu, sekme simgesi, telefon sayfası."""
    S = 512.0
    img = new(512, 512)
    p = painter(img)
    full = (512, 512)
    c = QPointF(S / 2, S / 2)
    r = S * 0.44
    glow(p, full, lambda q: (q.setBrush(QColor(0, 0, 0, 150)), q.setPen(Qt.NoPen),
                             q.drawEllipse(QPointF(c.x(), c.y() + 10), r, r)), 14, mode=QPainter.CompositionMode_SourceOver)
    # dış cam halka
    ring = QRadialGradient(QPointF(c.x(), c.y() - r * 0.4), r * 1.4)
    ring.setColorAt(0, QColor(255, 255, 255, 235))
    ring.setColorAt(1, QColor(200, 210, 225, 220))
    p.setPen(Qt.NoPen)
    p.setBrush(ring)
    p.drawEllipse(c, r, r)
    inner = r * 0.84
    red = QRadialGradient(QPointF(c.x() - inner * 0.25, c.y() - inner * 0.35), inner * 1.35)
    red.setColorAt(0, QColor("#ff5562"))
    red.setColorAt(0.55, QColor("#e3101f"))
    red.setColorAt(1, QColor("#9c0414"))
    p.setBrush(red)
    p.drawEllipse(c, inner, inner)
    g = inner * 1.25
    crescent_star(p, c.x() - g * 0.198, c.y(), g)
    # üst cam parlaklığı
    hl = QPainterPath()
    hl.addEllipse(QRectF(c.x() - inner * 0.78, c.y() - inner * 0.98, inner * 1.56, inner * 0.95))
    p.fillPath(hl, lin(0, c.y() - inner, 0, c.y(), (0, "#ffffff70"), (1, "#ffffff00")))
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(120, 0, 10, 120), 3))
    p.drawEllipse(c, inner, inner)
    p.end()
    return img.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation) if size != 512 else img


def bot(size: int = 512) -> QImage:
    """Yardımcının (Sor) yüzü: lacivert dairede parlak beyaz robot başı, mavi gözler, kulaklık, ay yıldızlı rozet."""
    S = 512.0
    img = new(512, 512)
    p = painter(img)
    full = (512, 512)
    c = QPointF(S / 2, S / 2)
    R = S * 0.47
    circle = QPainterPath()
    circle.addEllipse(c, R, R)
    bg = QRadialGradient(QPointF(c.x(), c.y() - R * 0.3), R * 1.2)
    bg.setColorAt(0, QColor("#4d1a66"))
    bg.setColorAt(0.6, QColor("#1f0c33"))
    bg.setColorAt(1, QColor("#0c0614"))
    p.fillPath(circle, bg)
    p.setPen(QPen(lin(0, c.y() - R, 0, c.y() + R, (0, "#ffc27a"), (1, "#a8207a")), 10))
    p.drawPath(circle)
    p.setPen(Qt.NoPen)
    p.save()
    p.setClipPath(circle)
    # anten
    p.setPen(QPen(QColor("#c9d2e0"), 10, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(c.x(), 150), QPointF(c.x(), 100))
    p.setPen(Qt.NoPen)
    glow(p, full, lambda q: (q.setBrush(QColor(255, 40, 60)), q.setPen(Qt.NoPen), q.drawEllipse(QPointF(c.x(), 92), 22, 22)), 12)
    ball = QRadialGradient(QPointF(c.x() - 6, 86), 24)
    ball.setColorAt(0, QColor("#ff8a92"))
    ball.setColorAt(1, QColor("#c00616"))
    p.setBrush(ball)
    p.drawEllipse(QPointF(c.x(), 92), 19, 19)
    # kulaklık
    for sx in (-1, 1):
        ear = QRectF(c.x() + sx * 150 - 26, 232, 52, 104)
        p.fillPath(rrect(ear, 22), lin(0, ear.top(), 0, ear.bottom(), (0, "#ff6aa8"), (1, "#d63a7c")))
    # baş
    head = QRectF(c.x() - 138, 140, 276, 228)
    hp = rrect(head, 78)
    glow(p, full, lambda q: q.fillPath(hp.translated(0, 12), QColor(0, 0, 0, 170)), 14, mode=QPainter.CompositionMode_SourceOver)
    p.fillPath(hp, lin(0, head.top(), 0, head.bottom(), (0, "#ffffff"), (0.55, "#e8edf4"), (1, "#a9b3c3")))
    shine = QPainterPath()
    shine.addEllipse(QRectF(head.left() + 30, head.top() + 8, head.width() - 60, 50))
    p.fillPath(shine, QColor(255, 255, 255, 140))
    # yüz camı
    visor = QRectF(c.x() - 104, 190, 208, 118)
    vp = rrect(visor, 54)
    p.fillPath(vp, lin(0, visor.top(), 0, visor.bottom(), (0, "#1b2740"), (1, "#060a14")))
    # gözler
    for sx in (-1, 1):
        eye = QRectF(c.x() + sx * 46 - 17, 222, 34, 46)
        ep = rrect(eye, 17)
        glow(p, full, lambda q, ep=ep: q.fillPath(ep, QColor(255, 150, 70)), 12, strength=2)
        p.fillPath(ep, lin(0, eye.top(), 0, eye.bottom(), (0, "#fff0dc"), (1, "#ff9f43")))
    # gülümseme
    smile = QPainterPath(QPointF(c.x() - 30, 284))
    smile.quadTo(QPointF(c.x(), 304), QPointF(c.x() + 30, 284))
    p.setPen(QPen(QColor("#ff9f43"), 7, Qt.SolidLine, Qt.RoundCap))
    p.drawPath(smile)
    p.setPen(Qt.NoPen)
    # boyun ve gövde
    body = QRectF(c.x() - 120, 384, 240, 140)
    p.fillPath(rrect(body, 60), lin(0, body.top(), 0, body.bottom(), (0, "#f4f7fb"), (1, "#9aa5b8")))
    p.fillRect(QRectF(c.x() - 40, 362, 80, 26), QColor("#8b96aa"))
    # göğüste ay yıldız rozeti
    p.setBrush(lin(0, 410, 0, 470, (0, "#ff4552"), (1, "#b00718")))
    p.drawEllipse(QPointF(c.x(), 440), 30, 30)
    crescent_star(p, c.x() - 48 * 0.198, 440, 48)
    p.restore()
    p.end()
    return img.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation) if size != 512 else img


def logo(dark_text: bool = False) -> QImage:
    """Yatay logo: simge + 'GTA6 Altyazı' + 'TÜRKÇE ALTYAZI'. Saydam zemin."""
    W, H = 1240, 300
    img = new(W, H)
    p = painter(img)
    ic = icon(300, text=False)
    p.drawImage(QRectF(0, 0, 300, 300), ic)
    col = QColor("#0f1b33") if dark_text else QColor("white")
    f = _font(BLACK_IT if False else "InterDisplay-Black.otf", 128)
    path = QPainterPath()
    path.addText(330, 170, f, "GTA6 Altyazı")
    p.fillPath(path, col)
    f2 = _font(BOLD, 40, letter=14)
    cap = QPainterPath()
    cap.addText(336, 238, f2, "TÜRKÇE ALTYAZI")
    p.fillPath(cap, QColor("#e0457f") if dark_text else QColor("#ff9f43"))
    p.end()
    return img


def banner(W: int, H: int, line2: str = "Oyunlar artık Türkçe") -> QImage:
    """Simge solda, ad ve alt satır sağda; lacivert zemin (Android TV banner'ı, büyük tanıtım görseli)."""
    img = new(W, H)
    p = painter(img)
    bg = lin(0, 0, W, H, (0, "#3d1554"), (0.55, "#1f0c33"), (1, "#0c0614"))
    p.fillRect(QRectF(0, 0, W, H), bg)
    light = QRadialGradient(QPointF(W * 0.28, H * 0.5), H * 0.9)
    light.setColorAt(0, QColor(255, 80, 160, 90))
    light.setColorAt(1, QColor(255, 80, 160, 0))
    p.fillRect(QRectF(0, 0, W, H), light)
    s = H * 0.76
    ic = icon(1024, text=True)
    p.drawImage(QRectF(H * 0.09, (H - s) / 2, s, s), ic)
    x = H * 0.09 + s + H * 0.09
    avail = W - x - H * 0.07

    def fitted(text: str, fname: str, px: float, baseline: float) -> QPainterPath:
        path = QPainterPath()
        path.addText(0, 0, _font(fname, px), text)
        b = path.boundingRect()
        sc = min(1.0, avail / b.width())
        return QTransform().translate(x - b.left() * sc, baseline).scale(sc, sc).map(path)

    big = H * 0.21
    t1 = fitted("GTA6", "InterDisplay-Black.otf", big, H * 0.40)
    t2 = fitted("Altyazı", "InterDisplay-Black.otf", big, H * 0.62)
    sc = min(1.0, avail / max(t1.boundingRect().width(), t2.boundingRect().width()))
    p.fillPath(t1, QColor("white"))
    p.fillPath(t2, QColor("white"))
    t3 = fitted(line2, SEMI, H * 0.072, H * 0.76)
    p.fillPath(t3, QColor("#ffb37a"))
    del sc
    p.end()
    return img


# ----------------------------------------------------------------------------- ana ekran sahnesi
_BASE = {"tv": [150, 30, 1250, 650], "screen": [158, 38, 1242, 642], "shelf": [40, 690, 1520, 852],
         "ps5": [1290, 392, 1446, 700], "socket": [1500, 336, 1584, 420], "plug_rest": [1486, 676],
         "cable_from": [1440, 668]}
_DX, _DY = 70, 60          # arka ışığın bulanık kenarı kesilmesin diye çevrede boşluk
SCENE = {"w": 1720, "h": 980, **{k: [v + (_DX if i % 2 == 0 else _DY) for i, v in enumerate(vals)]
                                 for k, vals in _BASE.items()}}


def waves(w: int, h: int) -> QImage:
    img = new(w, h)
    p = painter(img)
    p.fillRect(QRectF(0, 0, w, h), lin(0, 0, w, h, (0, "#1a0626"), (0.5, "#4a0f45"), (1, "#0a0410")))
    vign = QRadialGradient(QPointF(w * 0.35, h * 0.75), w * 0.8)
    vign.setColorAt(0, QColor(0, 0, 0, 0))
    vign.setColorAt(1, QColor(0, 0, 10, 150))
    p.fillRect(QRectF(0, 0, w, h), vign)

    def ribbon(k: float) -> QPainterPath:
        path = QPainterPath(QPointF(-20, h * (0.70 + 0.05 * k)))
        path.cubicTo(QPointF(w * 0.30, h * (0.98 - 0.02 * k)), QPointF(w * 0.55, h * (0.42 + 0.05 * k)),
                     QPointF(w + 20, h * (0.06 + 0.17 * k)))
        return path

    paths = [ribbon(k) for k in (0.0, 0.7, 1.4, 2.2, 3.0)]
    # ribbonların arasında hafif yüzey
    sheet = QPainterPath(paths[0])
    rev = paths[2].toReversed()
    sheet.connectPath(rev)
    sheet.closeSubpath()
    p.fillPath(sheet, QColor(255, 90, 160, 28))

    def strokes(q: QPainter, wmul: float, alpha: int) -> None:
        for i, path in enumerate(paths):
            pen = QPen(QColor(255, 110, 170, alpha), (3.2 - i * 0.45) * wmul)
            pen.setCapStyle(Qt.RoundCap)
            q.strokePath(path, pen)

    glow(p, (w, h), lambda q: strokes(q, 6, 255), 18, strength=2)
    glow(p, (w, h), lambda q: strokes(q, 2, 255), 5, strength=1)
    strokes(p, 1, 255)
    for i, path in enumerate(paths[:3]):
        p.strokePath(path, QPen(QColor(255, 236, 222, 230 - i * 50), 1.2))
    # parlak düğüm
    hot = QRadialGradient(QPointF(w * 0.24, h * 0.80), w * 0.18)
    hot.setColorAt(0, QColor(255, 190, 150, 70))
    hot.setColorAt(1, QColor(255, 110, 170, 0))
    p.setCompositionMode(QPainter.CompositionMode_Screen)
    p.fillRect(QRectF(0, 0, w, h), hot)
    p.end()
    return img


def brushed(w: int, h: int, seed: int = 3) -> Image.Image:
    """Fırçalanmış çelik: yatay çizgiler, dikey ışık bantları."""
    import numpy as np
    rng = np.random.default_rng(seed)
    y = np.linspace(0, 1, h)[:, None]
    base = 0.72 - 0.26 * np.sin(np.pi * y) ** 0.8 + 0.10 * y          # üst ve alt açık, orta koyu
    noise = rng.normal(0, 1, (h, w))
    import cv2  # noqa: PLC0415

    def gaussian_filter1d(a, sigma, axis=1):  # noqa: ANN001, ANN202, ARG001
        return cv2.GaussianBlur(a.astype(np.float32), (0, 1), sigmaX=float(sigma), sigmaY=0.01)

    streak = gaussian_filter1d(noise, sigma=w * 0.02, axis=1)
    streak = streak / (np.abs(streak).max() + 1e-6)
    fine = gaussian_filter1d(rng.normal(0, 1, (h, w)), sigma=6, axis=1)
    fine = fine / (np.abs(fine).max() + 1e-6)
    x = np.linspace(0, 1, w)[None, :]
    bands = np.zeros((1, w))
    for cx, wd, a in ((0.08, 0.05, 0.10), (0.22, 0.07, 0.22), (0.38, 0.05, 0.12), (0.55, 0.08, 0.20), (0.72, 0.06, 0.16),
                      (0.88, 0.07, 0.20)):
        bands = bands + a * np.exp(-((x - cx) / wd) ** 2)
    v = base + bands * (0.6 + 0.4 * np.sin(np.pi * y)) + 0.035 * streak + 0.02 * fine
    v = np.clip(v, 0, 1)
    r = (v * 222 + 12).astype(np.uint8)
    g = (v * 226 + 12).astype(np.uint8)
    b = (v * 232 + 14).astype(np.uint8)
    return Image.fromarray(np.dstack([r, g, b, np.full_like(r, 255)]), "RGBA")


def scene() -> tuple[QImage, QImage]:
    """Duvara asılı TV, metal sehpa, PS5 ve priz (saydam zemin) ile arka ışık katmanı."""
    W, H = SCENE["w"], SCENE["h"]
    full = (W, H)
    img = new(W, H)
    p = painter(img)
    sx0, sy0, sx1, sy1 = SCENE["shelf"]
    # sehpanın yere düşen gölgesi
    glow(p, full, lambda q: (q.setBrush(QColor(0, 0, 0, 200)), q.setPen(Qt.NoPen),
                             q.drawRoundedRect(QRectF(sx0 + 30, sy1 - 18, sx1 - sx0 - 60, 34), 17, 17)), 18,
         mode=QPainter.CompositionMode_SourceOver)
    # TV gölgesi
    tx0, ty0, tx1, ty1 = SCENE["tv"]
    glow(p, full, lambda q: q.fillRect(QRectF(tx0 + 10, ty0 + 18, tx1 - tx0 - 20, ty1 - ty0), QColor(0, 0, 0, 170)), 22,
         mode=QPainter.CompositionMode_SourceOver)
    # TV gövdesi
    tv = QRectF(tx0, ty0, tx1 - tx0, ty1 - ty0)
    p.fillPath(rrect(tv, 7), lin(0, ty0, 0, ty1, (0, "#2a2d33"), (0.04, "#111316"), (1, "#060708")))
    p.setPen(QPen(QColor(90, 96, 108), 1.5))
    p.drawPath(rrect(tv.adjusted(0.75, 0.75, -0.75, -0.75), 7))
    p.setPen(Qt.NoPen)
    p.fillPath(rrect(QRectF((tx0 + tx1) / 2 - 38, ty1 - 1, 76, 7), 3), QColor("#1d2025"))
    # ekran: dalgalı duvar kağıdı
    ex0, ey0, ex1, ey1 = SCENE["screen"]
    p.drawImage(QRectF(ex0, ey0, ex1 - ex0, ey1 - ey0), waves(ex1 - ex0, ey1 - ey0))
    # sehpa: üst yüzey + ön yüz (fırçalanmış çelik)
    top = QRectF(sx0, sy0, sx1 - sx0, 20)
    front = QRectF(sx0, sy0 + 16, sx1 - sx0, sy1 - sy0 - 16)
    p.fillPath(rrect(QRectF(sx0, sy0, sx1 - sx0, sy1 - sy0), 20),
               lin(0, sy0, 0, sy1, (0, "#c7ccd3"), (1, "#6d737c")))
    metal = to_qt(brushed(int(front.width()), int(front.height())))
    fpath = rrect(front, 18)
    p.save()
    p.setClipPath(fpath)
    p.drawImage(front, metal)
    # alt kenar gölgesi ve üst kenar ışığı
    p.fillRect(QRectF(front.left(), front.bottom() - 14, front.width(), 14),
               lin(0, front.bottom() - 14, 0, front.bottom(), (0, "#00000000"), (1, "#00000070")))
    p.fillRect(QRectF(front.left(), front.top(), front.width(), 3), QColor(255, 255, 255, 150))
    p.restore()
    p.fillPath(rrect(top, 10), lin(0, top.top(), 0, top.bottom(), (0, "#eef1f5"), (0.5, "#b8bec7"), (1, "#8d939c")))
    p.setPen(QPen(QColor(255, 255, 255, 200), 1.2))
    p.drawLine(QPointF(sx0 + 14, sy0 + 1), QPointF(sx1 - 14, sy0 + 1))
    # iki çekmece arası çizgi
    mx = (sx0 + sx1) / 2
    p.setPen(QPen(QColor(40, 44, 50, 200), 3))
    p.drawLine(QPointF(mx, front.top() + 8), QPointF(mx, front.bottom() - 6))
    p.setPen(QPen(QColor(255, 255, 255, 120), 1.2))
    p.drawLine(QPointF(mx + 2.5, front.top() + 8), QPointF(mx + 2.5, front.bottom() - 6))
    p.setPen(Qt.NoPen)

    # PS5
    px0, py0, px1, py1 = SCENE["ps5"]
    glow(p, full, lambda q: (q.setBrush(QColor(0, 0, 0, 190)), q.setPen(Qt.NoPen),
                             q.drawEllipse(QRectF(px0 + 10, py1 - 20, px1 - px0 - 6, 26))), 8,
         mode=QPainter.CompositionMode_SourceOver)
    core_l, core_r = px0 + 100, px0 + 124
    left = QPainterPath(QPointF(px0 + 16, py1 - 12))
    left.cubicTo(QPointF(px0 + 8, py1 - 120), QPointF(px0 + 2, py0 + 120), QPointF(px0 + 10, py0 + 34))
    left.cubicTo(QPointF(px0 + 14, py0 + 10), QPointF(px0 + 30, py0 + 4), QPointF(px0 + 52, py0 + 8))
    left.lineTo(QPointF(core_l + 4, py0 + 22))
    left.lineTo(QPointF(core_l + 4, py1 - 12))
    left.closeSubpath()
    p.fillPath(left, lin(px0, 0, core_l, 0, (0, "#c9d0db"), (0.35, "#ffffff"), (1, "#e3e8ef")))
    p.save()
    p.setClipPath(left)
    p.fillRect(QRectF(px0, py0, core_l - px0, 60), lin(0, py0, 0, py0 + 60, (0, "#ffffff"), (1, "#ffffff00")))
    p.fillRect(QRectF(px0, py1 - 70, core_l - px0, 70), lin(0, py1 - 70, 0, py1, (0, "#00000000"), (1, "#0000002a")))
    p.restore()
    core = QRectF(core_l, py0 + 18, core_r - core_l, py1 - py0 - 30)
    p.fillRect(core, lin(core_l, 0, core_r, 0, (0, "#2b2f36"), (0.5, "#0d0f13"), (1, "#1d2026")))
    p.fillRect(QRectF(core_l + 1, py0 + 40, 2.2, py1 - py0 - 70), QColor(235, 235, 255, 200))   # beyaz ışık
    right = QPainterPath(QPointF(core_r - 2, py0 + 20))
    right.lineTo(QPointF(px1 - 22, py0 + 2))
    right.cubicTo(QPointF(px1 - 8, py0 + 2), QPointF(px1 - 4, py0 + 20), QPointF(px1 - 6, py0 + 60))
    right.cubicTo(QPointF(px1 - 8, py0 + 160), QPointF(px1 - 6, py1 - 100), QPointF(px1 - 10, py1 - 12))
    right.lineTo(QPointF(core_r - 2, py1 - 12))
    right.closeSubpath()
    p.fillPath(right, lin(core_r, 0, px1, 0, (0, "#eef2f7"), (1, "#a3acb9")))
    p.setPen(QPen(QColor(120, 130, 145, 140), 1.2))
    p.drawPath(left)
    p.drawPath(right)
    p.setPen(Qt.NoPen)
    base = QRectF(px0 + 40, py1 - 20, px1 - px0 - 50, 22)
    p.fillPath(rrect(base, 8), lin(0, base.top(), 0, base.bottom(), (0, "#2a2e35"), (1, "#060709")))

    # priz
    kx0, ky0, kx1, ky1 = SCENE["socket"]
    plate = QRectF(kx0, ky0, kx1 - kx0, ky1 - ky0)
    glow(p, full, lambda q: q.fillPath(rrect(plate.translated(3, 6), 10), QColor(0, 0, 0, 150)), 8,
         mode=QPainter.CompositionMode_SourceOver)
    p.fillPath(rrect(plate, 10), lin(0, ky0, 0, ky1, (0, "#f1f3f5"), (1, "#b4bac2")))
    p.setPen(QPen(QColor(110, 116, 126), 1.5))
    p.drawPath(rrect(plate.adjusted(0.75, 0.75, -0.75, -0.75), 10))
    p.setPen(QPen(QColor(255, 255, 255, 200), 1.2))
    p.drawPath(rrect(plate.adjusted(6, 6, -6, -6), 7))
    p.setPen(Qt.NoPen)
    c = plate.center()
    rec = QRadialGradient(QPointF(c.x(), c.y() + 8), 34)
    rec.setColorAt(0, QColor("#d9dde2"))
    rec.setColorAt(1, QColor("#8d949e"))
    p.setBrush(rec)
    p.drawEllipse(c, 28, 28)
    p.setBrush(QColor("#7c838d"))
    for dy in (-27, 23):
        p.drawRect(QRectF(c.x() - 7, c.y() + dy, 14, 4))
    p.setBrush(QColor("#15171a"))
    for dx in (-10, 10):
        p.drawEllipse(QPointF(c.x() + dx, c.y()), 4.6, 4.6)
    p.end()

    # arka ışık (çalışırken)
    light = new(W, H)
    lp = painter(light)
    lp.end()

    def back(q: QPainter) -> None:
        q.setPen(Qt.NoPen)
        q.fillPath(rrect(QRectF(tx0 - 26, ty0 - 26, tx1 - tx0 + 52, ty1 - ty0 + 52), 30), QColor(255, 60, 150))
        q.fillPath(rrect(QRectF(sx0 + 30, sy1 - 30, sx1 - sx0 - 60, 50), 25), QColor(255, 60, 150))

    lp = painter(light)
    glow(lp, full, back, 40, strength=2, mode=QPainter.CompositionMode_SourceOver)
    glow(lp, full, back, 12, strength=1, mode=QPainter.CompositionMode_Screen)
    lp.end()
    return img, light


def save(img: QImage, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    to_pil(img).save(path, optimize=True)


def main(argv: list[str]) -> int:
    """Varsayılan: görselleri yerlerine yazar. --out KLASÖR: hepsini yalnız o klasöre (önizleme)."""
    import json
    preview = Path(argv[argv.index("--out") + 1]) if "--out" in argv else None
    ui = preview or UI_OUT
    save(icon(1024), ui / "simge.png")          # macOS simgesi 1024 ister (make_assets buradan küçültür)
    save(icon(512, text=False), ui / "simge_yazisiz.png")
    save(rozet(256), ui / "rozet.png")
    save(bot(256), ui / "bot.png")
    save(logo(), ui / "logo.png")
    save(logo(dark_text=True), ui / "logo_acik.png")
    sc, light = scene()
    save(sc, ui / "sahne.png")
    save(light, ui / "sahne_isik.png")
    (ui / "sahne.json").write_text(json.dumps(SCENE), encoding="utf-8")
    android = preview or ROOT / "tv-android" / "app" / "src" / "main" / "res"
    docs = preview or ROOT / "docs" / "img"
    if preview:
        save(icon(512), preview / "android_icon.png")
        save(banner(640, 360), preview / "android_banner.png")
        save(banner(1280, 720), preview / "banner.png")
    else:
        save(icon(512), android / "mipmap-nodpi" / "icon.png")          # Android TV simgesi (TV'de bekleme logosu da)
        save(banner(640, 360), android / "drawable-nodpi" / "banner.png")   # Android TV ana ekran banner'ı (320x180 dp)
        save(banner(1280, 720), docs / "banner.png")                    # README'nin üstü
        # masaüstü simgeleri ve kurulum görselleri (simge.png'den)
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "packaging" / "make_assets.py")], check=True)
    print("tamam:", ui)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
