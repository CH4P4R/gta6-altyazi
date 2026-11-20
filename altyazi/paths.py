"""Dosya yolları. Kurulu (.exe) sürümde kaynaklar paketin içinden, kullanıcı verisi %APPDATA%'dan gelir."""

from __future__ import annotations

import os
import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)

# Paketle gelen dosyalar (config.yaml varsayılanları, modeller, TV APK'sı, adb)
RESOURCES = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def data_dir() -> Path:
    """Kullanıcıya ait ayarlar, önbellek, anahtarlar, kayıt dosyası."""
    if os.environ.get("ALTYAZI_DATA"):
        d = Path(os.environ["ALTYAZI_DATA"])
    elif sys.platform == "win32":
        d = Path(os.environ.get("APPDATA", Path.home())) / "GTA6Altyazi"
    elif sys.platform == "darwin":
        d = Path.home() / "Library" / "Application Support" / "GTA6Altyazi"
    else:
        d = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "gta6altyazi"
    d.mkdir(parents=True, exist_ok=True)
    return d


def default_config() -> Path:
    return RESOURCES / "config.yaml"


def user_config() -> Path:
    return data_dir() / "config.yaml"


def resource(rel: str) -> Path:
    return RESOURCES / rel


def data(rel: str) -> Path:
    return data_dir() / rel


def model_path(rel: str) -> Path:
    """Göreli model yollarını önce kullanıcı klasöründe, sonra paket içinde ara."""
    p = Path(rel)
    if p.is_absolute():
        return p
    for base in (data_dir(), RESOURCES, Path.cwd()):
        if (base / p).exists():
            return base / p
    return RESOURCES / p
