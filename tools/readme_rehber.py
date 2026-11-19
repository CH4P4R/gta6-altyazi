"""README'deki resimli rehber bölümünü altyazi/rehber.py'den üretir (uygulamadaki Rehber sayfasıyla aynı içerik).

    python tools/readme_rehber.py

README.md içinde <!-- REHBER:BASLA --> ile <!-- REHBER:BITIS --> arası yeniden yazılır.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from altyazi import rehber  # noqa: E402

START, END = "<!-- REHBER:BASLA -->", "<!-- REHBER:BITIS -->"
EMOJI = {"monitor": "🖥️", "tv-izle": "📺", "google-tv": "🤖", "lg": "📺", "samsung": "📺", "discord": "💬",
         "obs": "🎥", "gta6": "🎯", "ucretsiz": "🆓", "paketler": "📦", "sorunlar": "🧰"}


def render() -> str:
    out = [START, "",
           "> Bu bölüm uygulamadaki **Rehber** sayfasıyla aynıdır (kaynak: `altyazi/rehber.py`). "
           "Uygulamada da soldaki menüden **Rehber**'e girip aynı adımları resimli izleyebilirsin.", ""]
    out.append("| Konu | Ne anlatıyor |")
    out.append("|---|---|")
    for g in rehber.GUIDES:
        out.append(f"| {EMOJI.get(g['key'], '•')} [{g['title']}](#rehber-{g['key']}) | {g['summary']} |")
    out.append("")
    for g in rehber.GUIDES:
        out.append(f'<a name="rehber-{g["key"]}"></a>')
        out.append("<details>")
        out.append(f"<summary><b>{EMOJI.get(g['key'], '•')} {g['title']}</b> · {g['summary']}</summary>")
        out.append("")
        for i, st in enumerate(g["steps"], 1):
            out.append(f"#### Adım {i}: {st['title']}")
            out.append("")
            out.append(rehber.to_markdown(st))
            out.append("")
        out.append("</details>")
        out.append("")
    out.append(END)
    return "\n".join(out)


def main() -> int:
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    if START not in text or END not in text:
        print("README'de REHBER işaretleri yok")
        return 1
    a, b = text.index(START), text.index(END) + len(END)
    readme.write_text(text[:a] + render() + text[b:], encoding="utf-8")
    print("README rehberi güncellendi")
    return 0


if __name__ == "__main__":
    sys.exit(main())
