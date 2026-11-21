# SPDX-License-Identifier: AGPL-3.0-only
"""Yerel çeviri motorunun (OPUS-MT) etrafındaki kalite zinciri: Nino Game Translator'ın FreeTranslation.swift /
FreeLineTranslator mantığı (çağrı sırası: README_entegrasyon.py, A bölümü).

Satır parçalara bölünür (konuşan etiketi ve tireler çeviriye gitmez); kısa parça (1-3 sözcük) önceki cümleyle birlikte
" *** " ayracıyla çevrilir (bağlam). Her cümlede sırayla: hazır satır (sözlük) → büyük/küçük harf düzeni → sözlük
sadeleştirmesi → argo → oyun İngilizcesi → terim koruma (uydurma adla) → motor → terimleri Türkçe ekiyle geri koyma →
biçim düzeltmesi. Satırın tamamında sen/siz emir uyumu.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Callable

from . import bolucu, oyun_ingilizce, son_duzelti
from .sozluk import Glossary
from .terim import TermProtector

log = logging.getLogger(__name__)

SEPARATOR = " *** "
_LETTER = re.compile(r"[^\W\d_]")


def _utf16(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def after_separator(output: str, source: str) -> str | None:
    """Bağlamlı çıktının ayraçtan sonrası (Nino: afterSeparator); güvenilmezse None."""
    if output.count("***") != 1:
        return None
    before, after = output.split("***", 1)
    after = after.strip()
    if after.startswith("*") or before.rstrip().endswith("*"):
        return None
    if not _LETTER.search(before) or not _LETTER.search(after):
        return None
    if _utf16(after) > 3 * _utf16(source) + 20:
        return None
    return after


def _short(text: str) -> bool:
    words = [w for w in text.split() if _LETTER.search(w)]
    return 1 <= len(words) <= 3


class QualityLocal:
    """translate(satır) -> Türkçe. `engine(metin) -> Türkçe` ham OPUS-MT çağrısıdır."""

    RECENT_MS = 20000

    def __init__(self, engine: Callable[[str], str], glossary: Glossary,
                 slang: Callable[[str], str] | None = None):
        self.engine = engine
        self.glossary = glossary
        self.slang = slang
        self.names = bolucu.SpeakerNames()
        self._recent: tuple[str, float] | None = None       # önceki satırın son cümlesi ve zamanı
        self._lock = threading.Lock()

    @classmethod
    def build(cls, engine: Callable[[str], str], sozluk: dict[str, str], keep: list[str],
              user_dir=None, slang: Callable[[str], str] | None = None) -> QualityLocal:  # noqa: ANN001
        parts = [Glossary.built_in(), Glossary.from_dict({"terms": dict(sozluk), "keep": list(keep)})]
        if user_dir is not None:
            try:
                parts.append(Glossary.load(user_dir))
            except Exception as e:  # noqa: BLE001
                log.warning("Kullanıcı sözlüğü okunamadı: %s", e)
        return cls(engine, Glossary.merge(parts), slang)

    # ------------------------------------------------------------------ satır
    def translate(self, line: str) -> str:
        pieces = bolucu.split(line)
        with self._lock:
            self.names.learn(pieces)
            recent = self._recent
        prev = recent[0] if recent and (time.monotonic() * 1000 - recent[1]) < self.RECENT_MS else None
        outs: list[str | None] = []
        idx: list[int] = []
        for i, p in enumerate(pieces):
            if not p.translate:
                outs.append(p.text)
                continue
            context = prev if _short(p.text) else None
            try:
                outs.append(self.sentence(p.text, context))
            except Exception:  # noqa: BLE001
                log.exception("Yerel çeviri zinciri")
                outs.append(None)
            idx.append(i)
            prev = p.text
        fixed = son_duzelti.register([outs[i] for i in idx])
        for i, f in zip(idx, fixed):
            outs[i] = f
        last = next((pieces[i].text for i in reversed(idx)), None)
        if last:
            with self._lock:
                self._recent = (last, time.monotonic() * 1000)
        return "".join(o if o is not None else pieces[k].text for k, o in enumerate(outs)).strip()

    # ------------------------------------------------------------------ cümle
    def _prepare(self, text: str) -> str:
        t = bolucu.normalize_case(text, names=self.names.all | set(self.glossary.capital_words))
        t = self.glossary.plain(t)
        if self.slang is not None:
            t = self.slang(t)
        return oyun_ingilizce.plain(t)

    def sentence(self, sentence: str, context: str | None = None) -> str:
        ready = self.glossary.line(sentence)
        if ready:
            return son_duzelti.apply(sentence, ready)
        apostrophe = son_duzelti.apostrophe(sentence)
        if context:
            guard = TermProtector(self.glossary, [sentence, context])
            ctx_masked = guard.protect(self._prepare(context))[0]
            masked, slots = guard.protect(self._prepare(sentence))
            after = after_separator(self.engine(ctx_masked + SEPARATOR + masked), sentence)
            back = TermProtector.restore(after, slots, guard.all_slots, apostrophe) if after else None
            if back:
                return son_duzelti.apply(sentence, back)
        guard = TermProtector(self.glossary, [sentence])
        masked, used = guard.protect(self._prepare(sentence))
        out = self.engine(masked)
        if not used:
            return son_duzelti.apply(sentence, out)
        back = TermProtector.restore(out, used, guard.all_slots, apostrophe)
        if back:
            return son_duzelti.apply(sentence, back)
        return son_duzelti.apply(sentence, self.engine(self._prepare(sentence)))     # yer tutucu düştü
