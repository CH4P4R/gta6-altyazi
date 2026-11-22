"""Özel çizilmiş bileşenler."""

from __future__ import annotations

import math

from PySide6.QtCore import (Property, QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSize, Qt, QTimer,
                            QVariantAnimation, Signal)
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QApplication, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget)

from . import theme as T


# --------------------------------------------------------------------------- marka görselleri
_MARKA: dict[str, object] = {}


def marka_path(name: str):  # noqa: ANN201
    """altyazi/ui/marka içindeki görsel (tools/marka_gorsel.py çizer; kurulumda aynı yerde)."""
    from pathlib import Path
    return Path(__file__).resolve().parent / "marka" / name


def marka_image(name: str):  # noqa: ANN201
    """QImage (önbellekli); dosya yoksa boş QImage: çizen yer yedek çizime geçer."""
    from PySide6.QtGui import QImage
    if name not in _MARKA:
        _MARKA[name] = QImage(str(marka_path(name)))
    return _MARKA[name]


def marka_pixmap(name: str, size: int):  # noqa: ANN201
    """Kare görseli size×size (yüksek DPI ekranda keskin) QPixmap olarak verir."""
    from PySide6.QtGui import QPixmap
    key = f"{name}@{size}"
    if key not in _MARKA:
        img = marka_image(name)
        dpr = 2.0
        if img.isNull():
            pm = QPixmap()
        else:
            pm = QPixmap.fromImage(img.scaled(int(size * dpr), int(size * dpr), Qt.KeepAspectRatio,
                                              Qt.SmoothTransformation))
            pm.setDevicePixelRatio(dpr)
        _MARKA[key] = pm
    return _MARKA[key]


# --------------------------------------------------------------------------- yardımcılar
def label(text: str = "", obj: str | None = None, wrap: bool = False) -> QLabel:
    lb = QLabel(text)
    if obj:
        lb.setObjectName(obj)
    lb.setWordWrap(wrap)
    lb.setTextInteractionFlags(Qt.TextSelectableByMouse if obj in ("muted", None) and wrap else Qt.NoTextInteraction)
    return lb


def button(text: str, obj: str | None = None, slot=None, tip: str = "") -> QPushButton:  # noqa: ANN001
    b = QPushButton(text)
    if obj:
        b.setObjectName(obj)
    b.setCursor(Qt.PointingHandCursor)
    if slot:
        b.clicked.connect(slot)
    if tip:
        b.setToolTip(tip)
    return b


