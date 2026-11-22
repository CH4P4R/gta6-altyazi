"""Ekrana çizim (PySide6).

OverlayWindow: oyun penceresinin (chiaki-ng / Remote Play) tam üstünde duran, saydam,
tıklamaları alttaki pencereye geçiren katman. İngilizce yazının üstünü kutuyla
kapatıp Türkçesini aynı yere yazar. Discord'da "ekran" paylaşınca bu da yayına girer.

VideoWindow: capture kart görüntüsünü kendi penceresinde gösterir ve Türkçe yazıyı
görüntünün içine çizer. Discord'da sadece bu pencereyi paylaşmak yeterli.
"""

from __future__ import annotations

import sys

import os
import threading

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")  # 1 Qt pikseli = 1 ekran pikseli

import numpy as np  # noqa: E402
from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QTimer, Signal  # noqa: E402
from PySide6.QtGui import (QColor, QFont, QFontMetricsF, QImage, QKeySequence, QPainter,  # noqa: E402
                           QPainterPath, QPen, QShortcut)
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from . import winutil  # noqa: E402
from .pipeline import DisplayItem  # noqa: E402


class Bridge(QObject):
    """İşçi iş parçacıklarından Qt ana iş parçacığına güvenli geçiş."""
    shown = Signal(object)
    cleared = Signal(str)
    frame_ready = Signal()
    overlaid = Signal(object)        # ekran yazıları (telefon, harita kartı, mesaj): ScreenItem.to_json listesi


class QtSink:
    def __init__(self, bridge: Bridge):
        self.bridge = bridge

    def show(self, item: DisplayItem) -> None:
        self.bridge.shown.emit(item)

    def clear(self, zone: str) -> None:
        self.bridge.cleared.emit(zone)


def _wrap(text: str, fm: QFontMetricsF, max_w: float) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and fm.horizontalAdvance(trial) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines or [""]


