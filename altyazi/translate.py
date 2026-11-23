"""Çeviri katmanları.

1. Önbellek (0 ms): daha önce görülen metin (OCR küçük hata yapsa bile benzerlikle bulunur).
2. Hızlı katman (~15-40 ms, GPU): yerel OPUS-MT modeli CTranslate2 ile. Ekrana hemen basılır.
3. Kalite katmanı (~0.4-1.5 sn): Claude / Gemini / DeepL. Gelince ekrandaki yazı güncellenir
   ve sonuç önbelleğe yazılır; aynı metin bir daha görülürse direkt kaliteli hali gelir.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import sys
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import slang, terms
from .config import CeviriCfg

log = logging.getLogger(__name__)

FAST, REFINED = 1, 2


class _Race:
    """Kalite öncelikli mod: hızlı çeviri, kaliteli çeviri için kısa bir süre bekler."""

    def __init__(self, deadline: float):
        self.deadline = deadline
        self.done = threading.Event()
        self.refined_ok = False


@dataclass
class Result:
    text: str
    source: str
    ms: float
    quality: int


def normalize(text: str) -> str:
    text = text.lower().replace("’", "'")
    text = re.sub(r"[^\w']+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------- önbellek
# OCR'ın birbirine karıştırdığı harfler: benzer satırı önbellekten alırken farkın bunlardan ibaret olması şartı
_OCR_FOLD = [("rn", "m"), ("vv", "w"), ("cl", "d"), ("1", "i"), ("l", "i"), ("|", "i"), ("j", "i"), ("ı", "i"),
             ("0", "o"), ("5", "s"), ("8", "b")]
_NUMBER = re.compile(r"\d+(st|nd|rd|th|k|m|s)?")
_NEGATIONS = {"not", "no", "never", "nothing", "nobody", "none", "nowhere", "neither", "nor", "without"}


def _fold(word: str) -> str:
    w = word.replace("'", "")
    for a, b in _OCR_FOLD:
        w = w.replace(a, b)
    return w


def _meaning(words: list[str]) -> tuple:
    """Bir harfi farklı olsa da anlamı değiştiren şeyler: sayılar ve olumsuzluklar."""
    nums = tuple(w for w in words if _NUMBER.fullmatch(w))
    neg = tuple(sorted(w for w in words if w in _NEGATIONS or w.endswith("n't")))
    return nums, neg


def ocr_variant(a: str, b: str) -> bool:
    """b, a'nın OCR hatalı okunmuş hali olabilir mi? (normalize edilmiş metinler)

    "Go to the car" ile "Go to the bar" %92 benziyor ama başka cümle; "Frank1in" ile "Franklin" aynı cümle.
    Kelime sayısı aynı olmalı, sayılar ve olumsuzluklar birebir aynı olmalı, farklı her kelime OCR'ın karıştırdığı
    harflerle aynı hale gelmeli ya da (5+ harfli kelimede) tek harf eksik/fazla olmalı.
    """
    wa, wb = a.split(), b.split()
    if len(wa) != len(wb) or _meaning(wa) != _meaning(wb):
        return False
    for x, y in zip(wa, wb):
        if x == y or _fold(x) == _fold(y):
            continue
        fx, fy = _fold(x), _fold(y)
        if min(len(fx), len(fy)) >= 5 and abs(len(fx) - len(fy)) == 1:
            short, long_ = sorted((fx, fy), key=len)
            if any(long_[:i] + long_[i + 1:] == short for i in range(len(long_))):
                continue
        return False
    return True


class Cache:  # noqa: D101
    # Yeni sürümde çevirisi düzeltilen ifadeler: önbellekteki eski (yanlış) çevirileri bir kez silinir
    STALE = [("long-guns", re.compile(r"\blong guns?\b", re.IGNORECASE))]

    def __init__(self, path: str, similarity: int):
        self.similarity = similarity
        self.lock = threading.Lock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS ceviri (anahtar TEXT PRIMARY KEY, kaynak TEXT,"
                        " ceviri TEXT, kalite INTEGER, motor TEXT, zaman REAL)")
        self._forget_stale()
        self.mem: dict[str, tuple[str, int, str]] = {
            k: (t, q, m) for k, t, q, m in self.db.execute("SELECT anahtar, ceviri, kalite, motor FROM ceviri")}
        self.keys = list(self.mem)
        log.info("Önbellek: %d çeviri yüklendi", len(self.mem))

    def _forget_stale(self) -> None:
        self.db.execute("CREATE TABLE IF NOT EXISTS temizlik (ad TEXT PRIMARY KEY)")
        done = {r[0] for r in self.db.execute("SELECT ad FROM temizlik")}
        for name, rx in self.STALE:
            if name in done:
                continue
            rows = [k for k, src in self.db.execute("SELECT anahtar, kaynak FROM ceviri") if rx.search(src or k)]
            self.db.executemany("DELETE FROM ceviri WHERE anahtar = ?", [(k,) for k in rows])
            self.db.execute("INSERT INTO temizlik VALUES (?)", (name,))
            if rows:
                log.info("Önbellek: %d eski çeviri silindi (%s)", len(rows), name)
        self.db.commit()

    def get(self, text: str) -> tuple[str, int, str] | None:
        key = normalize(text)
        if not key:
            return None
        hit = self.mem.get(key)
        if hit or len(key) < 10 or not self.keys:
            return hit
        from rapidfuzz import fuzz, process
        with self.lock:
            cands = process.extract(key, self.keys, scorer=fuzz.ratio, score_cutoff=self.similarity, limit=5)
        for cand, _score, _i in cands:
            if ocr_variant(cand, key):
                return self.mem[cand]
        return None

    def rows(self, min_quality: int = REFINED) -> list[tuple[str, str]]:
        """(İngilizce, Türkçe) satırları (paket olarak dışa aktarmak için)."""
        with self.lock:
            return list(self.db.execute("SELECT kaynak, ceviri FROM ceviri WHERE kalite >= ?", (min_quality,)))

    def put(self, text: str, translation: str, quality: int, engine: str) -> None:
        key = normalize(text)
        if not key or not translation:
            return
        old = self.mem.get(key)
        if old and old[1] > quality:
            return
        with self.lock:
            if key not in self.mem:
                self.keys.append(key)
            self.mem[key] = (translation, quality, engine)
            self.db.execute("INSERT OR REPLACE INTO ceviri VALUES (?,?,?,?,?,?)",
                            (key, text, translation, quality, engine, time.time()))
            self.db.commit()


# ---------------------------------------------------------------------- hızlı motorlar
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'])")


class LocalMT:
    """OPUS-MT (Helsinki-NLP) İngilizce→Türkçe, CTranslate2 ile. tools/model_indir.py ile kurulur."""

    name = "yerel"

    def __init__(self, path: str, device: str = "auto", beam: int = 2, threads: int = 0):
        import ctranslate2
        import sentencepiece as spm

        from . import paths
        p = paths.model_path(path)
        if not (p / "model.bin").exists():
            raise FileNotFoundError(f"{p} içinde model yok. Önce: python tools/model_indir.py")
        if device == "auto":
            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        compute = "int8_float16" if device == "cuda" else "int8"
        threads = 0 if device == "cuda" else (int(threads) if threads and threads > 0
                                              else max(2, min(8, (os.cpu_count() or 4) - 2)))
        self._make = lambda ct: ctranslate2.Translator(str(p), device=device, compute_type=ct, inter_threads=2,
                                                       intra_threads=threads)
        self.tr = self._make(compute)
        self.sp_src = spm.SentencePieceProcessor(model_file=str(p / "source.spm"))
        self.sp_tgt = spm.SentencePieceProcessor(model_file=str(p / "target.spm"))
        self.beam = beam
        self.device = device
        self.compute = compute
        if device == "cpu":
            self._tune()
        log.info("Yerel çeviri modeli: %s (%s, %s, ışın %d)", p.name, device, self.compute, self.beam)

    SAMPLE = "Get in the car, we have to go before the cops show up."

    def _timed(self) -> float:
        t0 = time.perf_counter()
        self.translate(self.SAMPLE)
        return (time.perf_counter() - t0) * 1000

    def _tune(self) -> None:
        """İşlemcide en hızlı ayarı ölçerek seç: Apple Silicon'da float32 (Accelerate) çoğu zaman int8'den hızlı;
        yavaş işlemcide ışın 1 (yapay zekâ katmanı zaten cilalar). Hedef: bir satır ~150 ms altı."""
        try:
            self._timed()                                  # ısınma (model belleğe yüklenir)
            best = self._timed()
            if sys.platform == "darwin" and best > 120:
                old = self.tr
                self.tr = self._make("float32")
                self._timed()
                f32 = self._timed()
                if f32 < best * 0.85:
                    best, self.compute = f32, "float32"
                else:
                    self.tr = old
            if best > 300 and self.beam > 1:
                self.beam = 1
                best = self._timed()
            log.info("Yerel çeviri hızı: ~%.0f ms/satır", best)
        except Exception:  # noqa: BLE001
            log.exception("Yerel çeviri ayarı ölçülemedi")

    def translate(self, text: str, kind: str = "", context=None) -> str:
        sents = [s for s in _SENT.split(text) if s.strip()] or [text]
        batch = [self.sp_src.encode(s, out_type=str) + ["</s>"] for s in sents]
        res = self.tr.translate_batch(batch, beam_size=self.beam, max_decoding_length=256,
                                      repetition_penalty=1.1)
        return " ".join(self.sp_tgt.decode(r.hypotheses[0]) for r in res).strip()


class GoogleFree:
    """Anahtarsız Google Çeviri (yerel model yoksa yedek)."""

    name = "google"

    def __init__(self):
        import requests
        self.s = requests.Session()

    def translate(self, text: str, kind: str = "", context=None) -> str:
        r = self.s.get("https://translate.googleapis.com/translate_a/single",
                       params={"client": "gtx", "sl": "en", "tl": "tr", "dt": "t", "q": text}, timeout=5)
        r.raise_for_status()
        return "".join(part[0] for part in r.json()[0] if part[0]).strip()


# ---------------------------------------------------------------------- kalite motorları
SYSTEM_PROMPT = """You translate English text from the video game Grand Theft Auto VI into Turkish, live. Your Turkish replaces the English on screen while the player watches, so it is read in a second or two.