class Card(QFrame):
    def __init__(self, inner: bool = False, margins: int = 18, spacing: int = 10):
        super().__init__()
        self.setObjectName("cardInner" if inner else "card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(margins, margins, margins, margins)
        self.lay.setSpacing(spacing)

    def add(self, w, stretch: int = 0):  # noqa: ANN001
        if isinstance(w, QWidget):
            self.lay.addWidget(w, stretch)
        else:
            self.lay.addLayout(w, stretch)
        return w


def hbox(*items, spacing: int = 10, margins: tuple = (0, 0, 0, 0)) -> QHBoxLayout:  # noqa: ANN002
    lay = QHBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    for it in items:
        if it is None:
            lay.addStretch(1)
        elif isinstance(it, int):
            lay.addSpacing(it)
        elif isinstance(it, QWidget):
            lay.addWidget(it)
        else:
            lay.addLayout(it)
    return lay


def vbox(*items, spacing: int = 8, margins: tuple = (0, 0, 0, 0)) -> QVBoxLayout:  # noqa: ANN002
    lay = QVBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    for it in items:
        if it is None:
            lay.addStretch(1)
        elif isinstance(it, int):
            lay.addSpacing(it)
        elif isinstance(it, QWidget):
            lay.addWidget(it)
        else:
            lay.addLayout(it)
    return lay


# --------------------------------------------------------------------------- ikonlar
def draw_icon(p: QPainter, name: str, r: QRectF, color: QColor, width: float = 1.8) -> None:
    """Basit çizgi ikonlar (her çözünürlükte keskin)."""
    p.save()
    pen = QPen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    cx, cy = r.center().x(), r.center().y()
    if name == "home":
        path = QPainterPath()
        path.moveTo(x + w * .12, cy - h * .02)
        path.lineTo(cx, y + h * .14)
        path.lineTo(x + w * .88, cy - h * .02)
        p.drawPath(path)
        p.drawRoundedRect(QRectF(x + w * .24, cy - h * .06, w * .52, h * .46), 2, 2)
    elif name == "regions":
        p.drawRoundedRect(QRectF(x + w * .1, y + h * .18, w * .8, h * .64), 3, 3)
        p.setPen(QPen(color, width, Qt.DashLine, Qt.RoundCap))
        p.drawRect(QRectF(x + w * .26, y + h * .52, w * .48, h * .18))
    elif name == "tv":
        p.drawRoundedRect(QRectF(x + w * .08, y + h * .16, w * .84, h * .56), 3, 3)
        p.drawLine(QPointF(x + w * .34, y + h * .86), QPointF(x + w * .66, y + h * .86))
        p.drawLine(QPointF(cx, y + h * .72), QPointF(cx, y + h * .86))
    elif name == "translate":
        f = T.font(9, QFont.Bold)
        f.setPixelSize(int(h * .48))
        p.setFont(f)
        p.drawText(QRectF(x, y + h * .02, w * .55, h * .6), Qt.AlignCenter, "A")
        p.drawText(QRectF(x + w * .42, y + h * .38, w * .55, h * .6), Qt.AlignCenter, "Ç")
        p.drawLine(QPointF(x + w * .2, y + h * .82), QPointF(x + w * .36, y + h * .66))
    elif name == "history":
        p.drawEllipse(QRectF(x + w * .14, y + h * .14, w * .72, h * .72))
        p.drawLine(QPointF(cx, cy), QPointF(cx, y + h * .3))
        p.drawLine(QPointF(cx, cy), QPointF(cx + w * .15, cy + h * .1))
    elif name == "settings":
        p.drawEllipse(QRectF(cx - w * .14, cy - h * .14, w * .28, h * .28))
        for i in range(8):
            a = i * math.pi / 4
            p.drawLine(QPointF(cx + math.cos(a) * w * .26, cy + math.sin(a) * h * .26),
                       QPointF(cx + math.cos(a) * w * .38, cy + math.sin(a) * h * .38))
        p.drawEllipse(QRectF(cx - w * .27, cy - h * .27, w * .54, h * .54))
    elif name == "ps":
        p.drawRoundedRect(QRectF(x + w * .1, y + h * .3, w * .8, h * .44), h * .22, h * .22)
        p.drawLine(QPointF(x + w * .26, cy + h * .02), QPointF(x + w * .4, cy + h * .02))
        p.drawLine(QPointF(x + w * .33, cy - h * .05), QPointF(x + w * .33, cy + h * .09))
        p.drawEllipse(QPointF(x + w * .66, cy - h * .02), w * .03, w * .03)
        p.drawEllipse(QPointF(x + w * .74, cy + h * .06), w * .03, w * .03)
    elif name == "bolt":
        path = QPainterPath()
        path.moveTo(x + w * .56, y + h * .1)
        path.lineTo(x + w * .26, y + h * .56)
        path.lineTo(x + w * .5, y + h * .56)
        path.lineTo(x + w * .42, y + h * .9)
        path.lineTo(x + w * .74, y + h * .42)
        path.lineTo(x + w * .5, y + h * .42)
        path.closeSubpath()
        p.drawPath(path)
    elif name == "phone":
        p.drawRoundedRect(QRectF(x + w * .3, y + h * .1, w * .4, h * .8), 4, 4)
        p.drawLine(QPointF(cx - w * .05, y + h * .78), QPointF(cx + w * .05, y + h * .78))
    elif name == "play":
        path = QPainterPath()
        path.moveTo(x + w * .32, y + h * .2)
        path.lineTo(x + w * .82, cy)
        path.lineTo(x + w * .32, y + h * .8)
        path.closeSubpath()
        p.setBrush(color)
        p.drawPath(path)
    elif name == "stop":
        p.setBrush(color)
        p.drawRoundedRect(QRectF(x + w * .26, y + h * .26, w * .48, h * .48), 3, 3)
    elif name == "monitor":                             # masaüstü ekranı
        p.drawRoundedRect(QRectF(x + w * .08, y + h * .14, w * .84, h * .56), 3, 3)
        p.drawLine(QPointF(cx, y + h * .70), QPointF(cx, y + h * .84))
        p.drawLine(QPointF(x + w * .30, y + h * .86), QPointF(x + w * .70, y + h * .86))
    elif name == "swap":                                # iki yönlü ok
        p.drawLine(QPointF(x + w * .15, y + h * .35), QPointF(x + w * .85, y + h * .35))
        p.drawLine(QPointF(x + w * .68, y + h * .20), QPointF(x + w * .85, y + h * .35))
        p.drawLine(QPointF(x + w * .68, y + h * .50), QPointF(x + w * .85, y + h * .35))
        p.drawLine(QPointF(x + w * .85, y + h * .68), QPointF(x + w * .15, y + h * .68))
        p.drawLine(QPointF(x + w * .32, y + h * .53), QPointF(x + w * .15, y + h * .68))
        p.drawLine(QPointF(x + w * .32, y + h * .83), QPointF(x + w * .15, y + h * .68))
    elif name == "check":
        path = QPainterPath()
        path.moveTo(x + w * .2, cy)
        path.lineTo(x + w * .42, y + h * .72)
        path.lineTo(x + w * .82, y + h * .3)
        p.drawPath(path)
    elif name == "guide":                              # açık kitap
        path = QPainterPath()
        path.moveTo(cx, y + h * .28)
        path.cubicTo(cx - w * .12, y + h * .18, x + w * .22, y + h * .18, x + w * .1, y + h * .24)
        path.lineTo(x + w * .1, y + h * .8)
        path.cubicTo(x + w * .22, y + h * .74, cx - w * .12, y + h * .74, cx, y + h * .84)
        path.cubicTo(cx + w * .12, y + h * .74, x + w * .78, y + h * .74, x + w * .9, y + h * .8)
        path.lineTo(x + w * .9, y + h * .24)
        path.cubicTo(x + w * .78, y + h * .18, cx + w * .12, y + h * .18, cx, y + h * .28)
        p.drawPath(path)
        p.drawLine(QPointF(cx, y + h * .28), QPointF(cx, y + h * .84))
    elif name == "copy":
        p.drawRoundedRect(QRectF(x + w * .3, y + h * .3, w * .5, h * .55), 2, 2)
        p.drawPolyline([QPointF(x + w * .2, y + h * .7), QPointF(x + w * .2, y + h * .15),
                        QPointF(x + w * .65, y + h * .15)])
    p.restore()


class Icon(QWidget):
    def __init__(self, name: str, size: int = 22, color: str = T.TEXT):
        super().__init__()
        self.name, self.color = name, QColor(color)
        self.setFixedSize(size, size)

    def setColor(self, c: str) -> None:  # noqa: N802
        self.color = QColor(c)
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        draw_icon(p, self.name, QRectF(self.rect()).adjusted(1, 1, -1, -1), self.color)


class NavButton(QPushButton):
    def __init__(self, text: str, icon: str):
        super().__init__(text)
        self.icon_name = icon
        self.setObjectName("navButton")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(42)

    def paintEvent(self, e) -> None:  # noqa: ANN001, N802
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QColor(T.TEXT if (self.isChecked() or self.underMouse()) else T.MUTED)
        draw_icon(p, self.icon_name, QRectF(14, (self.height() - 20) / 2, 20, 20), c)
        if self.isChecked():
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(T.accent_gradient(0, 0, 0, self.height())))
            p.drawRoundedRect(QRectF(0, 9, 3.5, self.height() - 18), 2, 2)


