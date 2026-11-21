# SPDX-License-Identifier: AGPL-3.0-only
"""Altyazının başındaki konuşan adı ("ARTHUR: We need to go.", "Dutch：Easy.").

Nino Game Translator'ın SpeakerPrefix.swift dosyasından taşındı (core/Sources/CouchSubsCore/SpeakerPrefix.swift;
Android SpeakerPrefix.kt ve Windows SpeakerPrefix.cs aynı kuralları uygular).

Ad çeviriye gitmez: motorlar adı çeviriyor ya da cümlenin içine katıyordu, paket anahtarı da çoğu zaman adsız
tutuluyor. Hat önce adlı satırı, sonra adsız cümleyi pakette arar; motora yalnız cümle gider, ad gösterirken geri
eklenir ya da (ayar kapalıysa) atılır.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Sequence
from dataclasses import dataclass

from ._harf import bosluk_satir_kirp, harf_var, sinif
from .bolucu import NOT_NAMES


@dataclass(frozen=True)
class Split:
    name: str
    body: str


@dataclass(frozen=True)
class SpokenLine:
    """Seslendirilecek bir cümle (Nino'nun Dubbing/SpeechScript.swift'indeki `SpokenLine`; `voiced` için gereken kadarı).

    `speaker`: altyazıdaki konuşmacı etiketi ("KRATOS: " → "KRATOS"), yoksa None. `new_turn`: diyalog tiresiyle başlayan
    yeni konuşma ("- Gidelim. - Bekle!"): etiketsiz satırlarda konuşan değişti demektir.
    """
    english: str
    turkish: str
    speaker: str | None = None
    new_turn: bool = False


_LU, _L = sinif("Lu"), sinif("L")
# En çok üç sözcük, her sözcük büyük harfle başlar (BÜYÜK HARF ya da Baş Harf Büyük), rakam yok; ardından ":" ya da "：".
_PATTERN = re.compile(
    "^([" + _LU + "][" + _L + r"'’.\-]*(?: [" + _LU + "][" + _L + r"'’.\-]*){0,2}) ?[:：]\s*"
)
MAX_NAME_LENGTH = 24


def split(text: str) -> Split | None:
    """Baştaki konuşan adı ve cümle; ad yoksa (saat "10:30", adres "https://", oran "16:9", "Note:" gibi başlıklar) None."""
    trimmed = bosluk_satir_kirp(text)
    found = _PATTERN.match(trimmed)
    if not found:
        return None
    name = found.group(1)
    body = bosluk_satir_kirp(trimmed[found.end():])
    if len(name) > MAX_NAME_LENGTH \
            or (" " not in name and name.lower() in NOT_NAMES) \
            or not harf_var(body) \
            or body.startswith("/"):
        return None
    return Split(name, body)


def present(translation: str, source: str, show: bool) -> str:
    """Gösterilecek metin: çeviri `source`'un baştaki adıyla başlar ("ARTHUR: Gitmeliyiz."); `show` kapalıysa
    İngilizcede konuşan adı olan satır başları atılır, yalnız Türkçe cümle kalır ("Hedef: …" gibi Türkçe başlık kalır)."""
    text = translation
    prefix = split(source)
    if prefix is not None:
        own = split(text)
        if own is None or own.name != prefix.name:
            text = f"{prefix.name}: {text}"
    if show:
        return text
    names = {s.name for s in (split(line) for line in source.split("\n")) if s is not None}
    if prefix is not None:
        names.add(prefix.name)
    lines = []
    for line in text.split("\n"):
        found = split(line)
        lines.append(found.body if found is not None and found.name in names else line)
    return "\n".join(lines)


def voiced(lines: Sequence[SpokenLine], prefix: Split | None) -> list[SpokenLine]:
    """Cümlenin seslendirme satırları adı taşımıyorsa konuşan, baştaki addır."""
    if prefix is None:
        return list(lines)
    result = list(lines)
    for index, line in enumerate(result):
        if line.speaker is not None or (index > 0 and line.new_turn):
            break
        result[index] = dataclasses.replace(line, speaker=prefix.name)
    return result
