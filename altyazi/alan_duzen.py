# SPDX-License-Identifier: AGPL-3.0-only
"""Okuma alanlarını oyun görüntüsünün üstünde fareyle düzenleme (bilgisayar katmanı ve capture kart penceresi).

Düzenleme açılınca (kısayol Ctrl+Shift+5 ya da Okuma alanı sayfasındaki "Ekranda düzenle") her alan oyun görüntüsünün
üstünde adıyla çerçeve olarak görünür:
  - içinden sürükle: taşı,  kenarından / köşesinden sürükle: boyutlandır,
  - sağ tık: aç / kapat ya da sil (ana altyazı alanı silinmez),  boş yere sağ tık: oraya yeni alan ekle,
  - Enter: kaydet,  Esc: vazgeç.
Koordinatlar ayarlardaki gibi görüntünün oranıdır (0-1). Çizim ve geometri Qt'den bağımsız tutuldu (test edilebilir).
"""

from __future__ import annotations

from dataclasses import dataclass, field

MIN_W, MIN_H = 0.03, 0.025          # en küçük alan (görüntü oranı)
HANDLE_PX = 9                       # kenar/köşe yakalama payı (piksel)
NEW_W, NEW_H = 0.30, 0.10           # sağ tıkla eklenen alanın boyu


@dataclass
class Region:
    ad: str
    alan: list[float]               # [x0, y0, x1, y1]
    aktif: bool = True
    main: bool = False              # ana altyazı alanı (silinmez)


@dataclass
class RegionEdit:
    """Alanların düzenleme durumu. `width`/`height`: görüntünün çizildiği alanın piksel boyu (yakalama payı için)."""

    regions: list[Region]
    width: float = 1920
    height: float = 1080
    selected: int | None = None
    _drag: tuple[int, str, float, float, list[float]] | None = field(default=None, repr=False)

    @classmethod
    def from_config(cls, bolgeler) -> "RegionEdit":  # noqa: ANN001
        regs = [Region(b.ad, [float(v) for v in b.alan], bool(getattr(b, "aktif", True)), i == 0)
                for i, b in enumerate(bolgeler)]
        return cls(regs)

    # ------------------------------------------------------------------ yakalama
    def hit(self, x: float, y: float) -> tuple[int, str] | None:
        """(alan sırası, yer): yer 'move' ya da kenar/köşe adı ('l', 'r', 't', 'b', 'tl', 'tr', 'bl', 'br')."""
        px, py = HANDLE_PX / max(1.0, self.width), HANDLE_PX / max(1.0, self.height)
        order = ([self.selected] if self.selected is not None else []) + \
            [i for i in reversed(range(len(self.regions))) if i != self.selected]
        for i in order:
            x0, y0, x1, y1 = self.regions[i].alan
            if not (x0 - px <= x <= x1 + px and y0 - py <= y <= y1 + py):
                continue
            edge = ""
            if abs(y - y0) <= py:
                edge += "t"
            elif abs(y - y1) <= py:
                edge += "b"
            if abs(x - x0) <= px:
                edge += "l"
            elif abs(x - x1) <= px:
                edge += "r"
            return i, edge or "move"
        return None

    def press(self, x: float, y: float) -> bool:
        h = self.hit(x, y)
        if h is None:
            self.selected = None
            return False
        i, part = h
        self.selected = i
        self._drag = (i, part, x, y, list(self.regions[i].alan))
        return True

    def move(self, x: float, y: float) -> bool:
        if self._drag is None:
            return False
        i, part, sx, sy, (x0, y0, x1, y1) = self._drag
        dx, dy = x - sx, y - sy
        if part == "move":
            w, h = x1 - x0, y1 - y0
            nx0 = min(max(0.0, x0 + dx), 1.0 - w)
            ny0 = min(max(0.0, y0 + dy), 1.0 - h)
            self.regions[i].alan = [nx0, ny0, nx0 + w, ny0 + h]
            return True
        if "l" in part:
            x0 = min(max(0.0, x0 + dx), x1 - MIN_W)
        if "r" in part:
            x1 = max(min(1.0, x1 + dx), x0 + MIN_W)
        if "t" in part:
            y0 = min(max(0.0, y0 + dy), y1 - MIN_H)
        if "b" in part:
            y1 = max(min(1.0, y1 + dy), y0 + MIN_H)
        self.regions[i].alan = [x0, y0, x1, y1]
        return True

    def release(self) -> None:
        self._drag = None

    # ------------------------------------------------------------------ sağ tık işleri
    def toggle(self, i: int) -> None:
        self.regions[i].aktif = not self.regions[i].aktif

    def remove(self, i: int) -> bool:
        if self.regions[i].main:
            return False
        del self.regions[i]
        self.selected = None
        return True

    def add(self, x: float, y: float) -> int:
        x0 = min(max(0.0, x - NEW_W / 2), 1.0 - NEW_W)
        y0 = min(max(0.0, y - NEW_H / 2), 1.0 - NEW_H)
        names = {r.ad for r in self.regions}
        n = 1
        while f"ek{n}" in names:
            n += 1
        self.regions.append(Region(f"ek{n}", [x0, y0, x0 + NEW_W, y0 + NEW_H]))
        self.selected = len(self.regions) - 1
        return self.selected

    # ------------------------------------------------------------------ ayara geri yazma
    def apply_to(self, bolgeler: list) -> list:  # noqa: ANN001
        """Düzenlenen alanları ayar listesine yazar: var olanların yeri ve açık/kapalı durumu güncellenir, silinenler
        çıkar, yeniler ek alan (arayüz yazısı) olarak eklenir. Okuma ayarları (renk eşikleri vb.) korunur."""
        from .config import BolgeCfg
        by_name = {b.ad: b for b in bolgeler}
        out = []
        for r in self.regions:
            b = by_name.get(r.ad)
            if b is None:
                b = BolgeCfg(ad=r.ad, tur="arayuz", hizalama="sol", capa="ust")
            b.alan = [round(v, 4) for v in r.alan]
            b.aktif = r.aktif
            out.append(b)
        return out