class Logo(QWidget):
    """Kenar çubuğunun üstü: uygulama simgesi + 'GTA6 Altyazı' + 'TÜRKÇE ALTYAZI' (Nino'nun sol üstü gibi)."""

    def __init__(self, scale: float = 1.0):
        super().__init__()
        self.s = scale
        self.setFixedHeight(int(58 * scale))
        self.setMinimumWidth(int(176 * scale))

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        s = self.s
        badge = QRectF(0, 3 * s, 52 * s, 52 * s)
        pm = marka_pixmap("simge_yazisiz.png", int(52 * s))
        if not pm.isNull():
            p.drawPixmap(badge.toRect(), pm)
        else:
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(T.accent_gradient(badge.left(), badge.top(), badge.right(), badge.bottom())))
            p.drawRoundedRect(badge, 12 * s, 12 * s)
        f1 = T.font(10, QFont.Black, display=True)
        f1.setPixelSize(int(19 * s))
        p.setFont(f1)
        p.setPen(QColor(T.TEXT))
        p.drawText(QPointF(62 * s, 28 * s), "GTA6 Altyazı")
        f2 = T.font(8, QFont.DemiBold)
        f2.setPixelSize(int(9.5 * s))
        f2.setLetterSpacing(QFont.AbsoluteSpacing, 2.2 * s)
        p.setFont(f2)
        p.setPen(QColor("#5fa8ff"))
        p.drawText(QPointF(63 * s, 45 * s), "TÜRKÇE ALTYAZI")


