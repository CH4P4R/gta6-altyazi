"""Çeviri katmanları.

1. Önbellek (0 ms): daha önce görülen metin (OCR küçük hata yapsa bile benzerlikle bulunur).
2. Hızlı katman (~15-40 ms, GPU): yerel OPUS-MT modeli CTranslate2 ile. Ekrana hemen basılır.
3. Kalite katmanı (~0.4-1.5 sn): Claude / Gemini / DeepL. Gelince ekrandaki yazı güncellenir
   ve sonuç önbelleğe yazılır; aynı metin bir daha görülürse direkt kaliteli hali gelir.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import CeviriCfg

log = logging.getLogger(__name__)

FAST, REFINED = 1, 2


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
class Cache:
    def __init__(self, path: str, similarity: int):
        self.similarity = similarity
        self.lock = threading.Lock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS ceviri (anahtar TEXT PRIMARY KEY, kaynak TEXT,"
                        " ceviri TEXT, kalite INTEGER, motor TEXT, zaman REAL)")
        self.mem: dict[str, tuple[str, int, str]] = {
            k: (t, q, m) for k, t, q, m in self.db.execute("SELECT anahtar, ceviri, kalite, motor FROM ceviri")}
        self.keys = list(self.mem)
        log.info("Önbellek: %d çeviri yüklendi", len(self.mem))

    def get(self, text: str) -> tuple[str, int, str] | None:
        key = normalize(text)
        if not key:
            return None
        hit = self.mem.get(key)
        if hit or len(key) < 10 or not self.keys:
            return hit
        from rapidfuzz import fuzz, process
        with self.lock:
            m = process.extractOne(key, self.keys, scorer=fuzz.ratio, score_cutoff=self.similarity)
        return self.mem[m[0]] if m else None

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

    def __init__(self, path: str, device: str = "auto", beam: int = 2):
        import ctranslate2
        import sentencepiece as spm

        p = Path(path)
        if not (p / "model.bin").exists():
            raise FileNotFoundError(f"{p} içinde model yok. Önce: python tools/model_indir.py")
        if device == "auto":
            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        compute = "int8_float16" if device == "cuda" else "int8"
        self.tr = ctranslate2.Translator(str(p), device=device, compute_type=compute,
                                         inter_threads=2, intra_threads=0 if device == "cuda" else 4)
        self.sp_src = spm.SentencePieceProcessor(model_file=str(p / "source.spm"))
        self.sp_tgt = spm.SentencePieceProcessor(model_file=str(p / "target.spm"))
        self.beam = beam
        self.device = device
        log.info("Yerel çeviri modeli: %s (%s, %s)", p.name, device, compute)

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

Never translate proper names: characters, gangs, places, businesses, brands, vehicles, weapons and radio stations stay as they are (Jason, Lucia, Vice City, Leonida, Port Gellhorn, Ambrosia, Grassrivers, Mount Kalaga...). Add Turkish suffixes with an apostrophe (Lucia'yla, Vice City'de).

The English comes from OCR and may contain small recognition errors (l/I, missing apostrophes, stray characters). Silently translate what was obviously meant. If the input is not real language (OCR garbage), output it unchanged.{glossary}"""


def _glossary_text(sozluk: dict[str, str]) -> str:
    if not sozluk:
        return ""
    return "\n\nRequired terms (English -> Turkish):\n" + "\n".join(f"- {k} -> {v}" for k, v in sozluk.items())


def _user_message(text: str, kind: str, context: list[tuple[str, str]]) -> str:
    parts = []
    if context:
        parts.append("Previous dialogue lines, for context only (do not translate again):")
        parts += [f"EN: {en}\nTR: {tr}" for en, tr in context]
        parts.append("")
    parts.append(f"kind={'subtitle' if kind == 'altyazi' else 'ui'}")
    parts.append(f"<text>{text}</text>")
    return "\n".join(parts)


