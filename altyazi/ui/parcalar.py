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
from .widgets import draw_icon, label, marka_image, marka_path, marka_pixmap


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


# TV uygulamasının yazı tipleri (tv-web/src/fonts; kurulumda tv-web/build/tizen/fonts): önizleme TV'deki gibi görünsün
TV_FONTS = [("aksiyon", "Aksiyon (GTA tarzı)", "BarlowCondensed-SemiBold.ttf"), ("modern", "Modern", "Barlow-SemiBold.ttf"),
            ("yuvarlak", "Yuvarlak", "Nunito-Variable.ttf"), ("sade", "Sade", "")]
_TV_FAMILIES: dict[str, str] = {}


def tv_font(key: str, px: int, bold: bool = True) -> QFont:
    """Altyazı yazı tipinin QFont'u; dosya bulunamazsa uygulamanın yazı tipi (Sade gibi)."""
    if not _TV_FAMILIES:
        from PySide6.QtGui import QFontDatabase
        from ..paths import resource
        for k, _name, file in TV_FONTS:
            if not file:
                continue
            for d in ("tv-web/src/fonts", "tv-web/build/tizen/fonts"):
                path = resource(d) / file
                if path.exists():
                    fams = QFontDatabase.applicationFontFamilies(QFontDatabase.addApplicationFont(str(path)))
                    if fams:
                        _TV_FAMILIES[k] = fams[0]
                    break
        _TV_FAMILIES.setdefault("_", "")
    fam = _TV_FAMILIES.get(key)
    f = QFont(fam) if fam else T.font(10)
    f.setWeight(QFont.Bold if bold else QFont.DemiBold)
    f.setPixelSize(max(1, int(px)))
    return f