class Dot(QWidget):
    COLORS = {"ok": T.OK, "warn": T.WARN, "bad": T.BAD, "off": T.FAINT, "info": T.INFO}

    def __init__(self, state: str = "off", size: int = 10):
        super().__init__()
        self.state = state
        self.setFixedSize(size + 8, size + 8)
        self._pulse = 0.0
        self._anim = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=1400, loopCount=-1)
        self._anim.valueChanged.connect(self._tick)

    def _tick(self, v) -> None:  # noqa: ANN001
        self._pulse = float(v)
        self.update()

    def setState(self, s: str) -> None:  # noqa: N802
        self.state = s
        if s in ("warn", "info"):
            self._anim.start()
        else:
            self._anim.stop()
            self._pulse = 0
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QColor(self.COLORS.get(self.state, T.FAINT))
        r = QRectF(self.rect())
        if self.state != "off":
            glow = QColor(c)
            glow.setAlphaF(0.25 * (1 - self._pulse) if self._anim.state() else 0.22)
            p.setPen(Qt.NoPen)
            p.setBrush(glow)
            grow = 4 * self._pulse
            p.drawEllipse(r.adjusted(-grow + 0, -grow + 0, grow, grow).adjusted(0.5, 0.5, -0.5, -0.5))
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawEllipse(r.adjusted(4, 4, -4, -4))


class StatusCard(Card):
    """Ana ekrandaki durum kartı: ikon, başlık, durum noktası, açıklama, eylem düğmesi."""

    def __init__(self, icon: str, title: str, action: str | None = None, slot=None):  # noqa: ANN001
        super().__init__(margins=16, spacing=6)
        self.icon = Icon(icon, 22, T.A2)
        self.title = label(title, "h3")
        self.dot = Dot()
        self.status = label("", "muted", wrap=True)
        self.status.setMinimumHeight(36)
        self.status.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.add(hbox(self.icon, self.title, None, self.dot, spacing=8))
        self.add(self.status)
        self.action = None
        if action:
            self.action = button(action, None, slot)
            self.add(self.action)
        self.setMinimumWidth(190)

    def set(self, state: str, text: str) -> None:
        self.dot.setState(state)
        self.status.setText(text)


class StartButton(QWidget):
    """Büyük başlat/durdur düğmesi: degrade, çalışırken nefes alan halka."""
    clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setFixedSize(132, 132)
        self.setCursor(Qt.PointingHandCursor)
        self.running = False
        self.enabled_ = True
        self._hover = False
        self._phase = 0.0
        self._anim = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=2200, loopCount=-1)
        self._anim.valueChanged.connect(lambda v: (setattr(self, "_phase", float(v)), self.update()))

    def setRunning(self, r: bool) -> None:  # noqa: N802
        self.running = r
        self._anim.start() if r else self._anim.stop()
        self.update()

    def setEnabledLook(self, e: bool) -> None:  # noqa: N802
        self.enabled_ = e
        self.setCursor(Qt.PointingHandCursor if e else Qt.ForbiddenCursor)
        self.update()

    def enterEvent(self, _e) -> None:  # noqa: ANN001, N802
        self._hover = True
        self.update()

    def leaveEvent(self, _e) -> None:  # noqa: ANN001, N802
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, e) -> None:  # noqa: ANN001, N802
        if self.enabled_ and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(10, 10, -10, -10)
        if self.running:  # nefes alan halka
            a = 0.5 + 0.5 * math.sin(self._phase * 2 * math.pi)
            ring = QColor(T.A1)
            ring.setAlphaF(0.18 + 0.22 * a)
            p.setPen(QPen(ring, 3 + 4 * a))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(r.adjusted(-4, -4, 4, 4))
        p.setPen(Qt.NoPen)
        if not self.enabled_:
            p.setBrush(QColor(T.SURFACE3))
        elif self.running:
            p.setBrush(QColor(T.SURFACE2))
            p.setPen(QPen(QColor(T.BORDER_HI), 1.5))
        else:
            g = T.accent_gradient(r.left(), r.top(), r.right(), r.bottom())
            if self._hover:
                g.setColorAt(0, QColor("#ff6bb4"))
                g.setColorAt(1, QColor("#ffb36b"))
            p.setBrush(QBrush(g))
        p.drawEllipse(r)
        ic = QRectF(r.center().x() - 22, r.center().y() - 22, 44, 44)
        draw_icon(p, "stop" if self.running else "play", ic,
                  QColor(T.A1 if self.running else ("white" if self.enabled_ else T.FAINT)), 2)


