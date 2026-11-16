"""Bölge başına metin tespiti ve değişim algılama.

Her karede yapılan iş çok ucuzdur (~1 ms): bölgedeki "metin pikselleri" maskesi
çıkarılır ve küçültülmüş hali bir önceki ile karşılaştırılır. OCR sadece metin
değiştiğinde çalışır. Böylece 60 fps'de bile işlemci boşta kalır ve yeni bir
altyazı çıktığı ilk karede OCR'a gönderilir.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from .config import BolgeCfg


@dataclass
class TextLine:
    image: np.ndarray                 # OCR'a gidecek görüntü (beyaz zemin, koyu yazı)
    box: tuple[int, int, int, int]    # bölge içi piksel (x0, y0, x1, y1)


@dataclass
class ZoneEvent:
    kind: str                                   # "text" | "clear"
    lines: list[TextLine] = field(default_factory=list)
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)
    line_height: float = 0.0


def zone_rect(cfg: BolgeCfg, w: int, h: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = cfg.alan
    return int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)


class ZoneDetector:
    def __init__(self, cfg: BolgeCfg):
        self.cfg = cfg
        r = max(1, cfg.cerceve_yaricap)
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
        self.shown_sig: np.ndarray | None = None
        self.cand_sig: np.ndarray | None = None
        self.cand_count = 0
        self.empty_since: float | None = None
        self._quick: np.ndarray | None = None

    # ------------------------------------------------------------------ maske
    def _seed(self, crop: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(metin adayı pikseller, koyu konturun dibindeki metin pikselleri) - ucuz kısım."""
        c = self.cfg
        b, g, r = cv2.split(crop[..., :3])
        mn = cv2.min(cv2.min(b, g), r)
        mx = cv2.max(cv2.max(b, g), r)
        spread = cv2.subtract(mx, mn)
        text = (mn >= c.beyaz_min) & (spread <= c.doygunluk_max)
        if c.renkli:
            text |= (mx >= c.renk_min) & (spread >= c.renk_fark_min)
        text_u8 = text.astype(np.uint8)
        if not c.cerceve:
            return text_u8, text
        dark = (mx <= c.koyu_max).astype(np.uint8)
        near_dark = cv2.dilate(dark, self._kernel)
        return text_u8, (text_u8 & near_dark).astype(bool)

    def text_mask(self, crop: np.ndarray, pre: tuple[np.ndarray, np.ndarray] | None = None) -> np.ndarray:
        text_u8, seed = pre if pre is not None else self._seed(crop)
        if not self.cfg.cerceve:
            return seed
        if not seed.any():
            return seed
        n, labels, stats, _ = cv2.connectedComponentsWithStats(text_u8, connectivity=8)
        w, h, area = stats[:, cv2.CC_STAT_WIDTH], stats[:, cv2.CC_STAT_HEIGHT], stats[:, cv2.CC_STAT_AREA]
        # Yazı harflerinin neredeyse tamamı koyu konturun dibindedir; parlak arka plan
        # lekelerinin ise sadece kenarı koyu bir şeye değer.
        near = np.bincount(labels[seed], minlength=n)
        keep = near >= 0.6 * np.maximum(area, 1)
        keep[0] = False
        # Büyük ve dolu lekeler (gökyüzü parçası, lamba) ve tek piksellik kırıntılar metin değildir
        zh = crop.shape[0]
        blob = (h > 0.5 * zh) | ((w > 40) & (h > 40) & (area > 0.8 * w * h)) | (area < 6)
        keep &= ~blob
        return keep[labels]

    @staticmethod
    def signature(mask: np.ndarray) -> np.ndarray:
        h, w = mask.shape
        small = cv2.resize(mask.astype(np.uint8) * 255, (max(1, w // 4), max(1, h // 4)),
                           interpolation=cv2.INTER_AREA)
        return small > 64

    @staticmethod
    def difference(a: np.ndarray, b: np.ndarray) -> float:
        union = np.count_nonzero(a | b)
        if union == 0:
            return 0.0
        return np.count_nonzero(a ^ b) / union

    # ------------------------------------------------------------- satırlar
    def split_lines(self, mask: np.ndarray) -> tuple[list[TextLine], tuple[int, int, int, int], float]:
        rows = np.flatnonzero(mask.sum(axis=1) > 0)
        if rows.size == 0:
            return [], (0, 0, 0, 0), 0.0
        # ardışık satır gruplarını bul
        runs: list[list[int]] = []
        start = prev = rows[0]
        for y in rows[1:]:
            if y != prev + 1:
                runs.append([start, prev + 1])
                start = y
            prev = y
        runs.append([start, prev + 1])
        # i noktası, aksan gibi küçük boşlukları birleştir
        merged = [runs[0]]
        for y0, y1 in runs[1:]:
            py0, py1 = merged[-1]
            gap = y0 - py1
            if gap <= max(2, int(0.15 * max(py1 - py0, y1 - y0))):
                merged[-1][1] = y1
            else:
                merged.append([y0, y1])
        merged = [r for r in merged if r[1] - r[0] >= self.cfg.min_satir_yuksekligi]
        if not merged:
            return [], (0, 0, 0, 0), 0.0

        lines: list[TextLine] = []
        heights = []
        H, W = mask.shape
        for y0, y1 in merged:
            lh = y1 - y0
            heights.append(lh)
            cols = np.flatnonzero(mask[y0:y1].any(axis=0))
            # aynı satırda birbirinden uzak metinleri ayrı parça yap (ör. ikon + yazı, iki sütun)
            seg_start = cols[0]
            prevx = cols[0]
            segs = []
            for x in cols[1:]:
                if x - prevx > 1.8 * lh:
                    segs.append((seg_start, prevx + 1))
                    seg_start = x
                prevx = x
            segs.append((seg_start, prevx + 1))
            for x0, x1 in segs:
                if x1 - x0 < lh * 0.6:      # tek başına küçük leke (ikon kırıntısı)
                    continue
                pad = max(2, lh // 4)
                bx0, by0 = max(0, x0 - pad), max(0, y0 - pad)
                bx1, by1 = min(W, x1 + pad), min(H, y1 + pad)
                sub = mask[by0:by1, bx0:bx1]
                img = np.where(sub, 0, 255).astype(np.uint8)
                lines.append(TextLine(img, (bx0, by0, bx1, by1)))
        if not lines:
            return [], (0, 0, 0, 0), 0.0
        bbox = (min(l.box[0] for l in lines), min(l.box[1] for l in lines),
                max(l.box[2] for l in lines), max(l.box[3] for l in lines))
        return lines, bbox, float(np.median(heights))

    # ------------------------------------------------------------ durum makinesi
    def process(self, crop: np.ndarray, now: float) -> ZoneEvent | None:
        c = self.cfg
        pre = self._seed(crop)
        # Hızlı yol: hiçbir şey beklemiyorsak ve kare öncekiyle aynıysa ağır analizi atla
        quick = self.signature(pre[1])
        idle = self.cand_sig is None and self.empty_since is None
        same = self._quick is not None and self.difference(quick, self._quick) < 0.04
        if idle and same:
            return None
        self._quick = quick  # son tam analizdeki hali; yavaş kaymalar da birikip yakalanır
        mask = self.text_mask(crop, pre)
        if np.count_nonzero(mask) < c.min_piksel:
            self.cand_sig, self.cand_count = None, 0
            if self.shown_sig is not None:
                if self.empty_since is None:
                    self.empty_since = now
                if (now - self.empty_since) * 1000 >= c.silme_ms:
                    self.shown_sig = None
                    self.empty_since = None
                    return ZoneEvent("clear")
            return None
        self.empty_since = None
        sig = self.signature(mask)
        if self.shown_sig is not None and self.difference(sig, self.shown_sig) < c.degisim_esigi:
            return None
        if self.cand_sig is not None and self.difference(sig, self.cand_sig) < c.degisim_esigi:
            self.cand_count += 1
        else:
            self.cand_sig, self.cand_count = sig, 1
        if self.cand_count <= c.sabit_kare:
            return None
        self.shown_sig = sig
        self.cand_sig, self.cand_count = None, 0
        lines, bbox, lh = self.split_lines(mask)
        if not lines:
            return None
        return ZoneEvent("text", lines, bbox, lh)

    def reject(self) -> None:
        """OCR sonucu güvenilmezdi: bir sonraki karede tekrar denensin."""
        self.shown_sig = None
        self._quick = None
