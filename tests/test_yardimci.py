"""Yardım sohbeti: bilgi tabanı rehberden, durum programdan; anahtar yoksa yönlendirir; motorun chat'i çağrılır."""

import types

from altyazi import yardimci as y
from altyazi.config import Config


def ctl_with(refine=None):  # noqa: ANN001
    return types.SimpleNamespace(cfg=Config(), state="hazir", tv_state=("bagli", "TV hazır"), engine_info={"ocr": "CPU"},
                                 ps5_paired=lambda: False, rp_state=("durdu", ""),
                                 engine=types.SimpleNamespace(refine=refine))


def test_guide_and_state_text():
    g = y.guide_text()
    assert "Cihazı Eşleştir" in g and "Samsung" in g and "Developer Mode" in g
    s = y.state_text(ctl_with())
    assert "Sürüm:" in s and "TV:" in s and "PS5" in s
    assert y._redact("hata sk-ant-api03-abcdefghijklmnop zz") == "hata sk-ant-api03-… zz"


def test_no_key_points_to_settings():
    assert "anahtar" in y.Assistant(ctl_with()).ask("TV bağlanmıyor")


def test_asks_engine_with_history_and_image():
    calls = []

    class Fake:
        name = "claude"

        def chat(self, system, turns, image=None):  # noqa: ANN001
            calls.append((system, list(turns), image))
            return "1. **Ayarlar**'a gir."

    bot = y.Assistant(ctl_with(Fake()))
    assert bot.ask("Samsung'da 12345 yok", b"jpg").startswith("1.")
    bot.ask("tamam sonra?")
    system, turns, image = calls[-1]
    assert "Bilgi tabanı" in system and turns[0] == ("Samsung'da 12345 yok", "1. **Ayarlar**'a gir.")
    assert calls[0][2] == b"jpg" and image is None
    msgs = y.to_messages([("a", "b"), ("c", "")], b"x", claude=True)
    assert msgs[-1]["content"][0]["type"] == "image" and msgs[1] == {"role": "assistant", "content": "b"}