class Sparkline(QWidget):
    def __init__(self):
        super().__init__()
        self.values: list[float] = []
        self.setMinimumHeight(46)

    def push(self, v: float) -> None:
        self.values = (self.values + [v])[-40:]
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        if len(self.values) < 2:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        hi = max(max(self.values), 150.0)
        n = len(self.values)
        pts = [QPointF(i * (w - 4) / (n - 1) + 2, h - 3 - (v / hi) * (h - 8)) for i, v in enumerate(self.values)]
        area = QPainterPath(QPointF(pts[0].x(), h))
        for pt in pts:
            area.lineTo(pt)
        area.lineTo(QPointF(pts[-1].x(), h))
        g = T.accent_gradient(0, 0, w, 0)
        fill = QColor(T.A1)
        fill.setAlphaF(0.12)
        p.setPen(Qt.NoPen)
        p.setBrush(fill)
        p.drawPath(area)
        line = QPainterPath(pts[0])
        for pt in pts[1:]:
            line.lineTo(pt)
        p.setPen(QPen(QBrush(g), 2))
        p.setBrush(Qt.NoBrush)
        p.drawPath(line)


class QrCode(QWidget):
    def __init__(self, size: int = 120):
        super().__init__()
        self.matrix = None
        self.setFixedSize(size, size)

    def setData(self, text: str) -> None:  # noqa: N802
        try:
            import segno
            self.matrix = segno.make(text, error="m").matrix
        except Exception:  # noqa: BLE001
            self.matrix = None
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("white"))
        p.drawRoundedRect(QRectF(self.rect()), 10, 10)
        if not self.matrix:
            return
        n = len(self.matrix)
        quiet = 2
        cell = (self.width() - 8) / (n + 2 * quiet)
        off = 4 + quiet * cell
        p.setBrush(QColor("#0d0b13"))
        for y, row in enumerate(self.matrix):
            for x, v in enumerate(row):
                if v:
                    p.drawRect(QRectF(off + x * cell, off + y * cell, cell + 0.4, cell + 0.4))


class FeedItem(QFrame):
    """Canlı çeviri akışındaki bir satır."""

    def __init__(self, item):  # noqa: ANN001
        super().__init__()
        self.setObjectName("cardInner")
        self.seq = item.seq
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(3)
        self.tag = label("", "tag")
        self.meta = label("", "faint")
        self.copy = button("Kopyala", "ghost", self._copy)
        self.copy.setFixedHeight(26)
        lay.addLayout(hbox(self.tag, None, self.meta, self.copy, spacing=6))
        self.tr = label("", "feedTr", wrap=True)
        self.en = label("", "muted", wrap=True)
        lay.addWidget(self.tr)
        lay.addWidget(self.en)
        self.update_item(item)

    def update_item(self, it) -> None:  # noqa: ANN001
        zone = "EKRAN" if it.zone.startswith("tam") else it.zone.upper()
        self.tag.setText(zone)
        q = "✓ " if it.quality >= 2 else ""
        self.meta.setText(f"{q}{it.source} · {it.latency_ms:.0f} ms")
        self.tr.setText(it.text)
        self.en.setText(it.english)
        self._text = it.text

    def _copy(self) -> None:
        QApplication.clipboard().setText(self._text)
        self.copy.setText("Kopyalandı")
        QTimer.singleShot(1200, lambda: self.copy.setText("Kopyala"))


