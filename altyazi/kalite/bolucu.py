# SPDX-License-Identifier: AGPL-3.0-only
"""Altyazıyı çevirmene cümle cümle verir.

Nino Game Translator'ın SubtitleSegmenter.swift dosyasından taşındı (core/Sources/CouchSubsCore/SubtitleSegmenter.swift;
Windows: CouchSubs.Translation/SubtitleSegmenter.cs, aynı kurallar). `SpeakerNames` sınıfı da aynı dosyadandır.

Alt alta sarılmış satırlar tek cümle olarak birleştirilir. Konuşmacı etiketi ("ATREUS:", "Kratos:") ve diyalog
tireleri çevrilmez: çeviri motorları adı çevirmeye ya da silmeye çalışıyor.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Iterable
from dataclasses import dataclass

from ._harf import bosluk_kirp, harf_var, sinif


@dataclass(frozen=True)
class Piece:
    """Çevrilecek bir parça ya da olduğu gibi kalacak ayraç/etiket."""
    text: str
    translate: bool


_LU, _LL, _L = sinif("Lu"), sinif("Ll"), sinif("L")
# Etiket: satır ya da cümle başında, en çok üç sözcüklü ad ve iki nokta.
# Ya tümü büyük harf ("ATREUS:", "OLD MAN:") ya da her sözcüğü büyük harfle başlayan ("Kratos:", "Mimir Head:").
_LABEL = re.compile(
    "^([" + _LU + "][" + _LU + r"\d'’.\-]+(?: [" + _LU + "][" + _LU + r"\d'’.\-]*){0,2}"
    + "|[" + _LU + "][" + _LL + "][" + _L + r"'’.\-]*(?: [" + _LU + "][" + _L + r"'’.\-]*){0,2}):\s+"
)
_DASH = re.compile(r"^[-–—]+\s*")
# `CharacterSet.newlines`: U+000A–U+000D, U+0085, U+2028, U+2029.
_NEWLINES = re.compile("[\n\x0b\x0c\r\x85  ]")

# Büyük harfle başlayıp iki noktayla biten ama ad olmayan oyun başlıkları; bunlar çevrilir.
NOT_NAMES = frozenset([
    "note", "warning", "tip", "hint", "objective", "objectives", "quest", "goal", "new", "reward", "rewards",
    "location", "chapter", "mission", "task", "tutorial", "update", "info", "status", "level", "controls",
    "press", "hold", "tap", "remember", "example", "question", "answer", "result", "results", "time",
    "listen", "look", "wait", "okay", "ok", "well", "so", "yes", "no", "now", "then", "and", "but",
])

# Noktadan sonra cümle bitmeyen kısaltmalar ("Mr. Smith").
ABBREVIATIONS = frozenset([
    "mr", "mrs", "ms", "dr", "st", "jr", "sr", "prof", "mt", "vs", "etc", "e.g", "i.e", "lt", "sgt", "capt", "gen", "col",
])


def split(text: str) -> list[Piece]:
    """Altyazıyı çevrilecek cümlelere ve olduğu gibi kalacak ayraç/etiketlere böler."""
    pieces: list[Piece] = []
    block = ""
    separator = ""

    def flush() -> None:
        nonlocal block, separator
        if not block:
            return
        if separator:
            pieces.append(Piece(separator, False))
        _add_block(block, pieces)
        block = ""
        separator = "\n"

    for raw in _NEWLINES.split(text):
        line = bosluk_kirp(raw)
        if not line:
            continue
        # Etiketli ya da tireli satır yeni bir konuşmadır; diğer satırlar sarmadır, birleştirilir.
        if speaker_label(line) is not None or _DASH.match(line):
            flush()
        if block:
            block += " "
        block += line
    flush()
    return pieces


def speaker_label(line: str) -> str | None:
    """Satır başındaki konuşmacı etiketi, boşluğuyla birlikte ("ATREUS: ")."""
    found = _LABEL.match(line)
    if not found:
        return None
    label = found.group(0)
    name = bosluk_kirp(label)[:-1]
    # Tek sözcüklü başlıklar ("Note:", "Objective:") ad değildir.
    if " " not in name and name.lower() in NOT_NAMES:
        return None
    return label


def name_from_label(label: str) -> str:
    """Etiketteki ad ("ATREUS: " → "ATREUS")."""
    return bosluk_kirp(label)[:-1]


def _add_block(raw: str, pieces: list[Piece]) -> None:
    block = " ".join(raw.split())
    dash = _DASH.match(block)
    if dash:
        pieces.append(Piece(bosluk_kirp(dash.group(0)) + " ", False))
        block = block[len(dash.group(0)):]
    for index, sentence in enumerate(sentences(block)):
        if index > 0:
            pieces.append(Piece(" ", False))
        body = sentence
        label = speaker_label(body)
        if label is not None:
            pieces.append(Piece(name_from_label(label) + ": ", False))
            body = body[len(label):]
        if body:
            pieces.append(Piece(body, harf_var(body)))


_ENDERS = frozenset(".!?…")
_CLOSERS = frozenset("\"'”’)]")


def sentences(block: str) -> list[str]:
    """Cümle sonu: . ! ? … (yinelenebilir), ardından isteğe bağlı kapanış tırnağı/parantez ve boşluk.
    Küçük harfle süren yer ("wait... what") ve kısaltmalar cümle sonu değildir."""
    result: list[str] = []
    start = 0
    index = 0
    while index < len(block):
        if block[index] != " ":
            index += 1
            continue
        back = index - 1
        while back >= start and block[back] in _CLOSERS:
            back -= 1
        candidate = block[start:index]
        following = block[index + 1] if index + 1 < len(block) else None
        if back >= start and block[back] in _ENDERS and not (following is not None and following.islower()) \
                and not _ends_with_abbreviation(candidate):
            result.append(candidate)
            start = index + 1
        index += 1
    if start < len(block):
        result.append(block[start:])
    return result


def _ends_with_abbreviation(sentence: str) -> bool:
    if not sentence.endswith("."):
        return False
    words = [w for w in sentence.split(" ") if w]
    word = (words[-1] if words else "")[:-1]
    # Tek harf ad baş harfidir ("J. R. R.").
    if len(word) == 1 and word.isupper():
        return True
    return word.lower() in ABBREVIATIONS


def normalize_case(sentence: str, names: Iterable[str] = ()) -> str:
    """Tümü büyük harfli cümleyi ("THE GATE WILL NOT HOLD.") cümle düzenine çevirir; çeviri motorları büyük harfli
    sözcükleri ad sanıp çevirmeden bırakıyor. Bilinen adlar (konuşmacı etiketlerinden öğrenilen) büyük harfle kalır.
    Tek sözcüğe dokunulmaz."""
    if any(c.islower() for c in sentence) or sum(1 for c in sentence if c.isalpha()) < 2 \
            or " " not in bosluk_kirp(sentence):
        return sentence

    lower_names = {n.lower() for n in names}
    output: list[str] = []
    word = ""
    start_of_sentence = True

    def flush_word() -> None:
        nonlocal word, start_of_sentence
        if not word:
            return
        lower = word.lower()
        if lower == "i" or start_of_sentence or lower in lower_names:
            output.append(lower[:1].upper() + lower[1:])
        else:
            output.append(lower)
        start_of_sentence = False
        word = ""

    for character in sentence:
        if character.isalpha() or character in "'’":
            word += character
        else:
            flush_word()
            if character in ".!?…":
                start_of_sentence = True
            output.append(character)
    flush_word()
    return "".join(output)


class SpeakerNames:
    """Konuşmacı etiketlerinden öğrenilen karakter adları. Adlar cümle içinde de büyük harfle kalır ve çevrilmez."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._names: set[str] = set()

    @property
    def all(self) -> set[str]:
        with self._lock:
            return set(self._names)

    def learn(self, pieces: Iterable[Piece]) -> None:
        """Parçalardaki etiketlerden adları öğrenir ("OLD MAN: " → "Old", "Man" değil, "Old Man")."""
        found = [name_from_label(p.text) for p in pieces if not p.translate and p.text.endswith(": ")]
        found = [name for name in found if name]
        if not found:
            return
        with self._lock:
            for name in found:
                # Çok sözcüklü adın her sözcüğü ayrıca tanınır: "ATREUS" etiketi cümledeki "ATREUS"u korur.
                self._names.update(w for w in name.split(" ") if len(w) >= 2)
