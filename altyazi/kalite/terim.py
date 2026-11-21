# SPDX-License-Identifier: AGPL-3.0-only
"""Sözlük terimlerini yerel çeviriden korur.

Nino Game Translator'ın TermProtection.swift dosyasından taşındı (core/Sources/CouchSubsCore/TermProtection.swift;
Windows: CouchSubs.Core/TermProtection.cs, aynı kurallar). `altyazi/terms.py`'nin yerini alabilecek tam sürümdür:
sözlük (`sozluk.Glossary`) tam sözcük ve uzun-terim-önce eşleşir, ek kuralları `ek.attach`'tadır, cümle başındaki cins
ad büyük harfle başlar, başka parçanın yer tutucusu çıktıya sızarsa sonuç güvenilmez sayılır.

Terim, çeviri öncesinde uydurma bir özel adla ("Zarmon", "Velkor") değiştirilir. Neden ad: OPUS-MT özel adı olduğu
gibi bırakıp Türkçe ekini kesmeyle ekler ("Zarmon'u al"); "[[1]]", "__T1__" gibi işaretleri ise model sözlüğünde
olmadığı için düşürebilir ya da bozabilir. Çeviriden sonra ad, büyük/küçük harf, boşluk ve kesme farkına bakılmadan
bulunur, yerine Türkçe terim konur ve ek terime göre yeniden kurulur. Bir ad çeviride yoksa sonuç güvenilmez sayılır
(None), çağıran korumasız çeviriye döner.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache

from . import ek
from ._harf import sinif, tr_buyuk
from .sozluk import Glossary

# Yer tutucu adlar: Türkçe ve İngilizcede sözcük değil, birbirinin başı değil, i/I içermez (Türkçe büyük/küçük harf
# dönüşümü bozmasın), ünsüzle biter (yumuşamaz) ve kalın ünlülüdür.
PLACEHOLDERS = ("Zarmon", "Velkor", "Dorvan", "Kelmar", "Tolvar", "Brandur", "Halvor", "Feldor")


@dataclass(frozen=True)
class Slot:
    """Korunan terim: yer tutucusu ve yerine konacak Türkçe."""
    placeholder: str
    english: str
    turkish: str


class TermProtector:
    """Bir cümle (ve bağlamı) için yer tutucu dağıtıcı; aynı terim aynı adı alır."""

    def __init__(self, glossary: Glossary, sources: Iterable[str]):
        """`sources`: kaynak metinler; içlerinde geçen yer tutucu ad kullanılmaz."""
        sources = list(sources)
        self._glossary = glossary
        self._free = [name for name in PLACEHOLDERS
                      if not any(re.search(re.escape(name), s, re.IGNORECASE) for s in sources)]
        self._by_term: dict[str, Slot] = {}
        self._order: list[Slot] = []

    @property
    def all_slots(self) -> list[Slot]:
        """Bütün yer tutucular (bağlamdakiler dahil); çıktıda beklenmeyen ad kalmasın diye."""
        return list(self._order)

    def protect(self, text: str) -> tuple[str, list[Slot]]:
        """Terimleri yer tutucularla değiştirir; bu metinde kullanılan yer tutucular döner."""
        matches = self._glossary.find(text)
        if not matches:
            return text, []
        output = ""
        used: list[Slot] = []
        position = 0
        for match in matches:
            key = match.english.lower()
            slot = self._by_term.get(key)
            if slot is None:
                # Ad kalmadıysa geri kalan terimler korunmaz; model onları kendi çevirir.
                if not self._free:
                    continue
                slot = Slot(self._free.pop(0), match.english, match.turkish)
                self._by_term[key] = slot
                self._order.append(slot)
            output += text[position:match.start] + slot.placeholder
            position = match.start + match.length
            if slot not in used:
                used.append(slot)
        output += text[position:]
        return output, used

    @staticmethod
    def restore(output: str, expected: Sequence[Slot], all_slots: Sequence[Slot] = (),
                apostrophe: str = "'") -> str | None:
        """Yer tutucuları Türkçe terimle değiştirir. `expected` çıktıda en az bir kez geçmeli, `all_slots` içindeki
        diğer adlar hiç geçmemeli; yoksa None."""
        if not expected and not all_slots:
            return output
        for slot in all_slots:
            if slot not in expected and _pattern(slot.placeholder).search(output):
                return None
        text = output
        for slot in expected:
            found = list(_pattern(slot.placeholder).finditer(text))
            if not found:
                return None
            result = text
            for match in reversed(found):
                suffix = match.group(1) if match.group(1) is not None else (match.group(2) or "")
                term = ek.attach(slot.turkish, suffix, apostrophe)
                if _starts_sentence(text, match.start()):
                    term = _capitalize(term)
                result = result[:match.start()] + term + result[match.end():]
            text = result
        return text


@lru_cache(maxsize=None)
def _pattern(placeholder: str) -> re.Pattern:
    """Yer tutucu ve ardındaki ek: kesmeyle ("Zarmon'a", "Zarmon 'a") ya da bitişik ("Zarmona")."""
    letter, letter_or_number = sinif("L"), sinif("L", "N")
    return re.compile(
        "(?<![" + letter_or_number + "])" + placeholder
        + r"(?:\s?['’`´]([" + letter + "]+)|([" + letter + "]+))?(?![" + letter_or_number + "])",
        re.IGNORECASE,
    )


def _starts_sentence(text: str, index: int) -> bool:
    """Metnin ya da cümlenin başı mı (önünde yalnız boşluk, tırnak, tire ya da cümle sonu var)."""
    i = index - 1
    while i >= 0:
        character = text[i]
        if character.isspace() or character in "\"“'‘(-–—¡¿":
            i -= 1
            continue
        return character in ".!?…"
    return True


def _capitalize(term: str) -> str:
    if not term or not term[0].islower():
        return term
    return tr_buyuk(term[0]) + term[1:]