Output only the Turkish translation: no quotes, labels, notes or explanations.

kind=subtitle (spoken dialogue): write natural, spoken, everyday Turkish the way a good Turkish fansub would. Keep the tone, slang, swearing, threats and humor as strong as the original; do not soften or censor. Keep it about as short as the English. Characters address each other with "sen" unless the scene is clearly formal.
kind=ui (help boxes, notifications, objectives, menus): concise standard Turkish game-UI style; objectives in the imperative ("Araca bin.", "Lucia'yı takip et."). Keep button and control names exactly as written (X, O, L2, R1, Options, ~INPUT~ and similar).
kind=message (phone text messages between characters): casual Turkish texting style. Keep the sender's tone, slang, abbreviations and ALL-CAPS shouting (in Turkish capitals), keep emojis and money signs ($$$). Short and natural, like a real Turkish text message ("Karavanıma! Anladın mı?").

Never translate proper names: characters, gangs, places, businesses, brands, vehicles, weapons and radio stations stay as they are (Jason, Lucia, Vice City, Leonida, Port Gellhorn, Ambrosia, Grassrivers, Mount Kalaga...). Add Turkish suffixes with an apostrophe (Lucia'yla, Vice City'de).

The English comes from OCR and may contain small recognition errors (l/I, missing apostrophes, stray characters). Silently translate what was obviously meant. If the input is not real language (OCR garbage), output it unchanged.{glossary}"""


SCREEN_PROMPT = """You read a screenshot from the video game Grand Theft Auto VI and translate its on-screen English text into Turkish for a Turkish player.

