"""Claude harcama sayacı: her yanıtın bildirdiği token sayısından gerçek maliyeti hesaplar.

Claude her yanıtta kaç token okuduğunu/yazdığını (önbellekten okunanlar ayrı) bildirir; bunlar Anthropic'in
liste fiyatlarıyla çarpılır. Bu oturumun ve bu bilgisayardaki tüm zamanların toplamı tutulur (harcama.json).
Fatura ile kuruşu kuruşuna aynı olmayabilir (vergi, indirim, kur); kesin rakam console.anthropic.com'dadır.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)

# $ / 1 milyon token, standart hız: (girdi, çıktı, önbellekten okuma). Önbelleğe yazma = girdi × 1.25.
PRICES: dict[str, tuple[float, float, float]] = {
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-opus-5": (5.0, 25.0, 0.50),
    "claude-opus-4-8": (5.0, 25.0, 0.50),
    "claude-opus-4-7": (5.0, 25.0, 0.50),
    "claude-opus-4-6": (5.0, 25.0, 0.50),
    "claude-sonnet-5-5": (2.0, 10.0, 0.10),
    "claude-sonnet-5": (2.0, 10.0, 0.20),
    "claude-sonnet-4-6": (3.0, 15.0, 0.30),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    "claude-haiku-4-5": (1.0, 5.0, 0.10),
    "claude-fable-5-2": (8.0, 40.0, 0.20),
    "claude-fable-5-1": (10.0, 50.0, 1.00),
    "claude-fable-5": (10.0, 50.0, 1.00),
}
FAST_MULTIPLIER = 2.0          # hızlı mod (speed="fast") fiyatı standart hızın iki katı
CACHE_WRITE = 1.25


def _price(model: str) -> tuple[float, float, float]:
    model = (model or "").strip()
    if model in PRICES:
        return PRICES[model]
    for name in sorted(PRICES, key=len, reverse=True):     # "claude-opus-5-5-xyz" gibi ekli adlar
        if model.startswith(name):
            return PRICES[name]
    return PRICES["claude-opus-5-5"]


def _n(usage: Any, field: str) -> int:
    v = usage.get(field) if isinstance(usage, dict) else getattr(usage, field, None)
    return int(v or 0)


def cost(model: str, usage: Any) -> float:
    """Bir yanıtın dolar maliyeti (usage: SDK'nın Usage nesnesi ya da aynı alanları taşıyan sözlük)."""
    if usage is None:
        return 0.0
    inp, out, read = _price(model)
    speed = usage.get("speed") if isinstance(usage, dict) else getattr(usage, "speed", None)
    mult = FAST_MULTIPLIER if str(speed or "").lower().endswith("fast") else 1.0
    total = (_n(usage, "input_tokens") * inp
             + _n(usage, "cache_creation_input_tokens") * inp * CACHE_WRITE
             + _n(usage, "cache_read_input_tokens") * read
             + _n(usage, "output_tokens") * out)
    return total / 1_000_000 * mult


class Spend:
    """İş parçacığı güvenli sayaç; değişince dinleyiciyi çağırır."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.path: Path | None = None
        self.session = 0.0
        self.requests = 0
        self.total = 0.0
        self.months: dict[str, float] = {}
        self.started: float | None = None
        self.listener: Callable[[], None] | None = None
        self._dirty_since = 0.0

    def load(self, path: str | Path) -> None:
        self.path = Path(path)
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.total = float(data.get("toplam", 0.0))
            self.months = {str(k): float(v) for k, v in (data.get("aylar") or {}).items()}
        except FileNotFoundError:
            pass
        except Exception as e:  # noqa: BLE001
            log.warning("Harcama dosyası okunamadı: %s", e)

    def add(self, model: str, usage: Any) -> float:
        c = cost(model, usage)
        if c <= 0:
            return 0.0
        month = time.strftime("%Y-%m")
        with self.lock:
            if self.started is None:
                self.started = time.monotonic()
            self.session += c
            self.requests += 1
            self.total += c
            self.months[month] = self.months.get(month, 0.0) + c
            save = time.monotonic() - self._dirty_since > 5     # diske en fazla 5 saniyede bir
            if save:
                self._dirty_since = time.monotonic()
        if save:
            self.save()
        if self.listener:
            try:
                self.listener()
            except Exception:  # noqa: BLE001
                log.exception("Harcama dinleyicisi hata verdi")
        return c

    def save(self) -> None:
        if not self.path:
            return
        with self.lock:
            data = {"toplam": round(self.total, 6), "aylar": {k: round(v, 6) for k, v in self.months.items()}}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
            tmp.replace(self.path)
        except Exception as e:  # noqa: BLE001
            log.warning("Harcama dosyası yazılamadı: %s", e)

    def hourly(self) -> float | None:
        """Bu oturumun saatlik ortalaması (ilk ücretli çeviriden beri); 5 dakikadan önce None."""
        with self.lock:
            if self.started is None:
                return None
            hours = (time.monotonic() - self.started) / 3600
            return self.session / hours if hours >= 5 / 60 else None

    def month(self) -> float:
        with self.lock:
            return self.months.get(time.strftime("%Y-%m"), 0.0)


def money(v: float) -> str:
    """0.374 → '0,37 $'; 1 sentten azsa '0,4¢' gibi."""
    if 0 < v < 0.01:
        return f"{v * 100:.1f}".replace(".", ",") + "¢"
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " $"


tracker = Spend()
