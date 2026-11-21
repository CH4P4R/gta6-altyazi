# SPDX-License-Identifier: AGPL-3.0-only
"""Kare kare gelen OCR çıktısını izleyip altyazının ne zaman çevrileceğine ve silineceğine karar verir.

Nino Game Translator'ın SubtitleStabilizer.swift dosyasından taşındı (core/Sources/CouchSubsCore/SubtitleStabilizer.swift;
Windows: CouchSubs.Core/SubtitleStabilizer.cs). Bölge izi karşılaştırması (`changed`) ve `TextBox`, Nino'nun
ReadScheduler.swift ve Reading.swift dosyalarından gereken kadarıyla alındı.

Altyazı kararlı hale gelince çevrilmesini, ekrandan kalkınca TV'den temizlenmesini ister; aynı altyazıyı tekrar
göndermez. Kararlar okuma hızına değil saate bağlıdır (`clock`: milisaniye; testlerde sahtesi verilir).
`pipeline.worse_reread`'in ve bölge başına "son gönderilen" kontrolünün tam karşılığıdır.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import ClassVar

from . import metin_eslesme, ocr_gurultu
from ._harf import bosluk_satir_kirp


@dataclass(frozen=True)
class StabilizerAction:
    """Okuma hattının bir kareye vereceği tepki: `NONE`, `translate(text)`, `CLEAR` ya da `restore(text)`.

    `restore`: az önce kalkan satır geri geldi; çevirisi yeniden gösterilir, yeniden çevrilmez (metin: ilk gönderilen
    hali).
    """
    kind: str
    text: str = ""

    NONE: ClassVar[StabilizerAction]
    CLEAR: ClassVar[StabilizerAction]

    @staticmethod
    def translate(text: str) -> StabilizerAction:
        return StabilizerAction("translate", text)

    @staticmethod
    def restore(text: str) -> StabilizerAction:
        return StabilizerAction("restore", text)


StabilizerAction.NONE = StabilizerAction("none")
StabilizerAction.CLEAR = StabilizerAction("clear")


@dataclass(frozen=True)
class StabilizerNote:
    """Satırın gönderilmeden bırakıldığı durumlar (yalnız altyazı günlüğü için; kararları değiştirmez).

    `worse_reread`: gönderilen satırın daha kötü (daha az sözcük okuyan) yeniden okuması; yeni satır sayılmadı.
    `garbled_dropped`: çöp gibi okunan satır yeterince kararlı kalmadan ekrandan kalktı ya da değişti; hiç gönderilmedi.
    """
    kind: str
    text: str

    @staticmethod
    def worse_reread(text: str) -> StabilizerNote:
        return StabilizerNote("worse_reread", text)

    @staticmethod
    def garbled_dropped(text: str) -> StabilizerNote:
        return StabilizerNote("garbled_dropped", text)


@dataclass(frozen=True)
class TextBox:
    """Okunan yazının bölgedeki yeri, bölgenin kenarlarına oranla (0–1)."""
    left: float
    top: float
    right: float
    bottom: float


# Bölge izinin boyutu: satır başına bu kadar gri örnek, bu kadar satır (Nino: ReadScheduler.signatureWidth/Height).
SIGNATURE_WIDTH = 64
SIGNATURE_HEIGHT = 12
# Video gürültüsü bu farkı aşmaz; bir harf eklenmesi aşar (Nino: ReadScheduler.defaultChangeThreshold).
DEFAULT_CHANGE_THRESHOLD = 16


def changed(a: Sequence[int], b: Sequence[int], threshold: int, within: TextBox | None = None) -> bool:
    """İki bölge izi farklı mı; `within` verilirse yalnız o kutunun içine bakılır (Nino: ReadScheduler.changed)."""
    if len(a) != len(b):
        return True
    columns = SIGNATURE_WIDTH
    rows = len(a) // columns
    if within is None or rows <= 0 or len(a) % columns != 0:
        return any(abs(int(x) - int(y)) > threshold for x, y in zip(a, b))
    left = min(max(math.floor(within.left * columns), 0), columns - 1)
    right = min(max(math.ceil(within.right * columns), left + 1), columns)
    top = min(max(math.floor(within.top * rows), 0), rows - 1)
    bottom = min(max(math.ceil(within.bottom * rows), top + 1), rows)
    for y in range(top, bottom):
        for x in range(left, right):
            if abs(int(a[y * columns + x]) - int(b[y * columns + x])) > threshold:
                return True
    return False


def uptime_ms() -> int:
    """Uygulamanın saati: tekdüze saatin milisaniyesi."""
    return int(time.monotonic() * 1000)


class SubtitleStabilizer:
    # Bölge bu kadar boş kalırsa altyazı kalkmış sayılır; parlak arka planda kaçan birkaç okuma silmez.
    CLEAR_AFTER_MS = 800
    # Okuma boş döndüğü halde satırın yeri, satır son okunduğundan beri değişmediyse yazı hâlâ oradadır, yazı tanıma
    # kaçırmıştır (parlak zeminde beyaz yazı). Satırın yeri değişince her zamanki `clear_after_ms` sayılır. Değişmeyen
    # yerde de satır en çok bu kadar tutulur.
    HOLD_UNCHANGED_MS = 4000
    # Kalkan satır bu süre içinde geri gelirse aynı satırdır (okuma kaçmıştı); yeniden çevrilmez.
    RESTORE_WITHIN_MS = 1500
    # Çevirisi başarısız olan satır en erken bu kadar sonra yeniden denenir.
    RETRY_AFTER_MS = 1000
    # Çöp gibi okunan satır (`ocr_gurultu.looks_garbled`) ancak bu kadar süre aynı okununca gider. Altyazılar geçişte
    # üst üste solarken yazı tanıma iki satırı karıştırıp birkaç kare aynı çöpü okuyabiliyordu.
    GARBLED_STABLE_MS = 700
    _HISTORY_SIZE = 5

    def __init__(self, similarity: float = 0.85, stable_frames: int = 2, clear_after_ms: int = CLEAR_AFTER_MS,
                 clock: Callable[[], int] = uptime_ms):
        self._similarity = similarity
        self._stable_frames = stable_frames
        self._clear_after_ms = clear_after_ms
        self._now = clock

        self._candidate = ""
        self._candidate_count = 0
        self._candidate_since = 0
        # Ekrandaki (gönderilmiş) satır: sadeleştirilmiş satırlar alt alta, ve ilk okunduğu hali.
        self._sent = ""
        self._sent_raw = ""
        self._empty_since: int | None = None
        # Boş okunan bölgede satırın yerinin değiştiği (ya da yeri bilinmediği için kalkmış sayıldığı) an.
        self._gone_since: int | None = None
        # Ekrandaki satırın son okunduğu karenin bölge izi ve satırın bölgedeki yeri.
        self._last_seen: tuple[Sequence[int], TextBox] | None = None
        # Son kalkan satırlar ve kalktıkları an: (satırlar, ham metin, an).
        self._history: list[tuple[str, str, int]] = []
        # Çevirisi başarısız olan satır ve en erken yeniden deneneceği an.
        self._forgotten = ""
        self._retry_at = 0
        # Bekleyen (henüz gönderilmemiş) çöp gibi okunan aday; gönderilmeden kalkarsa günlüğe yazılır.
        self._garbled_pending = ""
        # Son `feed` çağrısında bırakılan satır (günlük için); her çağrıda sıfırlanır.
        self.note: StabilizerNote | None = None

    def feed(self, raw_text: str, signature: Sequence[int] | None = None,
             box: TextBox | None = None) -> StabilizerAction:
        """Bir karenin okuması. `signature`: karenin bölge izi (64 × 12 gri örnek); verilmezse boş okuma hep kalkma
        sayılır. `box`: okunan yazının bölgedeki yeri."""
        time_ms = self._now()
        text = metin_eslesme.normalize(raw_text)
        self.note = None
        # 3 karakterden kısa okumalar (gürültü, tek simge) boş kare sayılır.
        if len(text) < 3:
            self._drop_garbled()
            self._candidate = ""
            self._candidate_count = 0
            since = self._empty_since if self._empty_since is not None else time_ms
            self._empty_since = since
            if not self._sent:
                return StabilizerAction.NONE
            # Satırın yeri son okunduğu kareden beri değişmediyse yazı tanıma kaçırmıştır; kalkma sayılmaz.
            if self._gone_since is None and not self._looks_unchanged(signature):
                self._gone_since = time_ms
            gone = self._gone_since is not None and time_ms - self._gone_since >= self._clear_after_ms
            if gone or time_ms - since >= self.HOLD_UNCHANGED_MS:
                self._leave_screen(time_ms)
                return StabilizerAction.CLEAR
            return StabilizerAction.NONE

        self._empty_since = None
        self._gone_since = None
        if metin_eslesme.is_similar(text, self._candidate, threshold=self._similarity):
            self._candidate_count += 1
        else:
            self._drop_garbled()
            self._candidate = text
            self._candidate_count = 1
            self._candidate_since = time_ms
        # Daktilo efektinde metin büyürken aday değişir; tamamlanıp kararlı olunca gider. Noktalamayla biten satır zaten
        # tamamdır; ilk karede gider. Çöp gibi okunan satır beklemeden gitmez; geçiş süresinden uzun kararlıysa gider.
        garbled = ocr_gurultu.looks_garbled(raw_text)
        if garbled:
            ready = self._candidate_count >= self._stable_frames \
                and time_ms - self._candidate_since >= self.GARBLED_STABLE_MS
        else:
            ready = self._candidate_count >= self._stable_frames or ends_sentence(raw_text)
        # Gönderilenin gürültülü yeniden okuması yeni satır değildir; TV'de aynı cümle iki kez görünmesin.
        if self._is_same(text, self._sent) or is_prefixed_reread(text, self._sent):
            self._remember(signature, box)
            return StabilizerAction.NONE
        if not ready:
            if garbled:
                self._garbled_pending = bosluk_satir_kirp(raw_text)
            return StabilizerAction.NONE
        self._garbled_pending = ""
        # Aynı cümlenin bir iki sözcüğü başka okunmuş, daha iyi olmayan okuması da yeni satır değildir. Daha çok sözcük
        # okuyan okuma yeniden çevrilir (TV yerine koyar).
        if self._sent_raw and metin_eslesme.is_worse_reread(raw_text, self._sent_raw):
            self.note = StabilizerNote.worse_reread(bosluk_satir_kirp(raw_text))
            self._remember(signature, box)
            return StabilizerAction.NONE

        # Az önce kalkan satır geri geldiyse okuma birkaç kare kaçmıştır: çevirisi yeniden gösterilir, yeniden çevrilmez.
        for index in range(len(self._history) - 1, -1, -1):
            rows, raw, left_at = self._history[index]
            if time_ms - left_at <= self.RESTORE_WITHIN_MS and self._is_same(text, rows):
                del self._history[index]
                self._leave_screen(time_ms)
                self._sent, self._sent_raw = rows, raw
                self._remember(signature, box)
                return StabilizerAction.restore(raw)
        # Çevirisi az önce başarısız olan satır her karede yeniden istenmez.
        if self._forgotten and time_ms < self._retry_at and self._is_same(text, self._forgotten):
            return StabilizerAction.NONE

        self._leave_screen(time_ms)
        self._forgotten = ""
        self._sent_raw = bosluk_satir_kirp(raw_text)
        self._sent = metin_eslesme.normalize_rows(self._sent_raw)
        self._remember(signature, box)
        return StabilizerAction.translate(self._sent_raw)

    def _remember(self, signature: Sequence[int] | None, box: TextBox | None) -> None:
        """Ekrandaki satır bu karede okundu: bölgenin izi ve satırın yeri saklanır (yer bilinmiyorsa hiçbiri)."""
        self._last_seen = (signature, box) if signature is not None and box is not None else None

    def _looks_unchanged(self, signature: Sequence[int] | None) -> bool:
        """Bu karede satırın yeri, satırın son okunduğu karedekiyle aynı mı (izi ve yeri bilinmiyorsa hayır)."""
        if signature is None or self._last_seen is None:
            return False
        seen_signature, seen_box = self._last_seen
        return not changed(seen_signature, signature, DEFAULT_CHANGE_THRESHOLD, within=seen_box)

    def _drop_garbled(self) -> None:
        """Bekleyen çöp aday gönderilmeden bırakıldı (kalktı ya da başka okumaya döndü): günlük için not edilir."""
        if not self._garbled_pending:
            return
        self.note = StabilizerNote.garbled_dropped(self._garbled_pending)
        self._garbled_pending = ""

    @staticmethod
    def _is_same(text: str, rows: str) -> bool:
        """Okuma, bu satırların (gürültülü) yeniden okuması mı; sonuna sözcük eklenmiş hali yenidir."""
        return bool(rows) and metin_eslesme.is_same_subtitle(text, rows)

    def _leave_screen(self, time_ms: int) -> None:
        """Ekrandaki satırı geçmişe yazar (kalktı ya da yerine başkası geldi)."""
        if not self._sent:
            return
        self._history.append((self._sent, self._sent_raw, time_ms))
        if len(self._history) > self._HISTORY_SIZE:
            self._history.pop(0)
        self._sent = ""
        self._sent_raw = ""
        self._last_seen = None

    def should_send(self, source: str, translation: str) -> bool:
        """Çeviri kaynağıyla neredeyse aynıysa metin zaten hedef dildedir (ör. konsolun Türkçe menüleri)."""
        return not metin_eslesme.is_similar(metin_eslesme.normalize(source), metin_eslesme.normalize(translation),
                                            threshold=0.90)

    def forget_sent(self) -> None:
        """Son gönderilen satırı unutur (ör. çevirisi başarısız oldu); satır ekranda kaldıkça yeniden kararlı sayılıp
        çevrilir, ama en erken `RETRY_AFTER_MS` sonra: kalıcı hatada her karede çevirmene gidilmez."""
        if self._sent:
            self._forgotten = self._sent
        self._retry_at = self._now() + self.RETRY_AFTER_MS
        self._sent = ""
        self._sent_raw = ""
        self._last_seen = None
        self._candidate = ""
        self._candidate_count = 0
        self._garbled_pending = ""

    def reset(self) -> StabilizerAction:
        self._candidate = ""
        self._candidate_count = 0
        self._garbled_pending = ""
        self.note = None
        self._empty_since = None
        self._gone_since = None
        self._last_seen = None
        self._history.clear()
        self._forgotten = ""
        if not self._sent:
            return StabilizerAction.NONE
        self._sent = ""
        self._sent_raw = ""
        return StabilizerAction.CLEAR


def is_prefixed_reread(text: str, rows: str) -> bool:
    """Okuma, gönderilen satırın başına önceki satırdan kalan çöp eklenmiş hali mi ("CESADE. TAl CESARE: Told me…" ↔
    "CESARE: Told me…"). Altyazı geçişinde iki okuma kare kare değişince TV'de çeviri 1 satır / 2 satır gidip
    geliyordu; ekrandaki satır korunur (Swift: `SubtitleStabilizer.isPrefixedReread(_:of:)`)."""
    read, shown = metin_eslesme.normalize(text), metin_eslesme.normalize(rows)
    return len(shown) >= 12 and len(read) > len(shown) and read.endswith(shown)


def ends_sentence(raw: str) -> bool:
    """Satır nokta, ünlem, soru ya da üç noktayla bitiyor mu (kapanan tırnak ve parantezler yok sayılır)."""
    text = bosluk_satir_kirp(raw)
    while text and text[-1] in "\"'”’»)]":
        text = text[:-1]
    return bool(text) and text[-1] in ".!?…"


# Swift'te bu ikisi `SubtitleStabilizer`'ın statik yöntemleridir; aynı adlarla sınıftan da çağrılabilsin.
SubtitleStabilizer.is_prefixed_reread = staticmethod(is_prefixed_reread)
SubtitleStabilizer.ends_sentence = staticmethod(ends_sentence)
