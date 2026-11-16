"""Ayar dosyası (config.yaml) okuma. Eksik alanlar varsayılanlarla doldurulur."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints

import yaml

log = logging.getLogger(__name__)


@dataclass
class BolgeCfg:
    """Ekranda okunacak bir bölge (altyazı, sol üst yardım kutusu, sağ üst bildirim...)."""
    ad: str = "altyazi"
    # [x0, y0, x1, y1] - görüntünün oranı olarak (0-1)
    alan: list[float] = field(default_factory=lambda: [0.12, 0.78, 0.88, 0.97])
    tur: str = "altyazi"          # altyazi | arayuz  (çeviri üslubu ve bağlam)
    hizalama: str = "orta"        # orta | sol | sag
    capa: str = "alt"             # alt | ust  (Türkçe metin uzarsa kutu hangi yöne büyüsün)
    # Metin pikseli: beyaz (tüm kanallar >= beyaz_min ve renk farkı <= doygunluk_max)
    beyaz_min: int = 180
    doygunluk_max: int = 60
    # GTA'daki sarı/mavi/yeşil vurgulu kelimeler için renkli piksel de say
    renkli: bool = True
    renk_min: int = 170
    renk_fark_min: int = 70
    # Metnin etrafında koyu kontur/gölge/kutu olmasını şart koş (gökyüzü, beyaz duvar gibi yanlış alarmları eler)
    cerceve: bool = True
    koyu_max: int = 90
    cerceve_yaricap: int = 3
    min_piksel: int = 60          # bundan az metin pikseli = bölge boş
    degisim_esigi: float = 0.15   # maske ne kadar değişirse "yeni metin" sayılır
    sabit_kare: int = 0           # 0 = metin değiştiği kare OCR'a gider (en hızlı)
    silme_ms: int = 200           # metin kaybolduktan sonra çeviriyi bu kadar ms sonra kaldır
    min_skor: float = 0.55        # OCR güveni bunun altındaysa gösterme
    min_satir_yuksekligi: int = 10
    kutu_opaklik: int = 255       # İngilizceyi kapatan kutunun opaklığı (0-255)
    yazi_olcek: float = 1.0


@dataclass
class KaynakCfg:
    tur: str = "pencere"          # pencere | capture | video | resim
    pencere_adi: str = "chiaki"   # başlıkta geçen metin (ör. "chiaki", "PS Remote Play")
    capture_cihaz: int = 0
    capture_genislik: int = 1920
    capture_yukseklik: int = 1080
    capture_fps: int = 60
    capture_ses: bool = True      # capture kartın sesini hoparlöre aktar
    capture_ses_cihaz: str = ""   # boşsa adında capture kartın adı geçen giriş aranır
    dosya: str = ""               # video/resim kaynağı için


@dataclass
class OcrCfg:
    gpu: bool = True
    model: str = ""               # boşsa paketteki PP-OCR tanıma modeli
    anahtar_dosyasi: str = ""


@dataclass
class CeviriCfg:
    # Hızlı katman: yerel model anında çevirir (ms'ler)
    hizli: str = "yerel"          # yerel | google | yok
    yerel_model: str = "models/opus-mt-en-tr"
    yerel_cihaz: str = "auto"     # auto | cuda | cpu
    yerel_beam: int = 2
    # Kalite katmanı: yapay zeka daha doğal çeviriyi gönderir, ekrandaki yazı güncellenir
    kalite: str = "claude"        # claude | gemini | deepl | yok
    claude_model: str = "claude-opus-5-5"
    claude_hizli_mod: bool = True  # Opus 5.5 "fast mode": ~2.5 kat hızlı üretim (2 kat fiyat)
    claude_efor: str = "low"
    gemini_model: str = "gemini-2.5-flash"
    gemini_anahtar: str = ""
    deepl_anahtar: str = ""
    baglam_satir: int = 6         # yapay zekaya verilen önceki diyalog satırı sayısı
    onbellek: str = "cache.sqlite"
    benzerlik: int = 92           # OCR küçük hata yapsa da önbellekten bulmak için (0-100)
    sozluk: dict[str, str] = field(default_factory=dict)  # zorunlu terimler: "Vice City": "Vice City"


@dataclass
class GosterimCfg:
    # overlay: oyun penceresinin üstüne şeffaf katman (chiaki / Remote Play)
    # pencere: görüntüyü kendi penceresinde Türkçe yazıyla birlikte gösterir (capture kart)
    mod: str = "overlay"
    yazi_tipi: str = "Segoe UI Semibold"
    gecikme_goster: bool = True   # köşede ms cinsinden gecikme
    tam_ekran: bool = False


@dataclass
class SunucuCfg:
    acik: bool = True
    port: int = 8787


@dataclass
class TvCfg:
    ip: str = ""                  # Google/Android TV'nin adresi ("python -m altyazi tv bul")
    otomatik: bool = True         # program açılınca TV uygulamasını kendiliğinden başlat
    # TV ekranı oyun görüntüsünü kırpıyor/kaydırıyorsa (overscan): [x, y, genişlik, yükseklik] oran
    kalibrasyon: list[float] = field(default_factory=lambda: [0.0, 0.0, 1.0, 1.0])


@dataclass
class Config:
    kaynak: KaynakCfg = field(default_factory=KaynakCfg)
    bolgeler: list[BolgeCfg] = field(default_factory=lambda: [BolgeCfg()])
    ocr: OcrCfg = field(default_factory=OcrCfg)
    ceviri: CeviriCfg = field(default_factory=CeviriCfg)
    gosterim: GosterimCfg = field(default_factory=GosterimCfg)
    sunucu: SunucuCfg = field(default_factory=SunucuCfg)
    tv: TvCfg = field(default_factory=TvCfg)


def _build(cls, data: Any, path: str):
    if not is_dataclass(cls):
        return data
    if data is None:
        return cls()
    if not isinstance(data, dict):
        raise ValueError(f"{path}: sözlük bekleniyordu")
    hints = get_type_hints(cls)
    known = {f.name for f in fields(cls)}
    for k in data:
        if k not in known:
            log.warning("Bilinmeyen ayar: %s.%s (yok sayıldı)", path, k)
    kwargs = {}
    for f in fields(cls):
        if f.name not in data:
            continue
        t, v = hints[f.name], data[f.name]
        if get_origin(t) is list and is_dataclass(get_args(t)[0]):
            v = [_build(get_args(t)[0], x, f"{path}.{f.name}[{i}]") for i, x in enumerate(v or [])]
        elif is_dataclass(t):
            v = _build(t, v, f"{path}.{f.name}")
        kwargs[f.name] = v
    return cls(**kwargs)


def load(path: str | Path = "config.yaml") -> Config:
    p = Path(path)
    if not p.exists():
        log.warning("%s bulunamadı, varsayılan ayarlar kullanılıyor", p)
        return Config()
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    local = p.with_name("config.local.yaml")  # kişisel anahtarlar için, git'e girmez
    if local.exists():
        _merge(data, yaml.safe_load(local.read_text(encoding="utf-8")) or {})
    return _build(Config, data, "config")


def _merge(base: dict, extra: dict) -> None:
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
