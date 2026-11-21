"""Yeni arayüz parçaları (GameTranslator, CouchSubs ve Nino'dan esinlenen düzen; renkler bizim gün batımı teması).

Toggle (açma/kapama anahtarı), Segmented (sekme düğmeleri), RadioCard (seçim kartı), IconTile (degrade ikon kutusu),
SectionCard (başlıklı kart), Pill (durum etiketi), ColorDots (renk seçici), PinInput (8 kutulu kod), SubtitlePreview
(canlı altyazı önizlemesi), Backdrop (ışıltılı arka plan), HelpFab (sağ alttaki yardım düğmesi), PagerDots.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen,
                           QRadialGradient)
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QCheckBox, QFrame, QGraphicsDropShadowEffect,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from . import theme as T
from .widgets import draw_icon, label


# --------------------------------------------------------------------------- arka plan
class Backdrop(QWidget):
    """Koyu zemin üstünde yumuşak pembe/turuncu ışıltı (Nino'nun mavi ışıltısının bizim renklerle hali)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("page")
        self.setAttribute(Qt.WA_StyledBackground, False)

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        p.fillRect(r, QColor(T.BG))
        for cx, cy, rad, color, alpha in ((0.78, -0.05, 0.75, T.A1, 34), (0.08, 1.05, 0.7, T.A2, 22),
                                          (0.45, 0.5, 0.9, T.A3, 10)):
            g = QRadialGradient(r.width() * cx, r.height() * cy, max(r.width(), r.height()) * rad)
            c = QColor(color)
            c.setAlpha(alpha)
            g.setColorAt(0, c)
            c2 = QColor(color)
            c2.setAlpha(0)
            g.setColorAt(1, c2)
            p.fillRect(r, QBrush(g))


# --------------------------------------------------------------------------- açma/kapama
class Toggle(QCheckBox):
    """iOS tarzı anahtar; QCheckBox'ın bütün arayüzü (isChecked, toggled) aynen geçerli."""

    def __init__(self, text: str = "", checked: bool = False):
        super().__init__(text)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("QCheckBox::indicator { width: 0; height: 0; } QCheckBox { spacing: 0; }")

    def sizeHint(self) -> QSize:  # noqa: N802
        fm = self.fontMetrics()
        w = 46 + (12 + fm.horizontalAdvance(self.text()) if self.text() else 0)
        return QSize(w, max(28, fm.height() + 6))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()

    def hitButton(self, pos) -> bool:  # noqa: ANN001, N802
        return self.rect().contains(pos)

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = 24
        track = QRectF(1, (self.height() - h) / 2, 42, h)
        p.setPen(Qt.NoPen)
        if self.isChecked():
            p.setBrush(QBrush(T.accent_gradient(track.left(), 0, track.right(), 0)))
        else:
            p.setBrush(QColor(T.SURFACE3))
        if not self.isEnabled():
            p.setOpacity(0.45)
        p.drawRoundedRect(track, h / 2, h / 2)
        knob = h - 6
        x = track.right() - knob - 3 if self.isChecked() else track.left() + 3
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(x, track.top() + 3, knob, knob))
        if self.text():
            p.setPen(QColor(T.TEXT))
            p.setFont(self.font())
            p.drawText(QRectF(track.right() + 12, 0, self.width() - track.right() - 12, self.height()),
                       Qt.AlignVCenter | Qt.AlignLeft, self.text())


# --------------------------------------------------------------------------- sekme düğmeleri
class Segmented(QFrame):
    """Yan yana seçenekler (TV | Bilgisayar ekranı | İkisi de). changed(değer) sinyali verir."""
    changed = Signal(str)

    def __init__(self, items: list[tuple[str, str]], current: str | None = None, big: bool = False):
        super().__init__()
        self.setObjectName("segmented")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}
        for value, text in items:
            b = QPushButton(text)
            b.setObjectName("segBig" if big else "seg")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, v=value: self.changed.emit(v))
            self.group.addButton(b)
            self.buttons[value] = b
            lay.addWidget(b, 1)
        self.setValue(current if current in self.buttons else items[0][0])

    def value(self) -> str:
        return next((v for v, b in self.buttons.items() if b.isChecked()), "")

    def setValue(self, v: str) -> None:  # noqa: N802
        if v in self.buttons:
            self.buttons[v].setChecked(True)


