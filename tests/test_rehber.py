"""Rehber tek kaynaktır: uygulama, sihirbaz ve README aynı içeriği gösterir."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_guide_image_exists():
    from altyazi import rehber
    folder = ROOT / "altyazi" / "ui" / "rehber"
    for g in rehber.GUIDES:
        assert g["steps"], g["key"]
        for st in g["steps"]:
            assert st["title"] and st["items"], (g["key"], st)
            if st.get("img"):
                assert (folder / f"{st['img']}.png").exists(), st["img"]
    for where in ("monitor", "tv", "ikisi"):
        ids = [st["id"] for st in rehber.chiaki_steps(where)]
        assert "indir" in ids and ids[-1] == "baglan"


def test_readme_guide_is_up_to_date():
    """README'deki rehber altyazi/rehber.py'den üretilir; elle değiştirilmiş ya da eskimişse: python tools/readme_rehber.py"""
    sys.path.insert(0, str(ROOT / "tools"))
    import readme_rehber
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    a, b = text.index(readme_rehber.START), text.index(readme_rehber.END) + len(readme_rehber.END)
    assert text[a:b] == readme_rehber.render()


def test_html_and_markdown_formatting():
    from altyazi import rehber
    st = rehber.step("Başlık", ["**Kalın** yaz", "ikinci"], note="not")
    html = rehber.to_html(st)
    assert "<b>Kalın</b>" in html and "①" in html and "②" in html and "not" in html
    md = rehber.to_markdown(st)
    assert "1. **Kalın** yaz" in md and "> not" in md