HELP = ("Alanları düzenle · sürükle: taşı · kenar/köşe: boyut · sağ tık: aç/kapat/sil · boş yere sağ tık: yeni alan "
        "· Enter: kaydet · Esc: vazgeç")


def paint(p, area, edit: RegionEdit) -> None:  # noqa: ANN001
    """Düzenleme katmanını çizer (Qt QPainter, QRectF alan)."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QPen

    edit.width, edit.height = area.width(), area.height()
    p.fillRect(area, QColor(10, 4, 20, 70))
    f = QFont()
    f.setPixelSize(max(12, int(area.height() * 0.018)))
    f.setBold(True)
    p.setFont(f)
    for i, r in enumerate(edit.regions):
        x0, y0, x1, y1 = r.alan
        rect = QRectF(area.left() + x0 * area.width(), area.top() + y0 * area.height(),
                      (x1 - x0) * area.width(), (y1 - y0) * area.height())
        col = QColor("#ff4fa3") if r.main else QColor("#ff9f43")
        if not r.aktif:
            col = QColor(150, 150, 160)
        fill = QColor(col)
        fill.setAlpha(60 if i == edit.selected else 30)
        p.fillRect(rect, fill)
        pen = QPen(col, 3 if i == edit.selected else 2)
        if not r.aktif:
            pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.drawRect(rect)
        label = ("Altyazı" if r.main else r.ad) + ("" if r.aktif else " (kapalı)")
        p.fillRect(QRectF(rect.left(), rect.top() - f.pixelSize() * 1.6, len(label) * f.pixelSize() * 0.62 + 14,
                          f.pixelSize() * 1.6), col)
        p.setPen(QColor("#1c0b2b"))
        p.drawText(QRectF(rect.left() + 7, rect.top() - f.pixelSize() * 1.6, 2000, f.pixelSize() * 1.6),
                   Qt.AlignVCenter | Qt.AlignLeft, label)
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        s = 8
        for hx, hy in ((rect.left(), rect.top()), (rect.right(), rect.top()), (rect.left(), rect.bottom()),
                       (rect.right(), rect.bottom())):
            p.drawRect(QRectF(hx - s / 2, hy - s / 2, s, s))
        p.setBrush(Qt.NoBrush)
    bar = QRectF(area.left(), area.top(), area.width(), f.pixelSize() * 2.4)
    p.fillRect(bar, QColor(31, 12, 51, 230))
    p.setPen(QColor("#ffffff"))
    p.drawText(bar, Qt.AlignCenter, HELP)