class Toast(QLabel):
    """Pencerenin altında beliren kısa bilgi balonu."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setStyleSheet(f"background:{T.SURFACE3}; border:1px solid {T.BORDER_HI}; border-radius:12px;"
                           f"padding:10px 16px; color:{T.TEXT}; font-weight:600;")
        self.setAlignment(Qt.AlignCenter)
        self.hide()
        self._eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._eff)
        self._anim = QPropertyAnimation(self._eff, b"opacity", self)
        self._timer = QTimer(self, singleShot=True, timeout=self._fade)

    def show_text(self, text: str, ms: int = 2600) -> None:
        self.setText(text)
        self.adjustSize()
        par = self.parentWidget()
        self.move((par.width() - self.width()) // 2 + 110, par.height() - self.height() - 26)
        self._anim.stop()
        self._eff.setOpacity(1.0)
        self.show()
        self.raise_()
        self._timer.start(ms)

    def _fade(self) -> None:
        self._anim.setDuration(400)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.finished.connect(self.hide)
        self._anim.start()


class Stepper(QWidget):
    """Sihirbazın sol tarafındaki adım listesi."""

    def __init__(self, steps: list[str], big: bool = False):
        super().__init__()
        self.steps = steps
        self.current = 0
        self.big = big
        self.setFixedWidth(260 if big else 230)

    def setSteps(self, steps: list[str]) -> None:  # noqa: N802
        self.steps = steps
        self.update()

    def setCurrent(self, i: int) -> None:  # noqa: N802
        self.current = i
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        y0, gap, rad = (130, 70, 17) if self.big else (150, 62, 14)
        fs_num, fs_name = (11, 13) if self.big else (9, 10.5)
        for i, name in enumerate(self.steps):
            cy = y0 + i * gap
            if i < len(self.steps) - 1:
                p.setPen(QPen(QColor(T.A1 if i < self.current else T.BORDER_HI), 2))
                p.drawLine(QPointF(30 + rad, cy + rad + 1), QPointF(30 + rad, cy + gap - rad - 1))
            r = QRectF(30, cy - rad, rad * 2, rad * 2)
            p.setPen(Qt.NoPen)
            if i < self.current:
                p.setBrush(QBrush(T.accent_gradient(r.left(), r.top(), r.right(), r.bottom())))
                p.drawEllipse(r)
                draw_icon(p, "check", r.adjusted(6, 6, -6, -6), QColor("white"), 2)
            elif i == self.current:
                p.setBrush(QBrush(T.accent_gradient(r.left(), r.top(), r.right(), r.bottom())))
                p.drawEllipse(r)
                f = T.font(fs_num, QFont.Bold)
                p.setFont(f)
                p.setPen(QColor("white"))
                p.drawText(r, Qt.AlignCenter, str(i + 1))
            else:
                p.setBrush(QColor(T.SURFACE2))
                p.setPen(QPen(QColor(T.BORDER_HI), 1.5))
                p.drawEllipse(r)
                p.setFont(T.font(fs_num, QFont.Bold))
                p.setPen(QColor(T.MUTED))
                p.drawText(r, Qt.AlignCenter, str(i + 1))
            p.setFont(T.font(fs_name, QFont.DemiBold if i == self.current else QFont.Normal))
            p.setPen(QColor(T.TEXT if i <= self.current else T.MUTED))
            p.drawText(QPointF(30 + rad * 2 + 16, cy + (6 if self.big else 5)), name)


class PreviewArt(QWidget):
    """Vice City gün batımı üstünde Türkçe altyazı önizlemesi (sihirbaz için)."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(190)

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        import random
        from PySide6.QtGui import QLinearGradient, QRadialGradient
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        clip = QPainterPath()
        clip.addRoundedRect(r, 16, 16)
        p.setClipPath(clip)
        sky = QLinearGradient(r.topLeft(), r.bottomLeft())
        sky.setColorAt(0, QColor("#2b1055"))
        sky.setColorAt(0.45, QColor("#a1336e"))
        sky.setColorAt(0.75, QColor("#ff8a4c"))
        sky.setColorAt(1, QColor("#ffc36b"))
        p.fillRect(r, QBrush(sky))
        sun = QRadialGradient(r.center().x(), r.bottom() - r.height() * 0.28, r.height() * 0.5)
        sun.setColorAt(0, QColor(255, 220, 150, 230))
        sun.setColorAt(0.35, QColor(255, 150, 90, 120))
        sun.setColorAt(1, QColor(255, 120, 80, 0))
        p.fillRect(r, QBrush(sun))
        rnd = random.Random(6)
        x = r.left()
        p.setPen(Qt.NoPen)
        while x < r.right():                      # şehir silueti
            bw = rnd.uniform(18, 46)
            bh = rnd.uniform(0.18, 0.62) * r.height()
            p.setBrush(QColor(28, 12, 40, 235))
            p.drawRect(QRectF(x, r.bottom() - bh, bw - 3, bh))
            p.setBrush(QColor(255, 190, 120, 120))
            for wy in range(int(r.bottom() - bh + 8), int(r.bottom() - 6), 9):
                if rnd.random() < 0.35:
                    p.drawRect(QRectF(x + rnd.uniform(3, bw - 9), wy, 3, 4))
            x += bw
        for i in range(4):                         # palmiyeler
            px = r.left() + r.width() * (0.08 + i * 0.29)
            p.setPen(QPen(QColor(18, 8, 26), 4))
            p.drawLine(QPointF(px, r.bottom()), QPointF(px + 6, r.bottom() - r.height() * 0.42))
            top = QPointF(px + 6, r.bottom() - r.height() * 0.42)
            p.setPen(QPen(QColor(18, 8, 26), 3))
            for a in (-150, -120, -60, -30, -90):
                ang = math.radians(a)
                p.drawLine(top, QPointF(top.x() + math.cos(ang) * 30, top.y() + math.sin(ang) * 14 + 12))
        text = "Lucia, Vice City'den hemen çıkmamız lazım. Şimdi!"
        f = T.font(10, QFont.DemiBold)
        px = max(13, int(r.height() * 0.085))
        while px > 12:
            f.setPixelSize(px)
            if QFontMetricsF(f).horizontalAdvance(text) + 28 <= r.width() * 0.8:
                break
            px -= 1
        fm = QFontMetricsF(f)
        tw, th = fm.horizontalAdvance(text) + 28, fm.height() + 14
        box = QRectF(r.center().x() - tw / 2, r.bottom() - th - r.height() * 0.08, tw, th)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 235))
        p.drawRoundedRect(box, 8, 8)
        path = QPainterPath()
        path.addText(QPointF(box.left() + 14, box.top() + 7 + fm.ascent()), f, text)
        p.setPen(QPen(QColor("black"), 3))
        p.drawPath(path)
        p.fillPath(path, QColor("white"))
        tag = QRectF(r.left() + 12, r.top() + 12, 128, 24)
        p.setBrush(QColor(0, 0, 0, 120))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(tag, 12, 12)
        p.setPen(QColor(T.OK))
        p.setFont(T.font(8.5, QFont.Bold))
        p.drawText(tag, Qt.AlignCenter, "● CANLI · 42 ms")