class Painter:
    def __init__(self, font_family: str, show_latency: bool):
        self.family = font_family
        self.show_latency = show_latency
        self.items: dict[str, DisplayItem] = {}
        self.last: DisplayItem | None = None
        self.overlay: list[dict] = []

    def paint(self, p: QPainter, area: QRectF) -> None:
        p.setRenderHint(QPainter.Antialiasing)
        for ov in list(self.overlay):
            try:
                self._overlay_item(p, area, ov)
            except Exception:  # noqa: BLE001
                pass
        for it in list(self.items.values()):
            self._item(p, area, it)
        if self.show_latency and self.last:
            self._hud(p, area)

    def _item(self, p: QPainter, A: QRectF, it: DisplayItem) -> None:
        x0, y0, x1, y1 = it.rect
        R = QRectF(A.x() + x0 * A.width(), A.y() + y0 * A.height(), (x1 - x0) * A.width(), (y1 - y0) * A.height())
        zx0, _, zx1, _ = it.zone_rect
        zone_w = (zx1 - zx0) * A.width()
        line_px = max(14.0, it.line_h * A.height())
        font = QFont(self.family)
        font.setWeight(QFont.DemiBold)
        font.setPixelSize(int(line_px * 0.92 * it.font_scale))
        fm = QFontMetricsF(font)
        pad = line_px * 0.28
        if it.align == "orta":   # altyazı: bölge genişliğine kadar yayılabilir
            max_w = max(R.width(), zone_w * 0.96)
        else:                    # sol/sağ üst kutular: orijinal kutu genişliğinde kır
            max_w = min(zone_w, max(R.width() * 1.15, line_px * 12))
        lines = _wrap(it.text, fm, max_w - 2 * pad)
        spacing = fm.height() * 1.05
        tw = max(fm.horizontalAdvance(s) for s in lines) + 2 * pad
        th = spacing * len(lines) + 2 * pad - (spacing - fm.height())

        if it.align == "sol":
            bx = R.left() - pad
        elif it.align == "sag":
            bx = R.right() + pad - tw
        else:
            bx = R.center().x() - tw / 2
        if th <= R.height() + 2 * pad:            # Türkçe sığıyorsa İngilizcenin tam ortasına
            by = R.center().y() - th / 2
        else:                                      # sığmıyorsa çapa yönüne doğru büyüsün
            by = (R.bottom() + pad - th) if it.anchor == "alt" else (R.top() - pad)
        text_box = QRectF(bx, by, tw, th)
        cover = text_box.united(R.adjusted(-pad, -pad, pad, pad))   # İngilizce tamamen kapansın

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, it.box_opacity))
        p.drawRoundedRect(cover, pad * 0.8, pad * 0.8)

        outline = QPen(QColor(0, 0, 0, 255), max(2.0, line_px * 0.10))
        outline.setJoinStyle(Qt.RoundJoin)
        y = text_box.top() + pad + fm.ascent()
        for s in lines:
            w = fm.horizontalAdvance(s)
            if it.align == "sol":
                x = text_box.left() + pad
            elif it.align == "sag":
                x = text_box.right() - pad - w
            else:
                x = text_box.center().x() - w / 2
            path = QPainterPath()
            path.addText(QPointF(x, y), font, s)
            p.strokePath(path, outline)
            p.fillPath(path, QColor(255, 255, 255))
            y += spacing

    def _overlay_item(self, p: QPainter, A: QRectF, ov: dict) -> None:
        """Ekran yazısı (TV'deki çizimin bilgisayar karşılığı): sade gölgeli yazı, balon, kart; eğik telefon için açılı."""
        b = ov.get("box") or {}
        R = QRectF(A.x() + b.get("left", 0) * A.width(), A.y() + b.get("top", 0) * A.height(),
                   (b.get("right", 0) - b.get("left", 0)) * A.width(), (b.get("bottom", 0) - b.get("top", 0)) * A.height())
        if R.width() <= 2 or R.height() <= 2:
            return
        p.save()
        angle = float(ov.get("angle") or 0)
        if angle:
            p.translate(R.center())
            p.rotate(angle)
            p.translate(-R.center())
        alpha = float(ov.get("alpha") if ov.get("alpha") is not None else 1.0)
        radius = R.height() * (0.25 if ov.get("side") else 0.12)
        if ov.get("backdrop"):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(12, 12, 16, int(150 * alpha)))
            p.drawRoundedRect(R, 18, 18)
            p.restore()
            return
        line_px = max(12.0, float(ov.get("line") or 0.03) * A.height())
        font = QFont(self.family)
        font.setWeight(QFont.DemiBold)
        font.setItalic(bool(ov.get("italic")))
        font.setPixelSize(int(line_px * 0.9))
        fm = QFontMetricsF(font)
        pad = line_px * 0.3
        plain = bool(ov.get("plain"))
        fill, ink = ov.get("fill"), ov.get("ink")
        if not plain:
            p.setPen(Qt.NoPen)
            if fill:
                c = QColor(fill)
                c.setAlphaF(max(0.0, min(1.0, alpha)))
                p.setBrush(c)
            else:
                p.setBrush(QColor(0, 0, 0, int(200 * (alpha if ov.get("alpha") is not None else 1.0))))
            p.drawRoundedRect(R, radius, radius)
        lines = []
        for para in str(ov.get("text") or "").split("\n"):
            lines += _wrap(para, fm, R.width() - 2 * pad)
        card = bool(ov.get("card"))
        if card:                                   # kart: solda vurgu çizgisi, başlık renkli (Nino'nun kartı gibi)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 79, 163))
            p.drawRect(QRectF(R.left(), R.top() + pad * 0.6, max(3.0, line_px * 0.12), R.height() - pad * 1.2))
            pad *= 1.6
            lines = []
            for para in str(ov.get("text") or "").split("\n"):
                lines += _wrap(para, fm, R.width() - 2 * pad)
        y = R.top() + pad * (0.6 if card else 1) + fm.ascent()
        color = QColor(ink) if ink else QColor(255, 255, 255)
        shadow = QPen(QColor(0, 0, 0, 230), max(2.0, line_px * 0.12))
        shadow.setJoinStyle(Qt.RoundJoin)
        for i, s in enumerate(lines):
            path = QPainterPath()
            path.addText(QPointF(R.left() + pad, y), font, s)
            if plain or not fill:
                p.strokePath(path, shadow)
            p.fillPath(path, QColor(255, 120, 180) if card and i == 0 else color)
            y += fm.height() * 1.05
        p.restore()

    def _hud(self, p: QPainter, A: QRectF) -> None:
        it = self.last
        txt = f"{it.latency_ms:.0f} ms  (OCR {it.ocr_ms:.0f} · {it.source} {it.mt_ms:.0f})"
        font = QFont(self.family)
        font.setPixelSize(max(11, int(A.height() * 0.014)))
        p.setFont(font)
        fm = QFontMetricsF(font)
        r = QRectF(A.right() - fm.horizontalAdvance(txt) - 16, A.top() + 6, fm.horizontalAdvance(txt) + 10,
                   fm.height() + 4)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 140))
        p.drawRect(r)
        p.setPen(QColor(120, 255, 120) if it.latency_ms < 150 else QColor(255, 210, 90))
        p.drawText(r, Qt.AlignCenter, txt)

    # sinyaller
    def on_show(self, it: DisplayItem) -> None:
        self.items[it.zone] = it
        self.last = it

    def on_clear(self, zone: str) -> None:
        self.items.pop(zone, None)