class ClaudeMT:
    name = "claude"

    def __init__(self, cfg: CeviriCfg):
        import anthropic

        self.anthropic = anthropic
        # Kimlik bilgisi ortamdan okunur: ANTHROPIC_API_KEY (ya da `ant auth login` profili)
        self.client = anthropic.Anthropic(max_retries=1, timeout=10.0)
        self.model = cfg.claude_model
        self.effort = cfg.claude_efor
        self.fast = cfg.claude_hizli_mod
        self.system = [{"type": "text", "text": SYSTEM_PROMPT.format(glossary=_glossary_text(cfg.sozluk)),
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
        if self.fast:
            kwargs["speed"] = "fast"
        try:
            return self.client.beta.messages.create(**kwargs)
        except self.anthropic.RateLimitError:
            if not self.fast:
                raise
            kwargs.pop("speed")  # hızlı modun ayrı limiti doldu: normal hızla dene
            return self.client.beta.messages.create(**kwargs)

    def translate(self, text: str, kind: str = "", context=None) -> str | None:
        r = self._request(text, kind, context or [])
        if r.stop_reason == "refusal":
            log.info("Claude bu satırı çevirmeyi reddetti, hızlı çeviri ekranda kalıyor")
            return None
        out = "".join(b.text for b in r.content if b.type == "text").strip()
        return out.removeprefix("<text>").removesuffix("</text>").strip() or None


class GeminiMT:
    name = "gemini"

    def __init__(self, cfg: CeviriCfg):
        from google import genai
        from google.genai import types

        self.types = types
        self.client = genai.Client(api_key=cfg.gemini_anahtar or None)
        self.model = cfg.gemini_model
        self.system = SYSTEM_PROMPT.format(glossary=_glossary_text(cfg.sozluk))

    def translate(self, text: str, kind: str = "", context=None) -> str | None:
        t = self.types
        r = self.client.models.generate_content(
            model=self.model,
            contents=_user_message(text, kind, context or []),
            config=t.GenerateContentConfig(system_instruction=self.system, temperature=0.3,
                                           thinking_config=t.ThinkingConfig(thinking_budget=0)),
        )
        return (r.text or "").strip() or None


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
        self.cache = Cache(cfg.onbellek, cfg.benzerlik)
        self.fast = self._make_fast(cfg)
        self.refine = self._make_refine(cfg)
        self.fast_pool = ThreadPoolExecutor(2, thread_name_prefix="hizli")
        self.refine_pool = ThreadPoolExecutor(4, thread_name_prefix="kalite")
        self.context: deque[tuple[str, str]] = deque(maxlen=max(0, cfg.baglam_satir))
        self.ctx_lock = threading.Lock()

    @staticmethod
    def _make_fast(cfg: CeviriCfg):
        try:
            if cfg.hizli == "yerel":
                m = LocalMT(cfg.yerel_model, cfg.yerel_cihaz, cfg.yerel_beam)
                m.translate("Warm up the engine.")
                return m
            if cfg.hizli == "google":
                return GoogleFree()
        except Exception as e:  # noqa: BLE001
            log.error("Hızlı çeviri katmanı açılamadı (%s). Sadece kalite katmanı kullanılacak.", e)
        return None

    @staticmethod
    def _make_refine(cfg: CeviriCfg):
        makers = {"claude": ClaudeMT, "gemini": GeminiMT, "deepl": DeepLMT}
        if cfg.kalite not in makers:
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

    def submit(self, text: str, kind: str, on_result: Callable[[Result], None]) -> None:
        """Sonuçlar on_result ile (başka iş parçacığından) gelir: önce hızlı, sonra kaliteli."""
        t0 = time.perf_counter()
        hit = self.cache.get(text)
        if hit:
            tr, q, engine = hit
            on_result(Result(tr, f"önbellek/{engine}", (time.perf_counter() - t0) * 1000, q))
            self._remember(kind, text, tr)
            if q >= REFINED or not self.refine:
                return
        elif self.fast:
            self.fast_pool.submit(self._run_fast, text, kind, on_result)
        self._schedule_refine(text, kind, on_result)

    def _run_fast(self, text: str, kind: str, on_result) -> None:
        t = time.perf_counter()
        try:
            tr = self._post(self.fast.translate(text))
        except Exception as e:  # noqa: BLE001
            log.warning("Hızlı çeviri hatası: %s", e)
            return
        ms = (time.perf_counter() - t) * 1000
        self.cache.put(text, tr, FAST, self.fast.name)
        self._remember(kind, text, tr)
        on_result(Result(tr, self.fast.name, ms, FAST))

    def _schedule_refine(self, text: str, kind: str, on_result) -> None:
        if not self.refine:
            return
        with self.ctx_lock:
            ctx = [c for c in self.context if c[0] != text] if kind == "altyazi" else []
        self.refine_pool.submit(self._run_refine, text, kind, ctx, on_result)

    def _run_refine(self, text: str, kind: str, ctx, on_result) -> None:
        t = time.perf_counter()
        try:
            tr = self.refine.translate(text, kind, ctx)
        except Exception as e:  # noqa: BLE001
            log.warning("%s çeviri hatası: %s", self.refine.name, e)
            return
        if not tr:
            return
        tr = self._post(tr)
        ms = (time.perf_counter() - t) * 1000
        self.cache.put(text, tr, REFINED, self.refine.name)
        self._remember(kind, text, tr)
        on_result(Result(tr, self.refine.name, ms, REFINED))