def scroll_page(content: QWidget):  # noqa: ANN201
    from PySide6.QtWidgets import QScrollArea
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setWidget(content)
    sa.setFrameShape(QFrame.NoFrame)
    return sa


def fit_font_metrics(text: str, f: QFont, width: float) -> float:
    return QFontMetricsF(f).horizontalAdvance(text) / max(width, 1)


__all__ = ["Card", "Icon", "NavButton", "Logo", "Dot", "StatusCard", "StartButton", "Sparkline", "QrCode",
           "FeedItem", "Toast", "Stepper", "PreviewArt", "label", "button", "hbox", "vbox", "scroll_page", "draw_icon",
           "QSize", "QSizePolicy", "Property"]


class IconBadge(QWidget):
    """Degrade daire içinde ikon (sihirbazın kartları)."""

    def __init__(self, icon: str, size: int = 52, active: bool = True):
        super().__init__()
        self.icon, self.active = icon, active
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def setActive(self, on: bool) -> None:  # noqa: N802
        self.active = on
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        p.setPen(Qt.NoPen)
        if self.active:
            p.setBrush(QBrush(T.accent_gradient(r.left(), r.top(), r.right(), r.bottom())))
        else:
            p.setBrush(QColor(T.SURFACE3))
        p.drawEllipse(r)
        m = r.width() * 0.26
        draw_icon(p, self.icon, r.adjusted(m, m, -m, -m), QColor("white" if self.active else T.A2),
                  max(2.0, r.width() / 22))
