"""Ayar dosyası (config.yaml) okuma. Eksik alanlar varsayılanlarla doldurulur."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field, fields, is_dataclass
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
    # Aynı bölgedeki ayrı yazılar (ör. altta "Arabaya git" görev yazısı, üstünde diyalog): satırlar arası boşluk
    # satır yüksekliğinin bu katından büyükse ayrı paragraf sayılır, ayrı çevrilir ve kendi yerine basılır
    paragraf_boslugu: float = 0.45
    min_skor: float = 0.55        # OCR güveni bunun altındaysa gösterme
    min_satir_yuksekligi: int = 10
    kutu_opaklik: int = 255       # İngilizceyi kapatan kutunun opaklığı (0-255)
    yazi_olcek: float = 1.3       # Türkçe yazı İngilizceden ne kadar büyük olsun (alttakini bastırsın)
    aktif: bool = True            # kapalı bölge okunmaz (Okuma alanı › Ek alanlar)


@dataclass
class KaynakCfg:
    tur: str = "pencere"          # pencere | remoteplay (yerleşik, chiaki penceresi gerekmez) | capture | video | resim
    pencere_adi: str = "chiaki"   # başlıkta geçen metin (ör. "chiaki", "PS Remote Play")
    chiaki_yolu: str = ""         # chiaki-ng programının yeri (boşsa bilinen yerlerde aranır)
    oyun_yeri: str = "tv"         # tv (TV'de oynar, kasa izler) | monitor (chiaki ile kasada oynar) | ikisi
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
    # otomatik: Mac'te Apple Vision (Neural Engine; kendini sınar, okuyamazsa PP-OCR), diğerlerinde PP-OCR
    motor: str = "otomatik"       # otomatik | vision | ppocr
    sik_oku: bool = False         # değişmeyen altyazı alanını da saniyede bir yeniden oku (ilk okuma bozuksa düzelir)
    # CouchSubs: bozuk / yarım okunan satır çevrilmeden önce daha iyi okuma için en çok bu kadar beklenir (0 = beklemez;
    # bizde varsayılan beklemeden göstermek, daha iyi okuma gelince yerinde düzeltmektir)
    bozuk_bekleme_ms: int = 0
    yarim_bekleme_ms: int = 0
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
    kalite: str = "claude"        # claude | gemini | deepl | yerelai | yok
    claude_anahtar: str = ""      # boşsa ANTHROPIC_API_KEY ortam değişkeni kullanılır
    claude_model: str = "claude-opus-5-5"
    claude_hizli_mod: bool = True  # Opus 5.5 "fast mode": ~2.5 kat hızlı üretim (2 kat fiyat)
    claude_efor: str = "low"
    gemini_model: str = "gemini-2.5-flash"   # bulunamazsa gemini-flash-latest denenir
    gemini_anahtar: str = ""      # ücretsiz: aistudio.google.com/apikey
    deepl_anahtar: str = ""       # ücretsiz plan anahtarı ":fx" ile biter
    # Yerel yapay zekâ (Ollama / LM Studio, OpenAI uyumlu sunucu): anahtar, kota ve ücret yok
    yerelai_adres: str = "http://localhost:11434/v1"
    yerelai_model: str = "qwen2.5:7b"
    yerelai_anahtar: str = ""
    baglam_satir: int = 6         # yapay zekaya verilen önceki diyalog satırı sayısı
    argo_duzelt: bool = True      # yerel modele vermeden önce sokak dilini düzgün İngilizceye çevir
    kalite_bekleme_ms: int = 350  # kaliteli çeviri bu süre içinde gelirse yerel çeviri hiç gösterilmez (0 = kapalı)
    onbellek: str = "cache.sqlite"
    benzerlik: int = 92           # OCR küçük hata yapsa da önbellekten bulmak için (0-100)
    sozluk: dict[str, str] = field(default_factory=dict)  # zorunlu terimler: "Vice City": "Vice City"
    ekran_yazilari: bool = True     # telefon, harita görev kartı ve telefona gelen mesajlar kendiliğinden çevrilsin (Nino)
    # Telefondaki mesajların Türkçesi: ust (her balonun tam üstünde, balonun renginde; telefon Türkçe görünür) | yan
    # (telefonun yanında ayrı panelde)
    telefon_yeri: str = "yan"
    konusan_goster: bool = True     # konuşanın adı çevirinin başında kalsın ("LUCIA: Gitmeliyiz."); ad çevrilmez
    oyun_sor: bool = True           # oyun paketle tanınmazsa iki dakika sonra "Hangi oyunu oynuyorsun?" diye sor
    paket_kullan: bool = True       # hazır oyun paketlerinde olan satır çevirmene gitmeden gelsin
    yerel_is_parcacigi: int = 0     # yerel modelin işlemcide kullanacağı çekirdek sayısı (0 = kendiliğinden)
    # GTA 6'nın İngilizce metni (kullanıcı indirir): okunan satır oyunun gerçek satırına çok benziyorsa düzeltilir
    oyun_metni: bool = True


@dataclass
class GosterimCfg:
    # overlay: oyun penceresinin üstüne şeffaf katman (chiaki / Remote Play)
    # pencere: görüntüyü kendi penceresinde Türkçe yazıyla birlikte gösterir (capture kart)
    mod: str = "overlay"
    yazi_tipi: str = "Segoe UI Semibold"
    gecikme_goster: bool = True   # köşede ms cinsinden gecikme
    tam_ekran: bool = False
    seslendir: bool = False       # altyazının Türkçesini sesli oku (dublaj; oyunun konuşma sesini kısmak gerekir)
    ses_hizi: int = 10            # konuşma hızı (yüzde, -50 … +50)
    tema: str = "koyu"            # koyu | acik (programın görünümü; yeniden açınca geçer)
    ana_ekran: str = "fis"        # fis: TV-sehpa-PS5 sahnesi, fişi prize sürükle | dugme: TV önizlemesi + kaydırmalı düğme


@dataclass
class ObsCfg:
    """OBS / yayın için ayrı altyazı görünümü (http://localhost:8787/obs). TV ve bilgisayar katmanını etkilemez."""
    gorunum: str = "ust"       # ust: oyunun İngilizcesinin tam üstünde (kutuyla örter) | serit: altyazı şeridi
    yazi_tipi: str = "modern"  # aksiyon | modern | yuvarlak | sade
    boyut: int = 100           # yazı boyu (%)
    renk: str = "#ffffff"      # yazı rengi
    kontur: bool = True        # yazının çevresinde siyah çizgi
    kutu: int = 85             # yazının arkasındaki kutunun koyuluğu (%; 0 = kutusuz)
    konum: str = "alt"         # şerit: alt | ust
    bosluk: int = 6            # şerit: ekranın kenarından uzaklık (yüksekliğin %'si)

    def style(self) -> dict:
        return {"gorunum": self.gorunum, "yazi_tipi": self.yazi_tipi, "boyut": max(50, min(250, int(self.boyut))),
                "renk": self.renk, "kontur": bool(self.kontur), "kutu": max(0, min(100, int(self.kutu))),
                "konum": self.konum, "bosluk": max(0, min(40, int(self.bosluk)))}


@dataclass
class HavuzCfg:
    """Ortak çeviri havuzu (kendi sunucumuz)."""
    acik: bool = True          # havuzu kullan
    adres: str = ""            # boş: GTA6 Altyazı'nın sunucusu (altyazi/havuz.py DEFAULT_URL); başka sunucu için adres
    gonder: bool = True        # yapay zekânın çevirdiği satırları havuza gönder (İngilizce + Türkçe, kişisel bilgi yok)
    al: bool = True            # havuzun paketini indir (herkesin çevirdiği satırlar ücretsiz)
    kimlik: str = ""           # rastgele kurulum kimliği (ilk açılışta üretilir)


@dataclass
class SunucuCfg:
    acik: bool = True
    port: int = 8787


@dataclass
class KisayolCfg:
    tam_ekran: str = "ctrl+shift+9"   # ekrandaki her şeyi çevir (telefon, menü, harita)
    duraklat: str = "ctrl+shift+0"    # çeviriyi duraklat / devam ettir
    tam_ekran_sure: int = 20          # tam ekran çeviri kaç saniye ekranda kalsın
    tam_ekran_gorsel: bool = True     # Claude anahtarı varsa ekran görüntüsünü Claude okusun (daha doğru, 2-4 sn)
    # Her işin ikinci kısayolu (CouchSubs: sayı tuş takımı olmayan klavyeler için ikisi birden)
    tam_ekran2: str = "num9"
    duraklat2: str = "num0"
    baslat: str = "ctrl+shift+8"      # çeviriyi başlat / durdur
    baslat2: str = "num8"
    seslendir: str = "ctrl+shift+7"   # Türkçe seslendirmeyi aç / kapat
    seslendir2: str = "num7"
    tv_deneme: str = "ctrl+shift+6"   # TV'ye deneme altyazısı gönder
    tv_deneme2: str = "num6"
    alan_duzenle: str = "ctrl+shift+5"   # okuma alanlarını oyun görüntüsünün üstünde fareyle düzenle
    alan_duzenle2: str = "num5"


@dataclass
class OtomatikCfg:
    """TV günleri için: kasada kimse yokken her şey kendiliğinden çalışsın."""
    windows_ile_baslat: bool = False   # bilgisayar açılınca uygulama simge durumunda açılsın
    chiaki_gorunce_baslat: bool = True  # chiaki penceresi açılınca çeviri başlasın, kapanınca dursun
    ps5_acilinca_baglan: bool = False  # PS5 açılınca chiaki kendiliğinden bağlansın
    chiaki_tam_ekran: bool = True      # otomatik bağlanınca chiaki tam ekran açılsın
    paket_guncelle: bool = True        # açılışta hazır paketlerin (GTA 6 dahil) yenisini sessizce indir
    surum_denetle: bool = True         # açılışta uygulamanın yeni sürümü var mı bak
    ps5_adi: str = ""                  # chiaki'de kayıtlı PS5 adı (ör. PS5-123); "PS5'i bul" doldurur
    ps5_ip: str = ""


@dataclass
class Ps5Cfg:
    """Yerleşik Remote Play: PS5 görüntüsü ikinci PSN hesabıyla arka planda alınır (chiaki penceresi gerekmez)."""
    ip: str = ""
    ad: str = ""                  # PS5'in adı (eşlemede PS5 verir)
    anahtar: str = ""             # eşleme anahtarı (onaltılık, 16 bayt)
    morning: str = ""             # eşlemenin ikinci anahtarı (onaltılık, 16 bayt)
    hesap: str = ""               # ikinci PSN hesabının kimliği (base64, 8 bayt)
    giris_sifresi: str = ""       # PS5 bu hesap için giriş şifresi istiyorsa 4 hane
    acilinca_baslat: bool = True  # PS5 açılınca çeviri kendiliğinden başlasın (TV günleri)


@dataclass
class TvCfg:
    marka: str = "android"        # android (Google TV, TCL, Sony...) | lg (webOS) | samsung (Tizen)
    ip: str = ""                  # TV'nin adresi
    lg_parola: str = ""           # LG Developer Mode ekranındaki parola (passphrase)
    samsung_profil: str = "gta6"  # Gelişmiş: Tizen Studio'daki Samsung sertifika profilinin adı
    tizen_yolu: str = ""          # Gelişmiş: Tizen Studio klasörü. Boşsa Tizen Studio'suz doğrudan kurulur
    otomatik: bool = True         # program açılınca TV uygulamasını kendiliğinden başlat
    # otomatik: TV izin verirse oyunun üstüne katman, vermezse yedek mod (HDMI uygulama içinde)
    mod: str = "otomatik"         # otomatik | katman | hdmi
    # TV ekranı oyun görüntüsünü kırpıyor/kaydırıyorsa (overscan): [x, y, genişlik, yükseklik] oran
    kalibrasyon: list[float] = field(default_factory=lambda: [0.0, 0.0, 1.0, 1.0])
    # TV'deki altyazının görünümü (Ayarlar › Altyazı görünümü; TV uygulamasına 'style' olarak gider)
    yerlesim: str = "cover"       # cover (İngilizcenin üstünü örter) | above | below | fixed (sabit, alttan yüzde)
    yazi_boyutu: int = 58         # sabit yerleşimde yazı boyu (px, 1080p'ye göre)
    yazi_rengi: str = "white"     # white | yellow | cyan | green | orange
    kalin: bool = True
    onceki_satirlar: bool = True  # hızlı konuşmada önceki satırlar üstte kalsın
    alttan: int = 7               # sabit yerleşimde alttan uzaklık (yüzde)
    zemin_sekli: str = "fit"      # fit (yazı kadar) | band (tam genişlik bant)
    yazi_tipi: str = "yuvarlak"   # yuvarlak (Nunito, okunaklı) | aksiyon (Barlow, GTA tarzı)
    uydur: bool = True            # boyut oyunun altyazısına uysun (kapalıysa sabit yazı boyutu)
    konusan_renk: bool = False    # her konuşanın adı ve satırı kendi renginde
    logo: bool = False            # sol alt köşede küçük GTA6 Altyazı logosu (yayın / ekran görüntüsü için)


@dataclass
class Config:
    kaynak: KaynakCfg = field(default_factory=KaynakCfg)
    bolgeler: list[BolgeCfg] = field(default_factory=lambda: [BolgeCfg()])
    ocr: OcrCfg = field(default_factory=OcrCfg)
    ceviri: CeviriCfg = field(default_factory=CeviriCfg)
    gosterim: GosterimCfg = field(default_factory=GosterimCfg)
    sunucu: SunucuCfg = field(default_factory=SunucuCfg)
    tv: TvCfg = field(default_factory=TvCfg)
    kisayol: KisayolCfg = field(default_factory=KisayolCfg)
    otomatik: OtomatikCfg = field(default_factory=OtomatikCfg)
    ps5: Ps5Cfg = field(default_factory=Ps5Cfg)
    havuz: HavuzCfg = field(default_factory=HavuzCfg)
    obs: ObsCfg = field(default_factory=ObsCfg)
    gocler: list[str] = field(default_factory=list)   # uygulanmış ayar göçleri (yeni sürümün getirdiği varsayılanlar)


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


def load(path: str | Path | None = None) -> Config:
    """Ayarları katman katman yükle: varsayılanlar < paketteki config.yaml < kullanıcı ayarları < config.local.yaml.

    path verilirse (komut satırı -c) kullanıcı ayarları yerine o dosya kullanılır.
    """
    from . import paths

    data: dict = {}
    layers = [paths.default_config()]
    if path is not None and Path(path).resolve() != paths.default_config().resolve():
        layers.append(Path(path))
    elif path is None:
        layers.append(paths.user_config())
    for p in layers:
        p = Path(p)
        if p.exists():
            _merge(data, yaml.safe_load(p.read_text(encoding="utf-8")) or {})
    local = Path(layers[-1]).with_name("config.local.yaml")
    if local.exists():
        _merge(data, yaml.safe_load(local.read_text(encoding="utf-8")) or {})
    cfg = _build(Config, data, "config")
    _migrate(cfg)
    if path is None:
        _restore_keys(cfg)
    log.info("Anahtarlar: %s", ", ".join(f"{k.split('_')[0]} {'var' if getattr(cfg.ceviri, k) else 'yok'}"
                                         for k in KEY_FIELDS))
    return cfg


KEY_FIELDS = ("claude_anahtar", "gemini_anahtar", "deepl_anahtar", "yerelai_anahtar")


def _vault() -> Path:
    from . import paths
    return paths.data("anahtarlar.yaml")


def _read_keys(p: Path) -> dict:
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    data = data.get("ceviri", data) if isinstance(data, dict) else {}
    return {k: str(data.get(k) or "") for k in KEY_FIELDS if isinstance(data, dict)}


def _restore_keys(cfg: Config) -> None:
    """Ayar dosyasında anahtar boşsa ama yedekte varsa geri koy (güncellemede anahtar kaybolmasın)."""
    saved = _read_keys(_vault())
    for k in KEY_FIELDS:
        if not getattr(cfg.ceviri, k, "") and saved.get(k):
            setattr(cfg.ceviri, k, saved[k])
            log.warning("%s ayar dosyasında yoktu; yedekten geri yüklendi", k)


def _migrate(cfg: Config) -> None:
    """Kaydedilmiş ayarları olan kullanıcıya yeni sürümün getirdiği varsayılanları bir kez ekle."""
    if "telefon-alani" not in cfg.gocler:
        cfg.gocler.append("telefon-alani")
        if not any(b.ad == "telefon" for b in cfg.bolgeler) and any(b.ad == "bildirim" for b in cfg.bolgeler):
            cfg.bolgeler.append(BolgeCfg(ad="telefon", alan=[0.66, 0.33, 1.0, 0.78], tur="altyazi", hizalama="sag",
                                         capa="ust", silme_ms=400))
    if "tv-remoteplay" not in cfg.gocler:
        # TV'de oynayan ve PS5'i eşlemiş biri chiaki penceresi beklemesin: görüntü arka planda PS5'ten gelsin
        cfg.gocler.append("tv-remoteplay")
        if cfg.kaynak.oyun_yeri == "tv" and cfg.kaynak.tur == "pencere" and cfg.ps5.anahtar:
            cfg.kaynak.tur = "remoteplay"
    if "yardim-asagi" not in cfg.gocler:
        # GTA 6'nın yardım kutusu köşede değil biraz aşağıda; eski alan (y ≤ 0.32) son satırı kesiyordu
        cfg.gocler.append("yardim-asagi")
        for b in cfg.bolgeler:
            if b.ad == "yardim" and [round(float(v), 2) for v in b.alan] == [0.0, 0.0, 0.36, 0.32]:
                b.alan = [0.0, 0.0, 0.36, 0.50]


def to_dict(cfg) -> dict:  # noqa: ANN001
    return asdict(cfg)


def save(cfg: Config, path: str | Path | None = None, explicit_keys: bool = False) -> Path:
    """Kullanıcı ayarlarını yaz (arayüzden yapılan değişiklikler).

    Anahtarlar korunur: boş anahtar, dosyadaki dolu anahtarın üstüne yalnız kullanıcı anahtar alanını kendisi
    boşalttıysa (explicit_keys) yazılır. Anahtarlar ayrıca anahtarlar.yaml'a yedeklenir.
    """
    from . import paths

    p = Path(path) if path else paths.user_config()
    p.parent.mkdir(parents=True, exist_ok=True)
    if path is None:
        old = _read_keys(p)
        vault = _read_keys(_vault())
        for k in KEY_FIELDS:
            if not getattr(cfg.ceviri, k, "") and not explicit_keys and (old.get(k) or vault.get(k)):
                setattr(cfg.ceviri, k, old.get(k) or vault.get(k))
                log.warning("%s boş kaydedilmek üzereydi; eski anahtar korundu", k)
        try:
            keys = {k: getattr(cfg.ceviri, k, "") for k in KEY_FIELDS}
            v = _vault()
            tmpv = v.with_suffix(".tmp")
            tmpv.write_text(yaml.safe_dump(keys, allow_unicode=True), encoding="utf-8")
            tmpv.replace(v)
        except OSError as e:
            log.warning("Anahtar yedeği yazılamadı: %s", e)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(yaml.safe_dump(to_dict(cfg), allow_unicode=True, sort_keys=False), encoding="utf-8")
    tmp.replace(p)
    return p


def is_first_run() -> bool:
    from . import paths

    return not paths.user_config().exists()


def _merge(base: dict, extra: dict) -> None:
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