class FontChoice(QWidget):
    """Dört yazı tipi düğmesi (2×2), her biri kendi yazı tipiyle yazılı; seçili olan mavi çerçeveli."""
    changed = Signal(str)

    def __init__(self, current: str):
        super().__init__()
        from PySide6.QtWidgets import QGridLayout
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(10)
        self.buttons: dict[str, QPushButton] = {}
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for i, (key, name, _f) in enumerate(TV_FONTS):
            b = QPushButton(name)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setObjectName("fontChoice")
            fam = tv_font(key, 17, True).family()
            b.setMinimumHeight(52)
            # Genel QSS düğmenin yazı tipini ezer: ailesi ve boyutu burada, her düğme kendi yazı tipiyle görünsün
            b.setStyleSheet("QPushButton#fontChoice { border-radius: 14px; border: 1.5px solid %s; background: %s;"
                            " padding: 8px 10px; color: %s; font-family: '%s'; font-size: 17px; font-weight: 700; }"
                            " QPushButton#fontChoice:checked { border: 2px solid %s; color: %s; }"
                            % (T.BORDER, T.SURFACE2, T.TEXT, fam, T.A1, T.A2))
            b.clicked.connect(lambda _=False, k=key: self._pick(k))
            self.group.addButton(b)
            self.buttons[key] = b
            grid.addWidget(b, i // 2, i % 2)
        self.setValue(current)

    def value(self) -> str:
        return next((k for k, b in self.buttons.items() if b.isChecked()), "modern")

    def setValue(self, key: str) -> None:  # noqa: N802
        (self.buttons.get(key) or self.buttons["modern"]).setChecked(True)

    def _pick(self, key: str) -> None:
        self.setValue(key)
        self.changed.emit(key)


class ViewChoice(QWidget):
    """Ana ekranın görünümü (Nino'daki Arayüz seçimi): 'Salon' (TV, sehpa, PS5, fiş) ya da 'Cam düğme'. Küçük resimli
    iki kart; seçili olan mavi çerçeveli."""
    changed = Signal(str)

    def __init__(self, current: str):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        self.cards: dict[str, QAbstractButton] = {}
        for key, name in (("fis", "Salon"), ("dugme", "Cam düğme")):
            c = _ViewCard(key, name)
            c.clicked.connect(lambda _=False, k=key: self._pick(k))
            self.cards[key] = c
            lay.addWidget(c, 1)
        self.setValue(current)

    def value(self) -> str:
        return next((k for k, c in self.cards.items() if c.isChecked()), "fis")

    def setValue(self, key: str) -> None:  # noqa: N802
        for k, c in self.cards.items():
            c.setChecked(k == key)

    def _pick(self, key: str) -> None:
        self.setValue(key)
        self.changed.emit(key)


class _ViewCard(QAbstractButton):
    def __init__(self, key: str, name: str):
        super().__init__()
        self.key, self.name = key, name
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        on = self.isChecked()
        p.setPen(QPen(QColor(T.A1) if on else QColor(T.BORDER), 2.2 if on else 1.2))
        p.setBrush(QColor(T.SURFACE2))
        p.drawRoundedRect(r, 18, 18)
        art = QRectF(r.left() + 14, r.top() + 12, r.width() - 28, r.height() - 52)
        if self.key == "fis":
            img = marka_image("sahne.png")
            if not img.isNull():
                s = min(art.width() / img.width(), art.height() / img.height())
                w, h = img.width() * s, img.height() * s
                p.drawImage(QRectF(art.center().x() - w / 2, art.center().y() - h / 2, w, h), img)
        else:
            pill = QRectF(art.center().x() - min(art.width(), 230) / 2, art.center().y() - 24, min(art.width(), 230), 48)
            g = QLinearGradient(pill.topLeft(), pill.bottomLeft())
            g.setColorAt(0, QColor("#ff5a66"))
            g.setColorAt(1, QColor("#c20d1e"))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(g))
            p.drawRoundedRect(pill, 24, 24)
            f = T.font(11, QFont.Black, display=True)
            f.setPixelSize(16)
            p.setFont(f)
            p.setPen(QColor("white"))
            p.drawText(pill.adjusted(18, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, "Türkçe")
            k = QRectF(pill.right() - 46, pill.top() + 3, 42, 42)
            p.setBrush(QColor(255, 255, 255, 60))
            p.drawEllipse(k)
            pm = marka_pixmap("rozet.png", 34)
            if not pm.isNull():
                p.drawPixmap(k.adjusted(4, 4, -4, -4).toRect(), pm)
        f = T.font(11, QFont.DemiBold)
        f.setPixelSize(15)
        p.setFont(f)
        p.setPen(QColor(T.A2) if on else QColor(T.TEXT))
        p.drawText(QRectF(r.left(), r.bottom() - 36, r.width(), 28), Qt.AlignCenter, self.name)


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
        f = tv_font(s.get("font", "modern"), tr_px, s.get("bold", True))
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
        c.setAlpha(130)
        sh.setColor(c)
        self.setGraphicsEffect(sh)

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = QRectF(4, 4, 52, 52)
        bot = marka_pixmap("bot.png", 52)              # yardımcının robot yüzü (tools/marka_gorsel.py)
        if not bot.isNull():
            p.drawPixmap(r.toRect(), bot)
            return
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


_SCENE_DEFAULT = {"w": 1720, "h": 980, "tv": [220, 90, 1320, 710], "screen": [228, 98, 1312, 702],
                  "shelf": [110, 750, 1590, 912], "ps5": [1360, 452, 1516, 760], "socket": [1570, 396, 1654, 480],
                  "plug_rest": [1556, 736], "cable_from": [1510, 728]}


def _scene_geo() -> dict:
    import json
    try:
        return json.loads(marka_path("sahne.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(_SCENE_DEFAULT)


def _wrap(fm: QFontMetricsF, text: str, width: float, max_lines: int = 2) -> list[str]:
    lines: list[str] = []
    cur = ""
    for w in text.split():
        t = f"{cur} {w}".strip()
        if cur and fm.horizontalAdvance(t) > width:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = fm.elidedText(lines[-1] + " …", Qt.ElideRight, width)
    return lines or [""]


def draw_live_screen(p: QPainter, screen: QRectF, text: str, english: str = "", live: bool = True,
                     counter: str = "") -> None:
    """Çeviri açıkken TV ekranı (Nino'daki gibi): koyu mor zemin, sol üstte ● CANLI, altta Türkçe altyazı."""
    bg = QLinearGradient(screen.topLeft(), screen.bottomRight())
    bg.setColorAt(0, QColor("#1c1d3d"))
    bg.setColorAt(0.6, QColor("#221a37"))
    bg.setColorAt(1, QColor("#3a1626"))
    p.fillRect(screen, QBrush(bg))
    u = screen.height() / 100.0
    if live:
        f = T.font(9, QFont.Black)
        f.setPixelSize(max(9, int(4.2 * u)))
        f.setLetterSpacing(QFont.AbsoluteSpacing, 0.08 * f.pixelSize())
        fm = QFontMetricsF(f)
        badge = QRectF(screen.left() + 3.5 * u, screen.top() + 3.5 * u, fm.horizontalAdvance("CANLI") + 9.5 * u,
                       fm.height() + 2.6 * u)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(8, 8, 14, 215))
        p.drawRoundedRect(badge, badge.height() / 2, badge.height() / 2)
        p.setBrush(QColor("#ff2d3d"))
        p.drawEllipse(QPointF(badge.left() + badge.height() / 2 + 0.4 * u, badge.center().y()), 1.5 * u, 1.5 * u)
        p.setFont(f)
        p.setPen(QColor("white"))
        p.drawText(badge.adjusted(badge.height() * 0.62 + 2.2 * u, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, "CANLI")
    if counter:
        f = T.font(9, QFont.Black)
        f.setPixelSize(max(10, int(7 * u)))
        p.setFont(f)
        p.setPen(QColor(T.OK))
        p.drawText(screen.adjusted(0, 3 * u, -4 * u, 0), Qt.AlignRight | Qt.AlignTop, counter)
    if text:
        f = T.font(10, QFont.Bold)
        f.setPixelSize(max(11, int(6.4 * u)))
        p.setFont(f)
        fm = QFontMetricsF(f)
        lines = _wrap(fm, text, screen.width() * 0.84)
        lh = fm.height() * 1.08
        y = screen.bottom() - 9 * u - lh * (len(lines) - 1)
        for ln in lines:
            path = QPainterPath()
            path.addText(0, 0, f, ln)
            path.translate(screen.center().x() - fm.horizontalAdvance(ln) / 2, y)
            p.setPen(QPen(QColor(0, 0, 0, 170), max(2.0, 0.9 * u), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
            p.fillPath(path, QColor("white"))
            y += lh
    p.setPen(Qt.NoPen)


def draw_idle_screen(p: QPainter, screen: QRectF, title: str = "GTA6 Altyazı",
                     sub: str = "Oyunlarınız artık Türkçe") -> None:
    """Fiş takılı değilken TV: dalgalı duvar kağıdının (sahnede çizili) üstünde parlayan simge ve ad."""
    u = screen.height() / 100.0
    p.fillRect(screen, QColor(2, 6, 24, 70))
    c = QPointF(screen.center().x(), screen.top() + 40 * u)
    r = 17 * u
    ring = QRadialGradient(c, r * 1.9)
    ring.setColorAt(0.45, QColor(255, 80, 165, 120))
    ring.setColorAt(1, QColor(255, 80, 165, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(ring))
    p.drawEllipse(c, r * 1.9, r * 1.9)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(255, 170, 120, 160), max(1.0, 0.5 * u)))
    p.drawEllipse(c, r * 1.35, r * 1.35)
    p.setPen(Qt.NoPen)
    pm = marka_pixmap("simge_yazisiz.png", max(16, int(r * 2)))
    if not pm.isNull():
        p.drawPixmap(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r).toRect(), pm)
    f = T.font(10, QFont.Black, display=True)
    f.setPixelSize(max(10, int(7.5 * u)))
    p.setFont(f)
    p.setPen(QColor("white"))
    p.drawText(QRectF(screen.left(), c.y() + r * 1.5, screen.width(), 11 * u), Qt.AlignCenter, title)
    f2 = T.font(9, QFont.Medium)
    f2.setPixelSize(max(8, int(3.8 * u)))
    p.setFont(f2)
    p.setPen(QColor(255, 220, 232, 215))
    p.drawText(QRectF(screen.left(), c.y() + r * 1.5 + 10 * u, screen.width(), 7 * u), Qt.AlignCenter, sub)


class PlugScene(QWidget):
    """Nino'nun ana ekranı gibi: duvara asılı TV, metal sehpa, PS5 ve duvarda priz (tools/marka_gorsel.py çizer).
    Fişi prize sürükleyince çeviri başlar, çekince durur: plugged(bool). setRunning() gerçek durumu yansıtır; çeviri
    açıkken TV'nin arkası mavi ışıkla parlar, ekranda ● CANLI ve son Türkçe altyazı görünür."""
    plugged = Signal(bool)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self.running = False
        self.text = ""
        self.counter = ""
        self._drag: QPointF | None = None
        self._plug_pos: QPointF | None = None          # sürüklenirken fişin yeri
        self.hints = True                               # kırmızı halka ve not (Ayarlar'dan kapatılabilir)
        self._G = _scene_geo()
        self._img = marka_image("sahne.png")
        self._light = marka_image("sahne_isik.png")
        self._cache: tuple = (None, None, None)
        self._glow = 0.0
        from PySide6.QtCore import QVariantAnimation
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(650)
        self._anim.valueChanged.connect(self._set_glow)

    def _set_glow(self, v) -> None:  # noqa: ANN001
        self._glow = float(v)
        self.update()

    # ----------------------------------------------------------- geometri
    def _fit(self) -> tuple[float, float, float]:
        W, H = self._G["w"], self._G["h"]
        s = min(self.width() / W, self.height() / H)
        return s, (self.width() - W * s) / 2, (self.height() - H * s) / 2

    def _rect(self, key: str) -> QRectF:
        s, ox, oy = self._fit()
        x0, y0, x1, y1 = self._G[key]
        return QRectF(ox + x0 * s, oy + y0 * s, (x1 - x0) * s, (y1 - y0) * s)

    def _pt(self, key: str) -> QPointF:
        s, ox, oy = self._fit()
        x, y = self._G[key]
        return QPointF(ox + x * s, oy + y * s)

    def _geo(self) -> dict:
        return {"tv": self._rect("tv"), "screen": self._rect("screen"), "shelf": self._rect("shelf"),
                "ps5": self._rect("ps5"), "socket": self._rect("socket"), "rest": self._pt("plug_rest"),
                "cable": self._pt("cable_from")}

    def _plug_at(self) -> QPointF:
        g = self._geo()
        if self._plug_pos is not None:
            return self._plug_pos
        return g["socket"].center() if self.running else g["rest"]

    def setRunning(self, on: bool) -> None:  # noqa: N802
        if on != self.running:
            self._anim.stop()
            self._anim.setStartValue(self._glow)
            self._anim.setEndValue(1.0 if on else 0.0)
            self._anim.start()
        self.running = on
        self._plug_pos = None
        self.update()

    def setText(self, text: str) -> None:  # noqa: N802
        self.text = text
        self.update()

    # ----------------------------------------------------------- fare
    def _near_plug(self, p: QPointF) -> bool:
        s = self._fit()[0]
        return (p - self._plug_at()).manhattanLength() < max(40.0, 120 * s)

    def mousePressEvent(self, e) -> None:  # noqa: ANN001, N802
        p = e.position()
        if self._near_plug(p):
            self._drag = p - self._plug_at()
            self._press = p
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, e) -> None:  # noqa: ANN001, N802
        if self._drag is not None:
            if (e.position() - getattr(self, "_press", e.position())).manhattanLength() < 6:
                return                                   # titreme: tıklama sayılsın
            self._plug_pos = e.position() - self._drag
            self.update()
        else:
            self.setCursor(Qt.OpenHandCursor if self._near_plug(e.position()) else Qt.ArrowCursor)

    def mouseReleaseEvent(self, e) -> None:  # noqa: ANN001, N802
        if self._drag is None:
            return
        self._drag = None
        self.setCursor(Qt.OpenHandCursor)
        g = self._geo()
        if self._plug_pos is None:                       # sürüklemeden tıklandı: tak / çek (Nino: "fişe dokunun")
            self.plugged.emit(not self.running)
            self.update()
            return
        near = (self._plug_pos - g["socket"].center()).manhattanLength() < g["socket"].width() * 1.6
        self._plug_pos = None
        if near != self.running:
            self.plugged.emit(near)
        self.update()

    # ----------------------------------------------------------- çizim
    def _scaled(self, which: str):  # noqa: ANN202
        """Sahne görselleri pencere boyutuna bir kez ölçeklenir (her karede yeniden ölçeklemek yavaş)."""
        from PySide6.QtGui import QPixmap
        key = (self.width(), self.height(), self.devicePixelRatioF())
        if self._cache[0] != key:
            s, _ox, _oy = self._fit()
            dpr = self.devicePixelRatioF()
            out = []
            for img in (self._img, self._light):
                if img.isNull():
                    out.append(QPixmap())
                    continue
                pm = QPixmap.fromImage(img.scaled(int(img.width() * s * dpr), int(img.height() * s * dpr),
                                                  Qt.KeepAspectRatio, Qt.SmoothTransformation))
                pm.setDevicePixelRatio(dpr)
                out.append(pm)
            self._cache = (key, out[0], out[1])
        return self._cache[1] if which == "scene" else self._cache[2]

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        g = self._geo()
        s, ox, oy = self._fit()
        scene = self._scaled("scene")
        if scene.isNull():                      # görsel yoksa (bozuk kurulum) basit çizim
            p.setPen(QPen(QColor(40, 40, 46), 6))
            p.setBrush(QColor(0, 0, 0))
            p.drawRoundedRect(g["tv"], 6, 6)
            p.setBrush(QColor(150, 155, 165))
            p.drawRoundedRect(g["shelf"], 8, 8)
            p.setBrush(QColor(220, 222, 226))
            p.drawRoundedRect(g["socket"], 6, 6)
            p.drawRoundedRect(g["ps5"], 10, 10)
        else:
            if self._glow > 0.01:
                p.setOpacity(self._glow)
                p.drawPixmap(QPointF(ox, oy), self._scaled("light"))
                p.setOpacity(1.0)
            p.drawPixmap(QPointF(ox, oy), scene)
        screen = g["screen"]
        if self.running:
            draw_live_screen(p, screen, self.text or "Çeviri açık: altyazının Türkçesi burada ve TV'de görünür.",
                             counter=self.counter)
        elif not scene.isNull():
            draw_idle_screen(p, screen)
        else:
            f = T.font(10, QFont.Bold)
            f.setPixelSize(max(11, int(screen.height() * 0.06)))
            p.setFont(f)
            p.setPen(QColor(150, 150, 160))
            p.drawText(screen, Qt.AlignCenter, "ÇALIŞTIRMAK İÇİN FİŞİ PRİZE SÜRÜKLE")
        self._draw_plug(p, g, s)
        if self.hints and self._plug_pos is None:
            self._draw_hint(p, g, s)

    def _draw_hint(self, p: QPainter, g: dict, s: float) -> None:
        """Fişin çevresinde kırmızı halka ve kısa not: 'Bu fişe tıklayın ↗' / 'Prizde: çeviri açık ✓'."""
        k = max(0.4, s)
        c = g["socket"].center() if self.running else self._plug_at() + QPointF(0, 6 * k)
        r = (g["socket"].width() * 0.95) if self.running else 46 * k
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 79, 163, 70), 10 * k))
        p.drawEllipse(c, r, r)
        p.setPen(QPen(QColor(T.A1), 3.2 * k))
        p.drawEllipse(c, r, r)
        text = "Prizde: çeviri açık ✓" if self.running else "Bu fişe tıklayın ↗"
        f = T.font(10, QFont.Black)
        f.setPixelSize(max(14, int(26 * k)))
        fm = QFontMetricsF(f)
        w, h = fm.horizontalAdvance(text) + 26 * k, fm.height() + 12 * k
        if self.running:
            box = QRectF(c.x() - w + r * 0.4, c.y() + r + 10 * k, w, h)
        else:
            box = QRectF(c.x() - w - r * 0.6, c.y() + r * 0.6, w, h)
        box.moveLeft(max(4.0, min(box.left(), self.width() - w - 4)))
        box.moveTop(min(box.top(), self.height() - h - 4))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(T.A1))
        p.drawRoundedRect(box, 9 * k, 9 * k)
        p.setFont(f)
        p.setPen(QColor("white"))
        p.drawText(box, Qt.AlignCenter, text)

    def _draw_plug(self, p: QPainter, g: dict, s: float) -> None:
        plug = self._plug_at()
        start = g["cable"]
        inserted = self.running and self._plug_pos is None
        k = max(0.35, s)                                     # fişin ölçeği
        cap_r = g["socket"].width() * 0.40
        end = QPointF(plug.x(), plug.y() + (cap_r * 0.7 if inserted else 30 * k))
        cable = QPainterPath(start)
        if inserted:   # kablo prizden aşağı sarkıp PS5'in arkasına gider (Nino 2. görsel)
            cable.cubicTo(QPointF(start.x() + 40 * k, start.y() + 30 * k),
                          QPointF(end.x() + 10 * k, end.y() + 160 * k), end)
        else:
            cable.cubicTo(QPointF(start.x() + 30 * k, start.y() + 40 * k),
                          QPointF(end.x() - 20 * k, end.y() + 90 * k), end)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(8, 9, 11), max(3.0, 11 * k), Qt.SolidLine, Qt.RoundCap))
        p.drawPath(cable)
        p.setPen(QPen(QColor(255, 255, 255, 40), max(1.0, 3 * k), Qt.SolidLine, Qt.RoundCap))
        p.drawPath(cable.translated(-1.5 * k, -2 * k))
        p.setPen(Qt.NoPen)
        if inserted:
            c = g["socket"].center()
            grad = QRadialGradient(QPointF(c.x() - cap_r * 0.35, c.y() - cap_r * 0.4), cap_r * 1.4)
            grad.setColorAt(0, QColor("#3b3f47"))
            grad.setColorAt(1, QColor("#050607"))
            p.setBrush(QBrush(grad))
            p.drawEllipse(c, cap_r, cap_r)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 50), max(1.0, 2 * k)))
            p.drawEllipse(c, cap_r * 0.78, cap_r * 0.78)
            p.setPen(Qt.NoPen)
            return
        body = QRectF(plug.x() - 22 * k, plug.y() - 8 * k, 44 * k, 42 * k)
        grad = QLinearGradient(body.topLeft(), body.topRight())
        grad.setColorAt(0, QColor("#2d3138"))
        grad.setColorAt(0.5, QColor("#0d0f12"))
        grad.setColorAt(1, QColor("#22252b"))
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(body, 12 * k, 12 * k)
        pin = QLinearGradient(0, plug.y() - 30 * k, 0, plug.y())
        pin.setColorAt(0, QColor("#f2f4f7"))
        pin.setColorAt(1, QColor("#9aa1ab"))
        p.setBrush(QBrush(pin))
        for dx in (-10, 10):
            p.drawRoundedRect(QRectF(plug.x() + dx * k - 3.2 * k, plug.y() - 30 * k, 6.4 * k, 24 * k), 3 * k, 3 * k)
        p.setBrush(QColor(255, 255, 255, 30))
        p.drawRoundedRect(QRectF(body.left() + 5 * k, body.top() + 4 * k, body.width() - 10 * k, 8 * k), 4 * k, 4 * k)