class Chips(QWidget):
    """Hazır seçenek düğmeleri (Otomatik · Alt orta · Geniş alt bant ...). picked(değer)."""
    picked = Signal(str)

    def __init__(self, items: list[tuple[str, str]], current: str | None = None):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.group = QButtonGroup(self)
        self.buttons: dict[str, QPushButton] = {}
        for value, text in items:
            b = QPushButton(text)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, v=value: self.picked.emit(v))
            self.group.addButton(b)
            self.buttons[value] = b
            lay.addWidget(b)
        lay.addStretch(1)
        if current in self.buttons:
            self.buttons[current].setChecked(True)

    def setValue(self, v: str | None) -> None:  # noqa: N802
        self.group.setExclusive(False)
        for k, b in self.buttons.items():
            b.setChecked(k == v)
        self.group.setExclusive(True)


# --------------------------------------------------------------------------- ikon kutusu
class IconTile(QWidget):
    """Yuvarlatılmış kare içinde degrade zemin ve beyaz ikon; altında yumuşak parıltı (Nino başlık ikonları)."""

    def __init__(self, icon: str, size: int = 56, glow: bool = True, colors: tuple[str, str] | None = None):
        super().__init__()
        self.icon = icon
        self.colors = colors or (T.A1, T.A2)
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        if glow:
            sh = QGraphicsDropShadowEffect(self)
            sh.setBlurRadius(size * 0.6)
            sh.setOffset(0, size * 0.08)
            c = QColor(self.colors[0])
            c.setAlpha(110)
            sh.setColor(c)
            self.setGraphicsEffect(sh)

    def setIcon(self, icon: str) -> None:  # noqa: N802
        self.icon = icon
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, QColor(self.colors[0]))
        g.setColorAt(1, QColor(self.colors[1]))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawRoundedRect(r, r.width() * 0.28, r.width() * 0.28)
        hi = QLinearGradient(r.topLeft(), r.bottomLeft())             # üstte cam parıltısı
        hi.setColorAt(0, QColor(255, 255, 255, 60))
        hi.setColorAt(0.5, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(hi))
        p.drawRoundedRect(r, r.width() * 0.28, r.width() * 0.28)
        m = r.width() * 0.25
        draw_icon(p, self.icon, r.adjusted(m, m, -m, -m), QColor("white"), max(2.0, r.width() / 20))


