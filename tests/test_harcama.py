"""Claude harcama sayacı."""

import pytest

from altyazi import harcama


def test_cost_uses_real_token_counts():
    u = {"input_tokens": 300, "cache_read_input_tokens": 1250, "cache_creation_input_tokens": 0,
         "output_tokens": 60}
    std = harcama.cost("claude-opus-5-5", u)
    # 300×4 + 1250×0.20 + 60×20 = 2650 → $0.00265
    assert std == pytest.approx(0.00265)
    assert harcama.cost("claude-opus-5-5", {**u, "speed": "fast"}) == pytest.approx(0.0053)
    # önbelleğe yazma girdi fiyatının 1.25 katı
    assert harcama.cost("claude-opus-5-5", {"cache_creation_input_tokens": 1000}) == pytest.approx(0.005)
    # bilinmeyen/ekli ad en yakın fiyatla; usage yoksa 0
    assert harcama.cost("claude-haiku-5-5", u) < std / 20
    assert harcama.cost("claude-opus-5-5-preview", u) == pytest.approx(std)
    assert harcama.cost("claude-opus-5-5", None) == 0.0


def test_spend_persists_and_notifies(tmp_path):
    path = tmp_path / "harcama.json"
    s = harcama.Spend()
    s.load(path)
    calls = []
    s.listener = lambda: calls.append(1)
    s.add("claude-opus-5-5", {"input_tokens": 1_000_000})          # $4
    s.add("claude-opus-5-5", {"output_tokens": 100_000, "speed": "fast"})   # $4
    assert s.session == pytest.approx(8.0) and s.requests == 2 and len(calls) == 2
    assert s.month() == pytest.approx(8.0)
    s.save()
    again = harcama.Spend()
    again.load(path)
    assert again.total == pytest.approx(8.0) and again.session == 0.0       # oturum sıfırdan, toplam korunur
    assert again.hourly() is None


def test_money_format():
    assert harcama.money(0.374) == "0,37 $"
    assert harcama.money(1234.5) == "1.234,50 $"
    assert harcama.money(0.004) == "0,4¢"
    assert harcama.money(0) == "0,00 $"
