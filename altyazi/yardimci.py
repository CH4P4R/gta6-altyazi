"""Yardım sohbeti ("Sor"): kurulumda ve kullanımda takılan kullanıcıya adım adım yardım eden yapay zekâ.

Nino Game Translator'ın "Nino'ya Sor"undan esinlenildi; ama ayrı bir sunucu yok: kullanıcının kendi Claude ya da Gemini
anahtarıyla (ya da yerel yapay zekâsıyla) doğrudan sorulur. Bilgi tabanı programın kendi rehberidir (rehber.py: README ve
uygulamadaki Rehber sayfasıyla aynı içerik) ve programın o anki durumu (sürüm, işletim sistemi, PS5/TV durumu, son hata
satırları). Sohbet yalnız bellekte durur; uygulama kapanınca silinir. Ekran görüntüsü eklenebilir (Claude ve Gemini).
"""

from __future__ import annotations

import base64
import logging
import platform
import re

log = logging.getLogger(__name__)

SYSTEM = """Sen "GTA6 Altyazı" programının yardım asistanısın. Program GTA 6 (ve başka oyunlar) için oyundaki İngilizce yazıyı anında okuyup Türkçesini TV'de ya da bilgisayar ekranında oyunun üstünde gösterir. Kullanıcı Türk ve teknik bilgisi az olabilir.

Kurallar:
- Türkçe, kısa ve sıcak yaz ("kanka" diyebilirsin). Adımları numaralı ver; her adım tek iş olsun.
- Ekran ve menü adlarını kalın yaz (**Ayarlar › Sistem › Uzaktan Oynatma**). TV ya da PS5'te nereye basacağını tam söyle.
- Yalnız aşağıdaki bilgi tabanına ve programın durumuna dayan. Bilmediğin bir şeyi uydurma; emin değilsen kullanıcıdan ekranın fotoğrafını ya da TV/PS5 modelini iste.
- Hata mesajı verilmişse önce onun ne demek olduğunu bir cümleyle açıkla, sonra çözümü ver.
- Program içindeki sayfalar: Ana ekran, Okuma alanları, TV, Çeviri, Geçmiş, Ayarlar, Rehber. Kurulum sihirbazı Ayarlar › Diğer'den yeniden açılır.

# Bilgi tabanı (programın rehberi)
{guide}

# Programın şu anki durumu
{state}"""


def guide_text() -> str:
    """Rehberin tamamı düz metin (yapay zekâya bilgi tabanı)."""
    from . import rehber
    out = []
    for g in rehber.GUIDES:
        out.append(f"## {g['title']}\n{g['summary']}")
        for i, st in enumerate(g["steps"], 1):
            items = "\n".join(f"  - {x}" for x in st["items"])
            note = f"\n  Not: {st['note']}" if st.get("note") else ""
            link = f"\n  Bağlantı: {st['link'][1]}" if st.get("link") else ""
            out.append(f"{i}. {st['title']}\n{items}{note}{link}")
    return "\n".join(out)


def state_text(ctl) -> str:  # noqa: ANN001
    """Programın durumu: sürüm, sistem, kaynak, PS5, TV, çeviri motoru ve son uyarı/hata satırları."""
    from . import __version__, paths
    c = ctl.cfg
    lines = [f"Sürüm: {__version__} · Sistem: {platform.system()} {platform.release()} ({platform.machine()})",
             f"Görüntü kaynağı: {c.kaynak.tur} · Oyun yeri: {c.kaynak.oyun_yeri} · Çeviri durumu: {ctl.state}",
             f"TV: marka {c.tv.marka}, adres {c.tv.ip or 'yok'}, durum: {' '.join(ctl.tv_state)}",
             f"PS5 (arka planda): {'eşli: ' + (c.ps5.ad or c.ps5.ip) if ctl.ps5_paired() else 'eşli değil'} · "
             f"durum: {' '.join(getattr(ctl, 'rp_state', ('', '')))}",
             f"Çeviri motorları: {ctl.engine_info or 'hazırlanıyor'} · kalite katmanı ayarı: {c.ceviri.kalite}"]
    try:
        log_lines = paths.data("altyazi.log").read_text(encoding="utf-8", errors="replace").splitlines()
        bad = [ln for ln in log_lines[-400:] if " WARNING " in ln or " ERROR " in ln][-12:]
        if bad:
            lines.append("Son uyarı ve hatalar:\n" + "\n".join(_redact(b) for b in bad))
    except OSError:
        pass
    return "\n".join(lines)


def _redact(line: str) -> str:
    """Günlükten anahtar benzeri dizgeleri at (yapay zekâya gitmesin)."""
    return re.sub(r"(sk-ant-[\w-]{6})[\w-]+|(AIza[\w-]{4})[\w-]+|([0-9a-f]{8})[0-9a-f-]{20,}", r"\1\2\3…", line)


class Assistant:
    """ask(soru, resim_jpeg=None) -> cevap. Geçmiş bellekte tutulur."""

    def __init__(self, ctl):  # noqa: ANN001
        self.ctl = ctl
        self.history: list[tuple[str, str]] = []

    def available(self) -> str | None:
        """Kullanılabilir motor adı; yoksa None."""
        eng = getattr(self.ctl, "engine", None)
        r = getattr(eng, "refine", None)
        return getattr(r, "name", None) if r is not None and r.name in ("claude", "gemini", "yerelai") else None

    def ask(self, question: str, image: bytes | None = None) -> str:
        eng = self.ctl.engine.refine if self.available() else None
        if eng is None:
            return ("Yardım sohbeti için bir yapay zekâ anahtarı lazım: **Çeviri** sayfasında Claude ya da ücretsiz Gemini "
                    "anahtarını gir. O zamana kadar **Rehber** sayfasındaki resimli adımlara bakabilirsin.")
        system = SYSTEM.format(guide=guide_text(), state=state_text(self.ctl))
        turns = self.history[-8:] + [(question, "")]
        try:
            answer = eng.chat(system, turns, image) or ""
        except Exception as e:  # noqa: BLE001
            log.warning("Yardım sohbeti: %s", e)
            return f"Şu an cevap alamadım ({type(e).__name__}). İnternet bağlantını ve anahtarını kontrol edip tekrar dene."
        answer = answer.strip() or "Cevap boş geldi, tekrar sorar mısın?"
        self.history.append((question, answer))
        return answer


def to_messages(turns: list[tuple[str, str]], image: bytes | None, claude: bool) -> list[dict]:
    """(soru, cevap) çiftlerini sohbet mesajlarına çevirir; son soruya resim eklenir."""
    msgs: list[dict] = []
    for i, (q, a) in enumerate(turns):
        last = i == len(turns) - 1
        if last and image:
            b64 = base64.b64encode(image).decode()
            if claude:
                content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                           {"type": "text", "text": q}]
            else:
                content = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                           {"type": "text", "text": q}]
            msgs.append({"role": "user", "content": content})
        else:
            msgs.append({"role": "user", "content": q})
        if a:
            msgs.append({"role": "assistant", "content": a})
    return msgs
