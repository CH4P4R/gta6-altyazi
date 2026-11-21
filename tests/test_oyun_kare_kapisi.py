# SPDX-License-Identifier: AGPL-3.0-only
"""Nino Game Translator'ın FrameGateTests.swift denemelerinden taşındı."""

from altyazi.oyun.kare_kapisi import BUSY, DEFAULT_STUCK_AFTER_MS, Enter, FrameGate, Stuck


def test_one_frame_at_a_time():
    gate = FrameGate(stuck_after_ms=1000)
    entry = gate.enter(now=0)
    assert isinstance(entry, Enter), "ilk kare girer"
    assert gate.enter(now=100) == BUSY, "önceki kare işlenirken yenisi atlanır"
    gate.leave(entry.token)
    assert not gate.is_busy
    assert isinstance(gate.enter(now=200), Enter), "önceki bitince sonraki girer"


def test_reset_lets_the_next_frame_in_while_an_old_read_is_still_running():
    """Durdur / Başlat kapıyı sıfırlar: eski oturumdan kalan bitmemiş okuma yeni oturumu bekletmez."""
    gate = FrameGate(stuck_after_ms=1000)
    old = gate.enter(now=0)
    assert isinstance(old, Enter)
    gate.reset()
    fresh = gate.enter(now=10)
    assert isinstance(fresh, Enter), "sıfırlanınca yeni kare girer"
    gate.leave(old.token)          # eski okuma sonunda biterse yeni okumayı serbest bırakmaz
    assert gate.is_busy
    assert gate.enter(now=20) == BUSY
    gate.leave(fresh.token)
    assert not gate.is_busy


def test_read_that_never_finishes_is_reported_as_stuck():
    gate = FrameGate(stuck_after_ms=1000)
    stuck = gate.enter(now=0)
    assert isinstance(stuck, Enter)
    assert gate.enter(now=999) == BUSY
    assert gate.enter(now=1500) == Stuck(1500)
    assert not gate.is_busy
    nxt = gate.enter(now=1501)
    assert isinstance(nxt, Enter), "takılma bildirilince sonraki kare girer"
    gate.leave(stuck.token)
    assert gate.is_busy, "takılan okumanın geç çıkışı yeni okumayı bırakmaz"
    gate.leave(nxt.token)
    assert not gate.is_busy


def test_default_stuck_limit_allows_slow_reads():
    gate = FrameGate()
    gate.enter(now=0)
    assert gate.enter(now=10_000) == BUSY, "yavaş makinede bütün karenin okuması birkaç saniye sürebilir"
    assert gate.enter(now=DEFAULT_STUCK_AFTER_MS) == Stuck(DEFAULT_STUCK_AFTER_MS)
