"""Görüntü üstünde bölgeleri fareyle taşıma/boyutlandırma."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..config import BolgeCfg
from . import theme as T

ZONE_COLORS = ["#ff4fa3", "#ff9f43", "#5cc8ff", "#3ddc97", "#8b5cf6", "#ffd166"]

PRESETS = {
    "Alt orta (altyazı)": ([0.10, 0.76, 0.90, 0.97], "altyazi", "orta", "alt"),
    "Geniş alt bant": ([0.02, 0.70, 0.98, 0.98], "altyazi", "orta", "alt"),
    "Tüm alt yarı": ([0.0, 0.50, 1.0, 1.0], "altyazi", "orta", "alt"),
    "Sol üst (yardım kutusu)": ([0.0, 0.0, 0.36, 0.50], "arayuz", "sol", "ust"),
    "Sağ üst (bildirim)": ([0.64, 0.0, 1.0, 0.32], "arayuz", "sag", "ust"),
    "Üst orta (görev)": ([0.20, 0.0, 0.80, 0.20], "arayuz", "orta", "ust"),
    "Sağ orta (telefon mesajları)": ([0.66, 0.33, 1.0, 0.78], "altyazi", "sag", "ust"),
}

HANDLE = 9


def to_qimage(frame: np.ndarray) -> QImage:
    f = np.ascontiguousarray(frame[..., :3])
    h, w = f.shape[:2]
    return QImage(f.data, w, h, f.strides[0], QImage.Format_BGR888).copy()


class RegionCanvas(QWidget):
    changed = Signal()
    selected = Signal(int)

    def __init__(self):
        super().__init__()
        self.setMinimumSize(520, 300)
        self.setMouseTracking(True)
        self.frame: np.ndarray | None = None
        self.image: QImage | None = None
        self.zones: list[BolgeCfg] = []
        self.sel = 0
        self.show_mask = True
        self._mask_img: QImage | None = None
        self._drag = None   # (mode, index, start_point, start_rect)

    # -------------------------------------------------------------- veri
    def set_frame(self, frame: np.ndarray | None) -> None:
        self.frame = frame
        self.image = to_qimage(frame) if frame is not None else None
        self.refresh_mask()

    def set_zones(self, zones: list[BolgeCfg]) -> None:
        self.zones = zones
        self.sel = min(self.sel, max(0, len(zones) - 1))
        self.refresh_mask()

    def refresh_mask(self) -> None:
        self._mask_img = None
        if self.frame is not None and self.show_mask and self.zones:
            from ..detector import ZoneDetector, zone_rect
            f = self.frame[..., :3]
            h, w = f.shape[:2]
            rgba = np.zeros((h, w, 4), np.uint8)
            for z in self.zones:
                x0, y0, x1, y1 = zone_rect(z, w, h)
                if x1 - x0 < 4 or y1 - y0 < 4:
                    continue
                m = ZoneDetector(z).text_mask(f[y0:y1, x0:x1])
                sub = rgba[y0:y1, x0:x1]
                sub[m] = (40, 40, 255, 230)   # BGRA: kırmızı
            self._mask_img = QImage(rgba.data, w, h, rgba.strides[0], QImage.Format_ARGB32).copy()
        self.update()

    # -------------------------------------------------------------- geometri
    def area(self) -> QRectF:
        W, H = self.width(), self.height()
        ar = 16 / 9 if self.image is None else self.image.width() / self.image.height()
        w = min(W, H * ar)
        h = w / ar
        return QRectF((W - w) / 2, (H - h) / 2, w, h)

    def zrect(self, z: BolgeCfg) -> QRectF:
        A = self.area()
        x0, y0, x1, y1 = z.alan
        return QRectF(A.x() + x0 * A.width(), A.y() + y0 * A.height(), (x1 - x0) * A.width(), (y1 - y0) * A.height())

    def _hit(self, pt: QPointF):  # noqa: ANN202
        order = [self.sel] + [i for i in range(len(self.zones)) if i != self.sel]
        for i in order:
            if i >= len(self.zones):
                continue
            r = self.zrect(self.zones[i])
            for name, c in (("tl", r.topLeft()), ("tr", r.topRight()), ("bl", r.bottomLeft()), ("br", r.bottomRight())):
                if abs(pt.x() - c.x()) <= HANDLE and abs(pt.y() - c.y()) <= HANDLE:
                    return name, i
            if r.contains(pt):
                return "move", i
        return None, None

    # -------------------------------------------------------------- fare
    def mousePressEvent(self, e) -> None:  # noqa: ANN001, N802
        mode, i = self._hit(e.position())
        if i is not None:
            self.sel = i
            self.selected.emit(i)
            self._drag = (mode, i, e.position(), list(self.zones[i].alan))
            self.update()

    def mouseMoveEvent(self, e) -> None:  # noqa: ANN001, N802
        pt = e.position()
        if not self._drag:
            mode, _ = self._hit(pt)
            cur = {"tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor, "tr": Qt.SizeBDiagCursor,
                   "bl": Qt.SizeBDiagCursor, "move": Qt.SizeAllCursor}.get(mode, Qt.ArrowCursor)
            self.setCursor(cur)
            return
        mode, i, start, r0 = self._drag
        A = self.area()
        dx = (pt.x() - start.x()) / A.width()
        dy = (pt.y() - start.y()) / A.height()
        x0, y0, x1, y1 = r0
        if mode == "move":
            w, h = x1 - x0, y1 - y0
            x0 = min(max(0.0, x0 + dx), 1 - w)
            y0 = min(max(0.0, y0 + dy), 1 - h)
            x1, y1 = x0 + w, y0 + h
        else:
            if "l" in mode:
                x0 = min(max(0.0, x0 + dx), x1 - 0.03)
            if "r" in mode:
                x1 = max(min(1.0, x1 + dx), x0 + 0.03)
            if "t" in mode:
                y0 = min(max(0.0, y0 + dy), y1 - 0.03)
            if "b" in mode:
                y1 = max(min(1.0, y1 + dy), y0 + 0.03)
        self.zones[i].alan = [round(v, 4) for v in (x0, y0, x1, y1)]
        self.update()

    def mouseReleaseEvent(self, _e) -> None:  # noqa: ANN001, N802
        if self._drag:
            self._drag = None
            self.refresh_mask()
            self.changed.emit()

    # -------------------------------------------------------------- çizim
    def paintEvent(self, _e) -> None:  # noqa: ANN001, N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        A = self.area()
        p.setPen(Qt.NoPen)
        if self.image is not None:
            p.drawImage(A, self.image)
            if self._mask_img is not None:
                p.drawImage(A, self._mask_img)
        else:
            g = QLinearGradient(A.topLeft(), A.bottomRight())
            g.setColorAt(0, QColor("#2a1640"))
            g.setColorAt(0.6, QColor("#5a2350"))
            g.setColorAt(1, QColor("#ff8a4c"))
            p.setBrush(QBrush(g))
            p.drawRoundedRect(A, 10, 10)
            p.setPen(QColor(255, 255, 255, 170))
            f = T.font(11, QFont.DemiBold)
            p.setFont(f)
            p.drawText(A.adjusted(0, -30, 0, -30), Qt.AlignCenter,
                       "Oyun görüntüsü yok\n\"Görüntü al\" ile oyundan bir kare al (PS5, pencere ya da capture kart)")
        for i, z in enumerate(self.zones):
            c = QColor(ZONE_COLORS[i % len(ZONE_COLORS)])
            r = self.zrect(z)
            fill = QColor(c)
            fill.setAlphaF(0.10 if i != self.sel else 0.16)
            p.setBrush(fill)
            p.setPen(QPen(c, 2.4 if i == self.sel else 1.6, Qt.SolidLine if i == self.sel else Qt.DashLine))
            p.drawRoundedRect(r, 6, 6)
            # etiket
            f = T.font(9, QFont.Bold)
            p.setFont(f)
            tw = p.fontMetrics().horizontalAdvance(z.ad) + 16
            tag = QRectF(r.left(), max(A.top(), r.top() - 24), tw, 20)
            if tag.top() < A.top() + 2:
                tag.moveTop(r.top() + 4)
                tag.moveLeft(r.left() + 4)
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawRoundedRect(tag, 6, 6)
            p.setPen(QColor("#0d0b13"))
            p.drawText(tag, Qt.AlignCenter, z.ad)
            if i == self.sel:
                p.setPen(QPen(QColor("white"), 1.5))
                p.setBrush(c)
                for pt in (r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()):
                    p.drawEllipse(pt, HANDLE * 0.62, HANDLE * 0.62)