class TvPreview(QWidget):
    """Nino'nun 'düğme' ana ekranı: masada duran TV önizlemesi; çeviri açıkken ● CANLI ve Türkçe altyazı, altında
    İngilizcesi soluk yazıyla."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.running = False
        self.text = ""
        self.english = ""

    def setRunning(self, on: bool) -> None:  # noqa: N802
        self.running = on
        self.update()

    def setText(self, text: str, english: str = "") -> None:  # noqa: N802
        self.text, self.english = text, english
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        foot = 46.0
        th = self.height() - foot - 22
        w = min(self.width() * 0.82, th * 1.68)
        th = w / 1.68
        tv = QRectF((self.width() - w) / 2, 4, w, th)
        # gölge ve ayak
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 90))
        p.drawRoundedRect(tv.adjusted(-2, 10, 2, 14), 26, 26)
        neck = QRectF(tv.center().x() - tv.width() * 0.05, tv.bottom(), tv.width() * 0.1, 14)
        p.setBrush(QColor(25, 27, 34))
        p.drawRect(neck)
        p.setBrush(QColor(30, 33, 42))
        p.drawRoundedRect(QRectF(tv.center().x() - tv.width() * 0.17, neck.bottom() - 2, tv.width() * 0.34, 7), 3, 3)
        frame = QLinearGradient(tv.topLeft(), tv.bottomLeft())
        frame.setColorAt(0, QColor("#2c2f37"))
        frame.setColorAt(1, QColor("#0b0c10"))
        p.setBrush(QBrush(frame))
        p.drawRoundedRect(tv, 24, 24)
        screen = tv.adjusted(9, 9, -9, -9)
        clip = QPainterPath()
        clip.addRoundedRect(screen, 17, 17)
        p.save()
        p.setClipPath(clip)
        if self.running:
            draw_live_screen(p, screen, self.text or "Altyazı bekleniyor…")
        else:
            draw_live_screen(p, screen, "", live=False)
            draw_idle_screen(p, screen)
        p.restore()
        if self.running and self.english:
            f = T.font(10, QFont.Normal)
            f.setItalic(True)
            f.setPixelSize(14)
            p.setFont(f)
            p.setPen(QColor(T.MUTED))
            fm = QFontMetricsF(f)
            p.drawText(QRectF(0, tv.bottom() + 20, self.width(), foot - 18), Qt.AlignHCenter | Qt.AlignTop,
                       fm.elidedText(self.english, Qt.ElideRight, self.width() * 0.8))


class SlideToggle(QWidget):
    """Kırmızı kaydırmalı düğme (Nino): solda 'Türkçe / Altyazı açık', sağda ay yıldızlı top. Topu sürükle ya da
    tıkla: toggled(bool). setOn() gerçek durumu yansıtır."""
    toggled = Signal(bool)

    def __init__(self):
        super().__init__()
        self.setFixedHeight(104)
        self.setMinimumWidth(380)
        self.setMaximumWidth(500)
        self.setCursor(Qt.PointingHandCursor)
        self.on = False
        self._t = 0.0                    # topun yeri: 0 sol, 1 sağ
        self._drag: float | None = None
        self._moved = False
        from PySide6.QtCore import QVariantAnimation
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(220)
        self._anim.valueChanged.connect(self._set_t)
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(46)
        sh.setOffset(0, 8)
        sh.setColor(QColor(0, 0, 0, 0))
        self._shadow = sh
        self.setGraphicsEffect(sh)

    def _set_t(self, v) -> None:  # noqa: ANN001
        self._t = float(v)
        self.update()

    def _animate_to(self, t: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._t)
        self._anim.setEndValue(t)
        self._anim.start()

    def setOn(self, on: bool) -> None:  # noqa: N802
        self.on = on
        if self._drag is None:
            self._animate_to(1.0 if on else 0.0)
        self._shadow.setColor(QColor(255, 79, 163, 150) if on else QColor(0, 0, 0, 90))
        self.update()

    def _pill(self) -> QRectF:
        return QRectF(8, 10, self.width() - 16, self.height() - 26)

    def _knob(self) -> QRectF:
        r = self._pill()
        d = r.height() + 14
        x = r.left() - 4 + (r.width() - d + 8) * self._t
        return QRectF(x, r.center().y() - d / 2, d, d)

    def mousePressEvent(self, e) -> None:  # noqa: ANN001, N802
        self._drag = e.position().x()
        self._moved = False
        self._start_t = self._t

    def mouseMoveEvent(self, e) -> None:  # noqa: ANN001, N802
        if self._drag is None:
            return
        dx = e.position().x() - self._drag
        if abs(dx) > 4:
            self._moved = True
        span = max(1.0, self._pill().width() - self._knob().width())
        self._t = max(0.0, min(1.0, self._start_t + dx / span))
        self.update()

    def mouseReleaseEvent(self, _e) -> None:  # noqa: ANN001, N802
        if self._drag is None:
            return
        self._drag = None
        want = (self._t > 0.5) if self._moved else (not self.on)
        self._animate_to(1.0 if want else 0.0)
        if want != self.on:
            self.toggled.emit(want)

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        r = self._pill()
        t = self._t
        rad = r.height() / 2
        # kapalıyken koyu cam, açıkken parlak kırmızı (top ilerledikçe kızarır)
        off = QLinearGradient(r.topLeft(), r.bottomLeft())
        off.setColorAt(0, QColor(255, 255, 255, 34))
        off.setColorAt(1, QColor(255, 255, 255, 14))
        p.setPen(QPen(QColor(255, 255, 255, 40), 1.2))
        p.setBrush(QBrush(off))
        p.drawRoundedRect(r, rad, rad)
        if t > 0.01:
            p.setOpacity(t)
            red = QLinearGradient(r.topLeft(), r.bottomLeft())
            red = QLinearGradient(r.topLeft(), r.topRight())          # bizim pembe → turuncu
            red.setColorAt(0, QColor("#ff4fa3"))
            red.setColorAt(1, QColor("#ff9f43"))
            p.setPen(QPen(QColor(255, 200, 170, 170), 1.4))
            p.setBrush(QBrush(red))
            p.drawRoundedRect(r, rad, rad)
            gloss = QPainterPath()
            gloss.addRoundedRect(QRectF(r.left() + 14, r.top() + 4, r.width() - 28, r.height() * 0.42), rad * 0.6,
                                 rad * 0.6)
            p.fillPath(gloss, QColor(255, 255, 255, 46))
            p.setOpacity(1.0)
        # yazılar
        f = T.font(14, QFont.Black, display=True)
        f.setPixelSize(30)
        f2 = T.font(10, QFont.DemiBold)
        f2.setPixelSize(14)
        knob = self._knob()
        tx = r.left() + 34 if t >= 0.5 else knob.right() + 18
        p.setPen(QColor("white"))
        p.setFont(f)
        p.drawText(QPointF(tx, r.center().y() + 2), "Türkçe")
        p.setFont(f2)
        p.setPen(QColor(255, 255, 255, 215))
        p.drawText(QPointF(tx + 1, r.center().y() + 22), "Altyazı açık" if self.on else "Altyazı kapalı")
        # top: cam halka + ay yıldızlı rozet
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 40))
        p.drawEllipse(knob)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 120), 1.5))
        p.drawEllipse(knob.adjusted(1, 1, -1, -1))
        p.setPen(Qt.NoPen)
        inner = knob.adjusted(knob.width() * 0.13, knob.height() * 0.13, -knob.width() * 0.13, -knob.height() * 0.13)
        pm = marka_pixmap("rozet.png", int(inner.width()))
        if not pm.isNull():
            p.drawPixmap(inner.toRect(), pm)
        else:
            p.setBrush(QColor("#e3192a"))
            p.drawEllipse(inner)