Numbered boxes drawn on the image mark text regions an OCR engine found; each number sits at its box's top-left corner and the user message lists what the OCR read there (it may contain errors). For each meaningful piece of text, read the English yourself from the image and translate it:
- Text inside a numbered box: use that number as id and box [0, 0, 0, 0].
- Text with no box (stylized titles, small print the OCR missed): id -1 and its box as [x0, y0, x1, y1] in 0-1000 coordinates of the whole image.
- Merge lines that belong to the same message, menu entry or sentence into one item; if one item spans several numbered boxes, use the first box's id.
- Skip HUD numbers, money, ammo, clock, map place names, vehicle license plates (and the state name on them), logos, standalone button icons with no text next to them, and text that is not English.
- Controller button icons inside a sentence ("Press [icon] to enter") are part of it: write PlayStation face buttons as △ ○ □ ✕ and others by name (L1, R2, L3, OPTIONS, TOUCHPAD, D-pad as ↑ ↓ ← →) in both english and turkish, at the same place, e.g. "Press △ to enter" → "Binmek için △ tuşuna bas".

Translation style: dialogue and messages in natural spoken Turkish (keep slang and tone, "sen" between characters); menus, objectives and notifications in concise standard Turkish game UI style, objectives in the imperative. Keep button names (X, O, L2, R1, Options) and proper names (Jason, Lucia, Vice City, Leonida...) unchanged; add Turkish suffixes with an apostrophe.{glossary}"""

SCREEN_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "english": {"type": "string"},
                    "turkish": {"type": "string"},
                    "box": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["id", "english", "turkish", "box"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["items"],
    "additionalProperties": False,
}


def _glossary_text(sozluk: dict[str, str]) -> str:
    from .gta_terms import style_guide
    return _required_terms(sozluk) + style_guide()


def _required_terms(sozluk: dict[str, str]) -> str:
    if not sozluk:
        return ""
    return "\n\nRequired terms (English -> Turkish):\n" + "\n".join(f"- {k} -> {v}" for k, v in sozluk.items())


def _user_message(text: str, kind: str, context: list[tuple[str, str]]) -> str:
    parts = []
    if context:
        parts.append("Previous lines, for context only (do not translate again):")
        parts += [f"EN: {en}\nTR: {tr}" if tr else f"EN: {en}" for en, tr in context]
        parts.append("")
    label = {"altyazi": "subtitle", "mesaj": "message"}.get(kind, "ui")
    parts.append(f"kind={label}")
    parts.append(f"<text>{text}</text>")
    return "\n".join(parts)


class ClaudeMT:
    name = "claude"

    def __init__(self, cfg: CeviriCfg):
        import anthropic

        self.anthropic = anthropic
        # Kimlik bilgisi ortamdan okunur: ANTHROPIC_API_KEY (ya da `ant auth login` profili)
        self.client = anthropic.Anthropic(api_key=cfg.claude_anahtar or None, max_retries=1, timeout=10.0)
        self.model = cfg.claude_model
        self.effort = cfg.claude_efor
        self.fast = cfg.claude_hizli_mod
        self.system = [{"type": "text", "text": SYSTEM_PROMPT.format(glossary=_glossary_text(cfg.sozluk)),
                        "cache_control": {"type": "ephemeral"}}]
        self.screen_system = [{"type": "text", "text": SCREEN_PROMPT.format(glossary=_glossary_text(cfg.sozluk)),
                               "cache_control": {"type": "ephemeral"}}]
        # TLS bağlantısını önceden kur ki ilk altyazı el sıkışmayı beklemesin (ücretsiz çağrı)
        threading.Thread(target=self._warm, daemon=True).start()

    def _warm(self) -> None:
        try:
            self.client.models.retrieve(self.model)
        except Exception as e:  # noqa: BLE001
            log.warning("Claude bağlantı testi başarısız: %s", e)

    def _request(self, text: str, kind: str, context):
        kwargs = dict(
            model=self.model,
            max_tokens=1024,
            system=self.system,
            messages=[{"role": "user", "content": _user_message(text, kind, context)}],
            output_config={"effort": self.effort},
            # Güvenlik filtresi bir satırı reddederse sunucu aynı isteği otomatik başka modelle tamamlar
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        return self._create(kwargs)

    def _create(self, kwargs: dict):
        """İsteği gönder (hızlı mod limiti dolarsa normal hızla) ve maliyetini harcama sayacına yaz."""
        from .harcama import tracker

        if self.fast:
            kwargs["speed"] = "fast"
        try:
            r = self.client.beta.messages.create(**kwargs)
        except self.anthropic.RateLimitError:
            if not self.fast:
                raise
            kwargs.pop("speed")  # hızlı modun ayrı limiti doldu: normal hızla dene
            r = self.client.beta.messages.create(**kwargs)
        try:
            tracker.add(getattr(r, "model", self.model), getattr(r, "usage", None))
        except Exception:  # noqa: BLE001
            log.exception("Harcama hesaplanamadı")
        return r

    def chat(self, system: str, turns: list[tuple[str, str]], image: bytes | None = None) -> str:
        """Yardım sohbeti (yardimci.py): rehber bağlamıyla serbest cevap."""
        from .yardimci import to_messages
        kwargs = dict(model=self.model, max_tokens=1500, system=[{"type": "text", "text": system}],
                      messages=to_messages(turns, image, claude=True), output_config={"effort": "medium"})
        fast, self.fast = self.fast, False
        try:
            r = self._create(kwargs)
        finally:
            self.fast = fast
        return "".join(getattr(b, "text", "") for b in r.content if getattr(b, "type", "") == "text")

    def read_screen(self, jpeg: bytes, regions: list[tuple[int, str]]) -> list[dict]:
        """Ekran görüntüsündeki yazıları Claude okusun ve çevirsin (tam ekran çeviri için)."""
        import base64
        import json

        listing = "\n".join(f"{i}: {t}" for i, t in regions) or "(OCR found no text regions)"
        kwargs = dict(
            model=self.model,
            max_tokens=8000,
            system=self.screen_system,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                             "data": base64.standard_b64encode(jpeg).decode("ascii")}},
                {"type": "text", "text": f"OCR regions (id: text as read by OCR):\n{listing}"},
            ]}],
            output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": SCREEN_SCHEMA}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        r = self._create(kwargs)
        if r.stop_reason == "refusal":
            return []
        text = next((b.text for b in r.content if b.type == "text"), "")
        return json.loads(text).get("items", []) if text else []

    def translate(self, text: str, kind: str = "", context=None) -> str | None:
        r = self._request(text, kind, context or [])
        if r.stop_reason == "refusal":
            log.info("Claude bu satırı çevirmeyi reddetti, hızlı çeviri ekranda kalıyor")
            return None
        out = "".join(b.text for b in r.content if b.type == "text").strip()
        return out.removeprefix("<text>").removesuffix("</text>").strip() or None


class GeminiMT:
    """Google Gemini (ücretsiz anahtar: aistudio.google.com/apikey). SDK'sız, düz HTTP ile: kuruluma ek paket gerekmez."""

    name = "gemini"
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, cfg: CeviriCfg):
        import requests

        key = cfg.gemini_anahtar or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
        self.s = requests.Session()
        self.s.headers.update({"x-goog-api-key": key, "Content-Type": "application/json"})
        self.models = list(dict.fromkeys([cfg.gemini_model, "gemini-flash-latest", "gemini-2.5-flash"]))
        self.system = SYSTEM_PROMPT.format(glossary=_glossary_text(cfg.sozluk))
        self.screen_system = SCREEN_PROMPT.format(glossary=_glossary_text(cfg.sozluk))
        self.thinking_off = True

    def _call(self, body: dict, timeout: float = 8) -> str | None:
        """generateContent; eskimiş model adında sıradakine, düşünme ayarını tanımayan modelde ayarsız geçer."""
        for _ in range(len(self.models) + 1):
            gen = body.setdefault("generationConfig", {})
            if self.thinking_off:
                gen["thinkingConfig"] = {"thinkingBudget": 0}
            else:
                gen.pop("thinkingConfig", None)
            r = self.s.post(self.URL.format(model=self.models[0]), json=body, timeout=timeout)
            if r.status_code == 404 and len(self.models) > 1:
                log.warning("Gemini modeli bulunamadı (%s), %s deneniyor", self.models[0], self.models[1])
                self.models.pop(0)
                continue
            if r.status_code == 400 and self.thinking_off and "thinking" in r.text.lower():
                self.thinking_off = False
                continue
            r.raise_for_status()
            cands = r.json().get("candidates") or []
            parts = (cands[0].get("content") or {}).get("parts") or [] if cands else []
            return "".join(p.get("text", "") for p in parts).strip() or None
        return None

    def chat(self, system: str, turns: list[tuple[str, str]], image: bytes | None = None) -> str:
        import base64
        contents = []
        for k, (q, a) in enumerate(turns):
            parts = [{"text": q}]
            if image and k == len(turns) - 1:
                parts.insert(0, {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(image).decode()}})
            contents.append({"role": "user", "parts": parts})
            if a:
                contents.append({"role": "model", "parts": [{"text": a}]})
        body = {"system_instruction": {"parts": [{"text": system}]}, "contents": contents,
                "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1500}}
        return self._call(body, timeout=40) or ""

    def read_screen(self, jpeg: bytes, regions: list[tuple[int, str]]) -> list[dict]:
        """Ekran (ya da tuş simgeli satır) görüntüsünü Gemini okusun ve çevirsin (Claude'daki read_screen ile aynı)."""
        import base64
        import json

        listing = "\n".join(f"{i}: {t}" for i, t in regions) or "(OCR found no text regions)"
        schema = {"type": "object", "properties": {"items": {"type": "array", "items": {
            "type": "object", "properties": {"id": {"type": "integer"}, "english": {"type": "string"},
                                             "turkish": {"type": "string"},
                                             "box": {"type": "array", "items": {"type": "integer"}}},
            "required": ["id", "english", "turkish", "box"]}}}, "required": ["items"]}
        body = {"systemInstruction": {"parts": [{"text": self.screen_system}]},
                "contents": [{"role": "user", "parts": [
                    {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(jpeg).decode("ascii")}},
                    {"text": f"OCR regions (id: text as read by OCR):\n{listing}"}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096,
                                     "responseMimeType": "application/json", "responseSchema": schema}}
        text = self._call(body, timeout=20)
        if not text:
            return []
        try:
            return json.loads(text).get("items", [])
        except ValueError:
            log.warning("Gemini ekran yanıtı okunamadı: %s", text[:200])
            return []

    def _body(self, text: str, kind: str, context) -> dict:  # noqa: ANN001
        gen = {"temperature": 0.3, "maxOutputTokens": 512}
        if self.thinking_off:
            gen["thinkingConfig"] = {"thinkingBudget": 0}
        return {"systemInstruction": {"parts": [{"text": self.system}]},
                "contents": [{"role": "user", "parts": [{"text": _user_message(text, kind, context or [])}]}],
                "generationConfig": gen}

    def translate(self, text: str, kind: str = "", context=None) -> str | None:
        return self._call(self._body(text, kind, context))


class LocalAIMT:
    """Bilgisayarda çalışan yapay zekâ (Ollama, LM Studio ya da başka bir OpenAI uyumlu sunucu): ücretsiz, internetsiz.
    (Fikir CouchSubs'ın 'Yerel model' seçeneğinden.)"""

    name = "yerelai"

    def __init__(self, cfg: CeviriCfg):
        import requests

        self.url = cfg.yerelai_adres.rstrip("/") + "/chat/completions"
        self.model = cfg.yerelai_model
        self.s = requests.Session()
        if cfg.yerelai_anahtar:
            self.s.headers["Authorization"] = f"Bearer {cfg.yerelai_anahtar}"
        self.system = SYSTEM_PROMPT.format(glossary=_glossary_text(cfg.sozluk))

    def chat(self, system: str, turns: list[tuple[str, str]], image: bytes | None = None) -> str:
        from .yardimci import to_messages
        body = {"model": self.model, "temperature": 0.4, "stream": False, "max_tokens": 1500,
                "messages": [{"role": "system", "content": system}, *to_messages(turns, image, claude=False)]}
        r = self.s.post(self.url, json=body, timeout=90)
        r.raise_for_status()
        out = (r.json()["choices"][0]["message"].get("content") or "").strip()
        return re.sub(r"<think>.*?</think>", "", out, flags=re.S).strip()

    def translate(self, text: str, kind: str = "", context=None) -> str | None:
        body = {"model": self.model, "temperature": 0.3, "stream": False, "max_tokens": 512,
                "messages": [{"role": "system", "content": self.system},
                             {"role": "user", "content": _user_message(text, kind, context or [])}]}
        r = self.s.post(self.url, json=body, timeout=15)
        r.raise_for_status()
        out = (r.json()["choices"][0]["message"].get("content") or "").strip()
        out = re.sub(r"<think>.*?</think>", "", out, flags=re.S).strip()   # düşünen modellerin iç sesi
        return out or None


class DeepLMT:
    name = "deepl"

    def __init__(self, cfg: CeviriCfg):
        import requests

        self.key = cfg.deepl_anahtar
        host = "api-free.deepl.com" if self.key.endswith(":fx") else "api.deepl.com"
        self.url = f"https://{host}/v2/translate"
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"DeepL-Auth-Key {self.key}"

    def translate(self, text: str, kind: str = "", context=None) -> str | None:
        data = {"text": [text], "source_lang": "EN", "target_lang": "TR"}
        if context:
            data["context"] = " ".join(en for en, _ in context)
        r = self.s.post(self.url, json=data, timeout=5)
        r.raise_for_status()
        return r.json()["translations"][0]["text"].strip() or None


# --------------------------------------------------------------------------- motor
class TranslationEngine:
    def __init__(self, cfg: CeviriCfg):
        self.cfg = cfg
        from . import paths
        self.cache = Cache(str(paths.data(cfg.onbellek)) if not Path(cfg.onbellek).is_absolute() else cfg.onbellek,
                           cfg.benzerlik)
        from .packs import PackLibrary
        self.packs = PackLibrary(paths.data("paketler"), paths.resource("paketler"))
        self.fast = self._make_fast(cfg)
        self.refine = self._make_refine(cfg)
        self.fast_pool = ThreadPoolExecutor(4, thread_name_prefix="hizli")
        self.refine_pool = ThreadPoolExecutor(4, thread_name_prefix="kalite")
        self.context: deque[tuple[str, str]] = deque(maxlen=max(0, cfg.baglam_satir))
        self.ctx_lock = threading.Lock()
        # Oynanan oyunun paketi (oyun/oyun_algi.py tanır); bulanık arama yalnız onda yapılır (Nino gibi).
        # Oyun bilinmiyorsa GTA 6 paketi (bu programın asıl oyunu).
        self.local_chain = None
        if self.fast is not None and self.fast.name == "yerel":
            try:                                  # Nino'nun yerel çeviri kalite zinciri (kalite/yerel_cevirmen.py)
                from .gta_terms import KEEP
                from .kalite.yerel_cevirmen import QualityLocal
                self.local_chain = QualityLocal.build(self.fast.translate, cfg.sozluk, KEEP, user_dir=paths.data("sozluk"),
                                                      slang=slang.normalize if cfg.argo_duzelt else None)
            except Exception:  # noqa: BLE001
                log.exception("Yerel çeviri kalite zinciri kurulamadı; düz çeviri kullanılacak")
        self.game_pack: str | None = None
        self._fuzzy: dict[str, object] = {}
        self._fuzzy_loading: set[str] = set()
        self.script = None                 # oyun metni (altyazi/oyun_metni.py): indirildiyse okuma düzeltmesi
        self.load_script()

    def load_script(self) -> None:
        """Oyun metni dizini indirilmiş ve açıksa yüklenir (indirmeden sonra da çağrılır)."""
        self.script = None
        if not getattr(self.cfg, "oyun_metni", True):
            return
        try:
            from .oyun_metni import ScriptIndex, default_path
            p = default_path()
            if p.exists():
                self.script = ScriptIndex(p)
                log.info("Oyun metni yüklendi: %d satır", self.script.count)
        except Exception as e:  # noqa: BLE001
            log.warning("Oyun metni açılamadı: %s", e)

    def snap(self, text: str) -> str:
        """Okunan satır oyunun gerçek satırına çok benziyorsa o satır (konuşan adı korunur); değilse aynısı.
        Başka bir oyun oynanıyorsa (oyun paketi GTA 6'nınki değil) dokunulmaz."""
        sc = self.script
        if sc is None or not text:
            return text
        if self.game_pack is not None:
            from .oyun.oyun_algi import pack_for_game
            from .oyun_metni import GAME
            if self.game_pack != pack_for_game(GAME, self.packs.packs):
                return text
        try:
            from .kalite import konusan
            sp = konusan.split(text)
            body = sp.body if sp else text
            fixed = sc.snap(body)
        except Exception:  # noqa: BLE001
            log.exception("Oyun metni araması")
            return text
        if not fixed:
            return text
        log.debug("Okuma düzeltildi: %r -> %r", body, fixed)
        return text[: len(text) - len(body)] + fixed if sp and text.endswith(body) else fixed

    @staticmethod
    def _make_fast(cfg: CeviriCfg):
        try:
            if cfg.hizli == "yerel":
                m = LocalMT(cfg.yerel_model, cfg.yerel_cihaz, cfg.yerel_beam, getattr(cfg, "yerel_is_parcacigi", 0))
                m.translate("Warm up the engine.")
                return m
            if cfg.hizli == "google":
                return GoogleFree()
        except Exception as e:  # noqa: BLE001
            log.error("Hızlı çeviri katmanı açılamadı (%s). Sadece kalite katmanı kullanılacak.", e)
        return None

    @staticmethod
    def _make_refine(cfg: CeviriCfg):
        makers = {"claude": ClaudeMT, "gemini": GeminiMT, "deepl": DeepLMT, "yerelai": LocalAIMT}
        if cfg.kalite not in makers:
            return None
        has_key = {
            "claude": bool(cfg.claude_anahtar or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")),
            "gemini": bool(cfg.gemini_anahtar or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
            "deepl": bool(cfg.deepl_anahtar),
            "yerelai": bool(cfg.yerelai_adres and cfg.yerelai_model),
        }[cfg.kalite]
        if not has_key:
            log.info("Kalite katmanı (%s) için anahtar girilmedi; sadece hızlı katman kullanılacak", cfg.kalite)
            return None
        try:
            return makers[cfg.kalite](cfg)
        except Exception as e:  # noqa: BLE001
            log.error("Kalite katmanı (%s) açılamadı: %s", cfg.kalite, e)
            return None

    def _post(self, text: str) -> str:
        for k, v in self.cfg.sozluk.items():
            text = text.replace(k, v) if k != v else text
        return text

    def _remember(self, kind: str, en: str, tr: str) -> None:
        if kind == "altyazi" and self.context.maxlen:
            with self.ctx_lock:
                if self.context and self.context[-1][0] == en:
                    self.context[-1] = (en, tr)
                else:
                    self.context.append((en, tr))

    @property
    def can_read_screen(self) -> bool:
        return self.refine is not None and hasattr(self.refine, "read_screen")

    @property
    def can_read_images(self) -> bool:
        """Kalite katmanı resim okuyabiliyor mu (Claude): tuş simgeli satırlar için."""
        return self.refine is not None and hasattr(self.refine, "read_screen")

    def submit_image(self, text: str, jpeg: bytes, kind: str, on_result: Callable[[Result], None]) -> None:
        """OCR'ın tuş simgesini okuyamadığı satır ("Press [△] to enter"): satırın küçük resmini Claude okur ve simgeyi
        çeviride korur ("Binmek için △ tuşuna bas"). Aynı satır önbellekten gelir; Claude'a bir kez sorulur."""
        t0 = time.perf_counter()
        hit = self.cache.get(text)
        if hit:
            on_result(Result(hit[0], f"önbellek/{hit[2]}", (time.perf_counter() - t0) * 1000, hit[1]))
            return

        def run() -> None:
            try:
                items = self.refine.read_screen(jpeg, [])
            except Exception as e:  # noqa: BLE001
                log.warning("Tuş simgeli satır okunamadı: %s", e)
                return
            tr = " ".join(str(i.get("turkish") or "").strip() for i in items if i.get("turkish")).strip()
            if not tr:
                return
            self.cache.put(text, tr, REFINED, "claude-görsel")
            self._remember(kind, text, tr)
            on_result(Result(tr, "claude-görsel", (time.perf_counter() - t0) * 1000, REFINED))

        self.refine_pool.submit(run)

    def _fuzzy_pack(self):  # noqa: ANN202
        """Oyunun paketinin bulanık araması (Nino PackFuzzy): ilk istekte arka planda yüklenir, hazır olana kadar None."""
        pid = self.game_pack
        if pid is None:
            from .oyun.oyun_algi import pack_for_game
            pid = pack_for_game("Grand Theft Auto VI", self.packs.packs)
        if not pid:
            return None
        fz = self._fuzzy.get(pid)
        if fz is not None or pid in self._fuzzy_loading:
            return fz
        pack = next((pk for pk in self.packs.packs if pk.id == pid), None)
        if pack is None:
            return None
        self._fuzzy_loading.add(pid)

        def load() -> None:
            try:
                from .oyun.paket_bulanik import FuzzyPack
                t0 = time.perf_counter()
                self._fuzzy[pid] = FuzzyPack.load(pack.path)
                log.info("Bulanık paket araması hazır: %s (%.1f sn)", pid, time.perf_counter() - t0)
            except Exception as e:  # noqa: BLE001
                log.warning("Bulanık paket yüklenemedi (%s): %s", pid, e)
        threading.Thread(target=load, daemon=True, name="bulanik-paket").start()
        return None

    def pack_lookup(self, text: str) -> tuple[str, str] | None:
        """Hazır paket: önce tam anahtar, sonra oyunun paketinde bulanık arama (OCR'ın bir iki harf hatası)."""
        if not getattr(getattr(self, "cfg", None), "paket_kullan", True):
            return None
        hit = self.packs.lookup(text)
        if hit:
            return hit
        fz = self._fuzzy_pack()
        if fz is not None:
            try:
                tr = fz.match(text)
            except Exception:  # noqa: BLE001
                log.exception("Bulanık paket araması")
                tr = None
            if tr:
                return tr, f"{fz.id}~"
        return None

    def _local_quality(self, text: str) -> str | None:
        if self.local_chain is None:
            return None
        try:
            return self.local_chain.translate(text) or None
        except Exception:  # noqa: BLE001
            log.exception("Yerel çeviri kalite zinciri")
            return None

    def _refine_text(self, text: str, kind: str, ctx) -> str | None:  # noqa: ANN001
        """Yapay zekâ çevirisi: konuşan adı ("LUCIA: ...") modele gitmez, sonra geri eklenir; model cümleyi
        çevirmeden geri verdiyse (yankı) sonuç yok sayılır (Nino AITranslation)."""
        from .kalite import konusan
        from .kalite.metin_eslesme import is_similar, normalize
        sp = konusan.split(text)
        body = sp.body if sp else text
        tr = self.refine.translate(body, kind, ctx)
        if not tr:
            return None
        if len(body) > 12 and is_similar(normalize(body), normalize(tr), 0.90):
            log.info("Yapay zekâ çevirmeden geri verdi, yok sayıldı: %s", body[:60])
            return None
        return konusan.present(tr, text, bool(getattr(getattr(self, "cfg", None), "konusan_goster", True))) if sp else tr

    def lookup(self, text: str) -> str | None:
        """Hazır paket ya da önbellekteki kaliteli çeviri (beklemeden); yoksa None."""
        hit = self.pack_lookup(text)
        if hit:
            return hit[0]
        cached = self.cache.get(text)
        return cached[0] if cached and cached[1] >= REFINED else None

    def translate_now(self, text: str, kind: str = "arayuz", context=None) -> str | None:  # noqa: ANN001
        """Bekleyerek çevir (ekran yazıları için, arka plan iş parçacığında): paket → önbellek → kalite → hızlı."""
        text = self.snap(text)
        found = self.lookup(text)
        if found:
            return found
        if self.refine:
            try:
                tr = self._refine_text(text, kind, context or [])
            except Exception as e:  # noqa: BLE001
                log.warning("%s çeviri hatası: %s", self.refine.name, e)
                tr = None
            if tr:
                tr = self._post(tr)
                self.cache.put(text, tr, REFINED, self.refine.name)
                return tr
        cached = self.cache.get(text)
        if cached:
            return cached[0]
        if self.fast:
            try:
                tr = self._local_quality(text) or \
                    self._post(self.fast.translate(slang.normalize(text) if self.cfg.argo_duzelt else text))
            except Exception as e:  # noqa: BLE001
                log.warning("Hızlı çeviri hatası: %s", e)
                return None
            self.cache.put(text, tr, FAST, self.fast.name)
            return tr
        return None

    def submit(self, text: str, kind: str, on_result: Callable[[Result], None], refine: bool = True) -> None:
        """Sonuçlar on_result ile (başka iş parçacığından) gelir: önce hızlı, sonra kaliteli."""
        t0 = time.perf_counter()
        text = self.snap(text)               # oyun metniyle okuma hatası düzeltilir (indirildiyse)
        pack_hit = self.pack_lookup(text)
        if pack_hit:                         # hazır paket: anında, ücretsiz, yapay zekaya sorulmaz
            tr, pack_id = pack_hit
            on_result(Result(tr, f"paket/{pack_id}", (time.perf_counter() - t0) * 1000, REFINED))
            self._remember(kind, text, tr)
            return
        hit = self.cache.get(text)
        if hit:
            tr, q, engine = hit
            on_result(Result(tr, f"önbellek/{engine}", (time.perf_counter() - t0) * 1000, q))
            self._remember(kind, text, tr)
            if q >= REFINED or not self.refine or not refine:
                return
            if refine:
                self._schedule_refine(text, kind, on_result)
            return
        race = None
        if self.fast and self.refine and refine and self.cfg.kalite_bekleme_ms > 0:
            race = _Race(t0 + self.cfg.kalite_bekleme_ms / 1000)
        if self.fast:
            self.fast_pool.submit(self._run_fast, text, kind, on_result, race)
        if refine:
            self._schedule_refine(text, kind, on_result, race)

    def _run_fast(self, text: str, kind: str, on_result, race: _Race | None = None) -> None:
        t = time.perf_counter()
        try:
            src = slang.normalize(text) if self.cfg.argo_duzelt else text
            tr = self._local_quality(text)
            if tr is None and self.fast.name == "yerel" and self.cfg.sozluk:
                protected, mapping = terms.protect(src, self.cfg.sozluk)
                if mapping:
                    tr = terms.restore(self.fast.translate(protected), mapping)
            if tr is None:
                tr = self._post(self.fast.translate(src))
        except Exception as e:  # noqa: BLE001
            log.warning("Hızlı çeviri hatası: %s", e)
            return
        ms = (time.perf_counter() - t) * 1000
        self.cache.put(text, tr, FAST, self.fast.name)
        self._remember(kind, text, tr)
        if race is not None:
            remaining = race.deadline - time.perf_counter()
            if remaining > 0:
                race.done.wait(remaining)
            if race.refined_ok:
                return                      # kaliteli çeviri zamanında geldi, hızlıyı hiç gösterme
        on_result(Result(tr, self.fast.name, ms, FAST))

    def _schedule_refine(self, text: str, kind: str, on_result, race: _Race | None = None) -> None:
        if not self.refine:
            return
        with self.ctx_lock:
            ctx = [c for c in self.context if c[0] != text] if kind == "altyazi" else []
        self.refine_pool.submit(self._run_refine, text, kind, ctx, on_result, race)

    def _run_refine(self, text: str, kind: str, ctx, on_result, race: _Race | None = None) -> None:
        t = time.perf_counter()
        tr = None
        try:
            tr = self._refine_text(text, kind, ctx)
        except Exception as e:  # noqa: BLE001
            log.warning("%s çeviri hatası: %s", self.refine.name, e)
        if not tr:
            if race is not None:
                race.done.set()             # kaliteli çeviri yok: hızlı olan hemen gösterilsin
            return
        tr = self._post(tr)
        ms = (time.perf_counter() - t) * 1000
        self.cache.put(text, tr, REFINED, self.refine.name)
        self._remember(kind, text, tr)
        if race is not None:
            race.refined_ok = True
            race.done.set()
        on_result(Result(tr, self.refine.name, ms, REFINED))