# --------------------------------------------------------------------------- kartlar
class SectionCard(QFrame):
    """Başlıklı kart: [ikon] Başlık + açıklama, altında içerik. add() Card ile aynı."""

    def __init__(self, title: str = "", subtitle: str = "", icon: str | None = None, accent: bool = False,
                 margins: int = 20, spacing: int = 12):
        super().__init__()
        self.setObjectName("cardAccent" if accent else "card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(margins, margins, margins, margins)
        self.lay.setSpacing(spacing)
        self.title_l = self.sub_l = None
        if title:
            head = QHBoxLayout()
            head.setSpacing(12)
            if icon:
                head.addWidget(IconTile(icon, 36, glow=False), 0, Qt.AlignTop)
            col = QVBoxLayout()
            col.setSpacing(2)
            self.title_l = label(title, "h2")
            col.addWidget(self.title_l)
            if subtitle:
                self.sub_l = label(subtitle, "muted", wrap=True)
                col.addWidget(self.sub_l)
            head.addLayout(col, 1)
            self.head = head
            self.lay.addLayout(head)

    def add(self, w, stretch: int = 0):  # noqa: ANN001
        if isinstance(w, QWidget):
            self.lay.addWidget(w, stretch)
        else:
            self.lay.addLayout(w, stretch)
        return w

    def add_right(self, w: QWidget) -> QWidget:
        """Başlık satırının sağına (ör. 'Aktif' anahtarı, 'Ayarla' düğmesi)."""
        self.head.addWidget(w, 0, Qt.AlignTop)
        return w


class Pill(QLabel):
    """Küçük durum etiketi: ● Eşleşti / ● Hazır / ● Bağlı değil."""
    COLORS = {"ok": T.OK, "warn": T.WARN, "bad": T.BAD, "off": T.FAINT, "info": T.INFO}

    def __init__(self, text: str = "", state: str = "off"):
        super().__init__()
        self.setObjectName("pill")
        self.set(state, text)

    def set(self, state: str, text: str) -> None:
        c = self.COLORS.get(state, T.FAINT)
        self.setText(f"<span style='color:{c}'>●</span>&nbsp; {text}")


class RadioCard(QFrame):
    """Seçim kartı: ◯ Başlık / açıklama; seçilince kenarı vurgulu. İçine ek alan (anahtar kutusu) konabilir."""
    clicked = Signal()

    def __init__(self, title: str, desc: str = "", badge: str = ""):
        super().__init__()
        self.setObjectName("radioCard")
        self.setCursor(Qt.PointingHandCursor)
        self._checked = False
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(18, 14, 18, 14)
        self.lay.setSpacing(8)
        head = QHBoxLayout()
        head.setSpacing(14)
        self.mark = _RadioMark()
        head.addWidget(self.mark, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.title_l = label(title, "h3")
        col.addWidget(self.title_l)
        if desc:
            self.desc_l = label(desc, "muted", wrap=True)
            col.addWidget(self.desc_l)
        head.addLayout(col, 1)
        if badge:
            self.badge = Pill(badge, "ok")
            head.addWidget(self.badge, 0, Qt.AlignTop)
        self.lay.addLayout(head)
        self.body = QWidget()
        self.body_l = QVBoxLayout(self.body)
        self.body_l.setContentsMargins(38, 4, 0, 0)
        self.body_l.setSpacing(8)
        self.body.hide()
        self.lay.addWidget(self.body)

    def add(self, w) -> None:  # noqa: ANN001
        (self.body_l.addWidget if isinstance(w, QWidget) else self.body_l.addLayout)(w)

    def isChecked(self) -> bool:  # noqa: N802
        return self._checked

    def setChecked(self, on: bool) -> None:  # noqa: N802
        self._checked = on
        self.mark.on = on
        self.mark.update()
        self.setProperty("checked", on)
        self.style().unpolish(self)
        self.style().polish(self)
        self.body.setVisible(on and self.body_l.count() > 0)

    def mouseReleaseEvent(self, e) -> None:  # noqa: ANN001, N802
        if e.button() == Qt.LeftButton:
            self.clicked.emit()


class _RadioMark(QWidget):
    def __init__(self):
        super().__init__()
        self.on = False
        self.setFixedSize(24, 24)

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(2, 2, 20, 20)
        if self.on:
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(T.accent_gradient(r.left(), r.top(), r.right(), r.bottom())))
            p.drawEllipse(r)
            p.setBrush(QColor("white"))
            p.drawEllipse(r.adjusted(6, 6, -6, -6))
        else:
            p.setPen(QPen(QColor(T.MUTED), 2))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(r.adjusted(1, 1, -1, -1))


class RadioGroup:
    """RadioCard'ları tek seçimli yapar. changed(değer) çağrısı için on_change verilebilir."""

    def __init__(self, on_change=None):  # noqa: ANN001
        self.cards: dict[str, RadioCard] = {}
        self.on_change = on_change

    def add(self, value: str, card: RadioCard) -> RadioCard:
        self.cards[value] = card
        card.clicked.connect(lambda v=value: self.set(v, user=True))
        return card

    def set(self, value: str, user: bool = False) -> None:
        for k, c in self.cards.items():
            c.setChecked(k == value)
        if user and self.on_change:
            self.on_change(value)

    def value(self) -> str:
        return next((k for k, c in self.cards.items() if c.isChecked()), "")


# --------------------------------------------------------------------------- renk seçici
class ColorDots(QWidget):
    """Yuvarlak renk düğmeleri (GameTranslator'daki yazı rengi seçimi)."""
    changed = Signal(str)

    def __init__(self, colors: list[tuple[str, str]], current: str):
        super().__init__()
        self.colors = colors
        self.current = current
        self.setFixedHeight(36)
        self.setMinimumWidth(len(colors) * 44)
        self.setCursor(Qt.PointingHandCursor)

    def setValue(self, v: str) -> None:  # noqa: N802
        self.current = v
        self.update()

    def _rects(self) -> list[QRectF]:
        return [QRectF(4 + i * 44, 4, 28, 28) for i in range(len(self.colors))]

    def mouseReleaseEvent(self, e) -> None:  # noqa: ANN001, N802
        for (value, _hex), r in zip(self.colors, self._rects()):
            if r.adjusted(-6, -6, 6, 6).contains(e.position()):
                self.current = value
                self.update()
                self.changed.emit(value)
                return

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        for (value, hexc), r in zip(self.colors, self._rects()):
            if value == self.current:
                p.setPen(QPen(QColor(T.A1), 2.5))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(r.adjusted(-4, -4, 4, 4))
            p.setPen(QPen(QColor(0, 0, 0, 80), 1))
            p.setBrush(QColor(hexc))
            p.drawEllipse(r)


# --------------------------------------------------------------------------- 8 kutulu kod
class PinInput(QWidget):
    """PS5'in 8 haneli eşleme kodu için 8 kutu (Nino). Yapıştırma ve geri silme kutular arasında dolaşır."""
    changed = Signal(str)

    def __init__(self, n: int = 8):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self.boxes: list[QLineEdit] = []
        for i in range(n):
            if i == n // 2:
                dash = label("–", "h2")
                dash.setStyleSheet(f"color:{T.MUTED};")
                lay.addWidget(dash)
            b = _PinBox(self, i)
            self.boxes.append(b)
            lay.addWidget(b)
        lay.addStretch(1)

    def text(self) -> str:
        return "".join(b.text() for b in self.boxes)

    def setText(self, s: str) -> None:  # noqa: N802
        digits = [c for c in s if c.isdigit()][:len(self.boxes)]
        for i, b in enumerate(self.boxes):
            b.blockSignals(True)
            b.setText(digits[i] if i < len(digits) else "")
            b.blockSignals(False)
        self.changed.emit(self.text())

    def clear(self) -> None:
        self.setText("")
        self.boxes[0].setFocus()

    def _typed(self, i: int, s: str) -> None:
        digits = "".join(c for c in s if c.isdigit())
        if len(digits) > 1:                       # yapıştırıldı: kalan kutulara dağıt
            self.setText(self.text()[:i] + digits)
            self.boxes[min(i + len(digits), len(self.boxes) - 1)].setFocus()
            return
        self.boxes[i].blockSignals(True)
        self.boxes[i].setText(digits)
        self.boxes[i].blockSignals(False)
        if digits and i + 1 < len(self.boxes):
            self.boxes[i + 1].setFocus()
            self.boxes[i + 1].selectAll()
        self.changed.emit(self.text())


class _PinBox(QLineEdit):
    def __init__(self, owner: PinInput, i: int):
        super().__init__()
        self.owner, self.i = owner, i
        self.setObjectName("pinBox")
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(52, 62)
        self.textEdited.connect(lambda s: owner._typed(i, s))

    def keyPressEvent(self, e) -> None:  # noqa: ANN001, N802
        if e.key() == Qt.Key_Backspace and not self.text() and self.i > 0:
            prev = self.owner.boxes[self.i - 1]
            prev.setText("")
            prev.setFocus()
            self.owner.changed.emit(self.owner.text())
            return
        super().keyPressEvent(e)


# --------------------------------------------------------------------------- canlı altyazı önizlemesi
TEXT_COLORS = [("white", "#FFFFFF"), ("yellow", "#FFE135"), ("cyan", "#5CE1E6"), ("green", "#7CF29A"),
               ("orange", "#FFB347")]


class SubtitlePreview(QWidget):
    """TV'deki görünümün önizlemesi: oyun sahnesi, İngilizce altyazının yeri ve seçilen biçimde Türkçesi."""

    def __init__(self, text: str = "Yanımdan ayrılma ve sesini alçak tut.", english: str = "Stay close to me and keep "
                 "your voice down."):
        super().__init__()
        self.text, self.english = text, english
        self.style_ = {"placement": "cover", "fontSize": 58, "background": 100, "bold": True, "textColor": "white",
                       "bottomPercent": 7, "backgroundShape": "fit", "lineScale": 1.3}
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def heightForWidth(self, w: int) -> int:  # noqa: N802
        return int(w * 9 / 16)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def set_style(self, **kw) -> None:  # noqa: ANN003
        self.style_.update(kw)
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        full = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        h = min(full.height(), full.width() * 9 / 16)
        w = h * 16 / 9
        r = QRectF(full.center().x() - w / 2, full.top(), w, h)
        clip = QPainterPath()
        clip.addRoundedRect(r, 14, 14)
        p.setClipPath(clip)
        sky = QLinearGradient(r.topLeft(), r.bottomLeft())
        sky.setColorAt(0, QColor("#1d1338"))
        sky.setColorAt(0.55, QColor("#6b2a5e"))
        sky.setColorAt(0.85, QColor("#c8603f"))
        sky.setColorAt(1, QColor("#2a1420"))
        p.fillRect(r, QBrush(sky))
        sun = QRadialGradient(r.left() + r.width() * 0.68, r.top() + r.height() * 0.62, r.height() * 0.45)
        sun.setColorAt(0, QColor(255, 196, 120, 170))
        sun.setColorAt(1, QColor(255, 140, 90, 0))
        p.fillRect(r, QBrush(sun))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(20, 10, 26, 230))                          # yer çizgisi ve palmiyeler
        p.drawRect(QRectF(r.left(), r.top() + r.height() * 0.78, r.width(), r.height() * 0.22))
        for i in range(5):
            px = r.left() + r.width() * (0.06 + i * 0.22)
            base = r.top() + r.height() * 0.8
            p.setPen(QPen(QColor(16, 8, 22), max(2.0, r.width() / 260)))
            p.drawLine(QPointF(px, base), QPointF(px + 5, base - r.height() * 0.3))
            top = QPointF(px + 5, base - r.height() * 0.3)
            for a in (-160, -125, -55, -20, -90):
                ang = math.radians(a)
                p.drawLine(top, QPointF(top.x() + math.cos(ang) * r.width() * 0.04,
                                        top.y() + math.sin(ang) * r.height() * 0.05 + r.height() * 0.04))
        s = self.style_
        scale = r.width() / 1920
        en_px = max(8, int(40 * scale))
        fen = T.font(9, QFont.DemiBold)
        fen.setPixelSize(en_px)
        fm_en = QFontMetricsF(fen)
        en_w = fm_en.horizontalAdvance(self.english) + 24 * scale
        en_h = fm_en.height() + 10 * scale
        en_box = QRectF(r.center().x() - en_w / 2, r.bottom() - r.height() * 0.13 - en_h, en_w, en_h)
        p.setPen(Qt.NoPen)                                            # oyunun kendi İngilizce altyazısı
        p.setBrush(QColor(0, 0, 0, 120))
        p.drawRoundedRect(en_box, 4, 4)
        p.setFont(fen)
        p.setPen(QColor(235, 235, 235))
        p.drawText(en_box, Qt.AlignCenter, self.english)

        tr_px = max(9, int(s.get("fontSize", 58) * scale * 0.9))
        if s.get("placement") == "cover":
            tr_px = max(9, int(en_px * float(s.get("lineScale", 1.3))))
        f = T.font(10, QFont.Bold if s.get("bold", True) else QFont.DemiBold)
        f.setPixelSize(tr_px)
        fm = QFontMetricsF(f)
        tw = fm.horizontalAdvance(self.text) + 36 * scale
        th = fm.height() + 16 * scale
        place = s.get("placement", "cover")
        if place == "above":
            y = en_box.top() - th - 8 * scale
        elif place == "below":
            y = en_box.bottom() + 8 * scale
        elif place == "fixed":
            y = r.bottom() - r.height() * s.get("bottomPercent", 7) / 100 - th
        else:
            y = en_box.center().y() - th / 2
            tw = max(tw, en_w + 8 * scale)
        box = QRectF(r.center().x() - tw / 2, y, tw, th)
        if s.get("backgroundShape") == "band":
            box = QRectF(r.left(), y, r.width(), th)
        alpha = max(0, min(100, int(s.get("background", 100)))) / 100
        glass = alpha >= 0.9
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(12, 10, 18, int(255 * (0.86 if glass else alpha))))
        rad = th * 0.32 if glass else 6 * scale + 2
        p.drawRoundedRect(box, rad, rad)
        color = dict(TEXT_COLORS).get(s.get("textColor", "white"), "#FFFFFF")
        path = QPainterPath()
        path.addText(QPointF(box.center().x() - fm.horizontalAdvance(self.text) / 2,
                             box.top() + (th - fm.height()) / 2 + fm.ascent()), f, self.text)
        if alpha < 0.35:
            p.setPen(QPen(QColor(0, 0, 0, 220), max(2.0, tr_px / 9)))
            p.drawPath(path)
        p.fillPath(path, QColor(color))
        p.setClipping(False)
        p.setPen(QPen(QColor(T.BORDER_HI), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, 14, 14)


# --------------------------------------------------------------------------- yardım düğmesi, nokta göstergesi
class HelpFab(QAbstractButton):
    """Sağ altta yuvarlak yardım düğmesi (Nino'daki robot düğmesinin bizim hali): konuşma balonu."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setFixedSize(60, 60)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Sor: takıldığın yeri yaz, rehberi bilen yapay zekâ anlatsın")
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(28)
        sh.setOffset(0, 6)
        c = QColor(T.A1)
        c.setAlpha(120)
        sh.setColor(c)
        self.setGraphicsEffect(sh)

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(4, 4, 52, 52)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(T.accent_gradient(r.left(), r.top(), r.right(), r.bottom())))
        p.drawEllipse(r)
        b = QPainterPath()                                   # konuşma balonu
        bub = QRectF(r.left() + 13, r.top() + 14, 26, 19)
        b.addRoundedRect(bub, 7, 7)
        tail = QPainterPath(QPointF(bub.left() + 7, bub.bottom() - 1))
        tail.lineTo(QPointF(bub.left() + 5, bub.bottom() + 6))
        tail.lineTo(QPointF(bub.left() + 13, bub.bottom() - 1))
        b = b.united(tail)
        p.setBrush(QColor("white"))
        p.drawPath(b)
        p.setBrush(QColor(T.A1))
        for i in range(3):
            p.drawEllipse(QPointF(bub.left() + 7 + i * 6, bub.center().y()), 1.9, 1.9)

    def place(self) -> None:
        par = self.parentWidget()
        self.move(par.width() - self.width() - 26, par.height() - self.height() - 24)
        self.raise_()


class PagerDots(QWidget):
    """Sihirbazın altındaki adım noktaları (geçerli adım uzun çizgi)."""

    def __init__(self, n: int):
        super().__init__()
        self.n, self.current = n, 0
        self.setFixedHeight(14)
        self.setMinimumWidth(n * 18 + 30)

    def setCount(self, n: int) -> None:  # noqa: N802
        self.n = n
        self.setMinimumWidth(n * 18 + 30)
        self.update()

    def setCurrent(self, i: int) -> None:  # noqa: N802
        self.current = i
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        widths = [36 if i == self.current else 9 for i in range(self.n)]
        total = sum(widths) + 9 * (self.n - 1)
        x = (self.width() - total) / 2
        p.setPen(Qt.NoPen)
        for i, w in enumerate(widths):
            r = QRectF(x, 2.5, w, 9)
            if i <= self.current:
                p.setBrush(QBrush(T.accent_gradient(r.left(), 0, r.right(), 0)))
            else:
                p.setBrush(QColor(T.SURFACE3))
            p.drawRoundedRect(r, 4.5, 4.5)
            x += w + 9


def row(*items, spacing: int = 12) -> QHBoxLayout:  # noqa: ANN002
    """Satır: None esnek boşluk, int sabit boşluk."""
    lay = QHBoxLayout()
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(spacing)
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


class Collapsible(QFrame):
    """'› Gelişmiş' gibi açılıp kapanan kart (Nino)."""

    def __init__(self, title: str, opened: bool = False):
        super().__init__()
        self.setObjectName("card")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(20, 14, 20, 14)
        self.lay.setSpacing(12)
        self.head = QPushButton()
        self.head.setObjectName("collapseHead")
        self.head.setCursor(Qt.PointingHandCursor)
        self.head.clicked.connect(lambda: self.setOpen(not self.body.isVisible()))
        self.title = title
        self.lay.addWidget(self.head)
        self.body = QWidget()
        self.body.setObjectName("clearBody")
        self.body.setStyleSheet("#clearBody { background: transparent; }")
        self.body_l = QVBoxLayout(self.body)
        self.body_l.setContentsMargins(0, 0, 0, 4)
        self.body_l.setSpacing(12)
        self.lay.addWidget(self.body)
        self.setOpen(opened)

    def add(self, w):  # noqa: ANN001
        (self.body_l.addWidget if isinstance(w, QWidget) else self.body_l.addLayout)(w)
        return w

    def setOpen(self, on: bool) -> None:  # noqa: N802
        self.body.setVisible(on)
        self.head.setText(("⌄  " if on else "›  ") + self.title)


class StyleCard(QFrame):
    """Hazır altyazı stili kartı: küçük önizleme + ad + açıklama; seçilince vurgulu (Nino)."""
    clicked = Signal()

    def __init__(self, name: str, desc: str, style: dict):
        super().__init__()
        self.setObjectName("radioCard")
        self.setCursor(Qt.PointingHandCursor)
        self.style_ = style
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 12)
        lay.setSpacing(6)
        self.prev = SubtitlePreview("Kim var orada?", "Who's there?")
        self.prev.set_style(**style)
        self.prev.setMinimumHeight(74)
        self.prev.setMaximumHeight(90)
        self.prev.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay.addWidget(self.prev)
        lay.addWidget(label(name, "h3"))
        lay.addWidget(label(desc, "faint"))
        self.setMinimumWidth(150)

    def setChecked(self, on: bool) -> None:  # noqa: N802
        self.setProperty("checked", on)
        self.style().unpolish(self)
        self.style().polish(self)

    def mouseReleaseEvent(self, e) -> None:  # noqa: ANN001, N802
        if e.button() == Qt.LeftButton:
            self.clicked.emit()


class HealthRow(QFrame):
    """Sistem sağlığı satırı: ikon, başlık, alt yazı, öneri ve sağda ● İyi / İyileştirilebilir."""

    def __init__(self):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 12, 0, 12)
        lay.setSpacing(14)
        self.icon = IconTile("check", 36, glow=False, colors=(T.SURFACE3, T.SURFACE2))
        lay.addWidget(self.icon, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.title = label("", "h3")
        self.sub = label("", "muted", wrap=True)
        self.advice = label("", None, wrap=True)
        col.addWidget(self.title)
        col.addWidget(self.sub)
        col.addWidget(self.advice)
        lay.addLayout(col, 1)
        self.state = label("", "h3")
        lay.addWidget(self.state, 0, Qt.AlignTop)

    def set(self, row: dict) -> None:
        from ..saglik import STATE_TEXT
        self.icon.setIcon(row["icon"])
        self.title.setText(row["title"])
        self.sub.setText(row["sub"])
        self.advice.setText(row["advice"])
        self.advice.setVisible(bool(row["advice"]))
        c = Pill.COLORS.get(row["state"], T.FAINT)
        self.state.setText(f"<span style='color:{c}'>●&nbsp; {STATE_TEXT.get(row['state'], '')}</span>")
