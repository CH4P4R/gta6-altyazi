# SPDX-License-Identifier: AGPL-3.0-only
"""Nino Game Translator'ın Pipeline/FrameGate.swift dosyasından taşındı.

Okuma hattına aynı anda tek kare girer; önceki kare hâlâ işleniyorsa yeni kare atlanır (kareler birikmez). Kapı her
girişe bir numara verir: durdurma ve yeni hat kapıyı sıfırlar, eski okumanın geç gelen çıkışı yeni okumayı serbest
bırakmaz. `stuck_after_ms`'ten uzun süren okuma takılmış sayılır; çağıran hattı yeniden kurar.
"""

from __future__ import annotations

from dataclasses import dataclass

# Yavaş makinede bütün karenin okuması birkaç saniye sürebilir; gerçek takılma hiç bitmediği için 45 sn yeter.
DEFAULT_STUCK_AFTER_MS = 45_000


@dataclass(frozen=True)
class Busy:
    """Önceki kare işleniyor; bu kare atlanır."""


@dataclass(frozen=True)
class Enter:
    """Kare hatta girer; bitince `leave(token)` çağrılır."""
    token: int


@dataclass(frozen=True)
class Stuck:
    """Önceki okuma `ms` milisaniyedir bitmedi. Kapı sıfırlandı; çağıran hattı yeniden kurup kareyi yeniden sokar."""
    ms: int


BUSY = Busy()


class FrameGate:
    DEFAULT_STUCK_AFTER_MS = DEFAULT_STUCK_AFTER_MS

    def __init__(self, stuck_after_ms: int = DEFAULT_STUCK_AFTER_MS):
        self.stuck_after_ms = stuck_after_ms
        self._current: tuple[int, int] | None = None     # (numara, giriş anı)
        self._last_token = 0

    @property
    def is_busy(self) -> bool:
        """Bir kare işleniyor mu."""
        return self._current is not None

    def enter(self, now: int) -> Busy | Enter | Stuck:
        """`now`: milisaniye saati (ör. time.monotonic() * 1000)."""
        if self._current is not None:
            elapsed = now - self._current[1]
            if elapsed < self.stuck_after_ms:
                return BUSY
            self._current = None
            return Stuck(elapsed)
        self._last_token += 1
        self._current = (self._last_token, now)
        return Enter(self._last_token)

    def leave(self, token: int) -> None:
        """Kare işlendi. Kapı bu arada sıfırlandıysa eski okumanın çıkışı bir şey değiştirmez."""
        if self._current is not None and self._current[0] == token:
            self._current = None

    def reset(self) -> None:
        """Çeviri durdu ya da hat yeniden kuruldu: süren okuma beklenmez."""
        self._current = None