class OverlayWindow(QWidget):
    def __init__(self, painter: Painter, bridge: Bridge, hwnd: int | None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setWindowTitle("GTA6 Altyazi Overlay")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.painter_ = painter
        self.hwnd = hwnd
        bridge.shown.connect(self._show)
        bridge.cleared.connect(self._clear)
        bridge.overlaid.connect(self._overlaid)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._follow)
        self._timer.start(150)
        self._follow()

    def showEvent(self, e) -> None:  # noqa: ANN001, N802
        super().showEvent(e)
        if sys.platform == "darwin":       # tam ekran chiaki'nin üstünde, bütün masaüstlerinde; tıklamayı geçir
            from . import macutil
            macutil.raise_overlay(self)

    def _follow(self) -> None:
        if not self.hwnd:
            self.setGeometry(QApplication.primaryScreen().geometry())
            return
        if winutil.is_minimized(self.hwnd):
            self.hide()
            return
        b = winutil.video_bounds(self.hwnd)       # oyun görüntüsü (başlık çubuğu/siyah bant hariç): kareyle aynı alan
        if b:
            l, t, r, btm = b
            if (self.x(), self.y(), self.width(), self.height()) != (l, t, r - l, btm - t):
                self.setGeometry(l, t, r - l, btm - t)
            if not self.isVisible():
                self.show()

    def _show(self, it: DisplayItem) -> None:
        self.painter_.on_show(it)
        self.update()

    def _clear(self, zone: str) -> None:
        self.painter_.on_clear(zone)
        self.update()

    def _overlaid(self, items: list) -> None:
        self.painter_.overlay = list(items or [])
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        self.painter_.paint(p, QRectF(self.rect()))
        p.end()

    def closeEvent(self, e) -> None:  # noqa: ANN001, N802
        # Kullanıcı bu pencereyi kapatamaz (çerçevesiz, tıklamayı geçirir); kapatma isteği yalnız sistemden gelir
        # (Windows kapanırken, taskkill). Eskiden yalnız katman kapanıyor, program penceresiz açık kalıp port 8787'yi
        # tutuyordu. Sistem kapatmak istiyorsa programın tamamı kapansın.
        super().closeEvent(e)
        if e.spontaneous():
            QApplication.quit()


class VideoWindow(QWidget):
    def __init__(self, painter: Painter, bridge: Bridge, fullscreen: bool = False):
        super().__init__()
        self.setWindowTitle("GTA6 Altyazi")
        self.setStyleSheet("background:black")
        self.resize(1280, 720)
        self.painter_ = painter
        self.bridge = bridge
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._pending = False
        bridge.shown.connect(lambda it: (painter.on_show(it), self.update()))
        bridge.cleared.connect(lambda z: (painter.on_clear(z), self.update()))
        bridge.overlaid.connect(lambda items: (setattr(painter, "overlay", list(items or [])), self.update()))
        bridge.frame_ready.connect(self._on_frame, Qt.QueuedConnection)
        QShortcut(QKeySequence("F11"), self, self._toggle_fs)
        QShortcut(QKeySequence("Esc"), self, self.showNormal)
        if fullscreen:
            self.showFullScreen()

    def _toggle_fs(self) -> None:
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def push_frame(self, frame: np.ndarray, _t: float) -> None:
        """Yakalama iş parçacığından çağrılır. Bekleyen çizim varsa yeni sinyal atılmaz."""
        with self._lock:
            self._frame = frame
            if self._pending:
                return
            self._pending = True
        self.bridge.frame_ready.emit()

    def _on_frame(self) -> None:
        self.repaint()  # hemen çiz (update() bir sonraki olay döngüsünü bekler)

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        with self._lock:
            frame, self._pending = self._frame, False
        p = QPainter(self)
        p.fillRect(self.rect(), Qt.black)
        if frame is not None:
            h, w = frame.shape[:2]
            fmt = QImage.Format_RGB32 if frame.shape[2] == 4 else QImage.Format_BGR888
            img = QImage(frame.data, w, h, frame.strides[0], fmt)
            s = min(self.width() / w, self.height() / h)
            area = QRectF((self.width() - w * s) / 2, (self.height() - h * s) / 2, w * s, h * s)
            p.drawImage(area, img)
            self.painter_.paint(p, area)
        p.end()


class StreamWindow(QWidget):
    """Yayın penceresi (CouchSubs): saydam tarayıcı kaynağı olmayan yayın programları (TikTok LIVE Studio, Streamlabs) için
    düz renkli zemin üstünde Türkçe altyazı. Programda Pencere yakalama ile eklenir, zemin Chroma key ile silinir."""

    def __init__(self, painter: Painter, bridge: Bridge, color: str = "#00ff00"):
        super().__init__()
        self.setWindowTitle("GTA6 Altyazı Yayın")
        self.resize(1280, 720)
        self.color = QColor(color)
        self.painter_ = painter
        bridge.shown.connect(self._show)
        bridge.cleared.connect(self._clear)
        bridge.overlaid.connect(self._overlaid)

    def _show(self, it) -> None:  # noqa: ANN001
        self.painter_.on_show(it)
        self.update()

    def _clear(self, zone: str) -> None:
        self.painter_.on_clear(zone)
        self.update()

    def _overlaid(self, items: list) -> None:
        self.painter_.overlay = list(items or [])
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.fillRect(self.rect(), self.color)
        self.painter_.paint(p, QRectF(self.rect()))
        p.end()
