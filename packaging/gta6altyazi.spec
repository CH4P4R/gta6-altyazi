# -*- mode: python ; coding: utf-8 -*-
# PyInstaller tarifi: pyinstaller packaging/gta6altyazi.spec  (depo kökünden)
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

datas = [(str(ROOT / "config.yaml"), "."), (str(ROOT / "LICENSE"), "."), (str(ROOT / "NOTICE"), ".")]
datas.append((str(ROOT / "altyazi" / "ui" / "rehber"), "altyazi/ui/rehber"))   # sihirbaz rehber görselleri
for rel in ("tv-android/release", "tv-web/release", "tv-web/build/tizen", "models/opus-mt-en-tr", "models/ocr",
            "tools/platform-tools", "paketler"):   # paketler: kuruluma gömülü hazır çeviri paketleri
    p = ROOT / rel
    if p.exists():
        datas.append((str(p), rel))
# Samsung'un geliştirici ara sertifikaları (Tizen Studio'suz Samsung kurulumu imzaya ekler)
datas.append((str(ROOT / "altyazi" / "samsung" / "ca"), "altyazi/samsung/ca"))
datas += collect_data_files("rapidocr_onnxruntime")      # OCR modelleri
binaries = collect_dynamic_libs("ctranslate2") + collect_dynamic_libs("onnxruntime")
if IS_WIN:
    binaries += collect_dynamic_libs("windows_capture")
    # NVIDIA cuBLAS: ctranslate2 GPU'da çeviri için ister; ctranslate2 klasörüne koy ki bulunsun
    try:
        import nvidia.cublas
        cublas = Path(list(nvidia.cublas.__path__)[0]) / "bin"
        binaries += [(str(f), "ctranslate2") for f in cublas.glob("*.dll")]
    except ImportError:
        print("UYARI: nvidia-cublas-cu12 yok, çeviri modeli CPU'da çalışacak")

# Yerleşik Remote Play (PS5'e chiaki penceresi olmadan bağlanma): CI'da native/ klasöründen derlenir
_rp = ROOT / "native" / "bin" / ("couchsubs_native.dll" if IS_WIN else "couchsubs_native.dylib")
if _rp.exists():
    binaries.append((str(_rp), "."))
elif os.environ.get("CI"):
    raise SystemExit(f"HATA: Remote Play kütüphanesi yok: {_rp}")
else:
    print(f"UYARI: Remote Play kütüphanesi yok ({_rp}); PS5'e arka planda bağlanma çalışmayacak")

hidden = collect_submodules("anthropic") + collect_submodules("paramiko") + collect_submodules("edge_tts") + [
    "sounddevice", "segno", "rapidfuzz.fuzz", "rapidfuzz.process", "edge_tts", "miniaudio"]
if IS_WIN:
    hidden += ["windows_capture"]
if IS_MAC:
    hidden += ["Quartz", "Vision", "AppKit", "Foundation", "ScreenCaptureKit", "CoreMedia", "ApplicationServices", "objc"]
    try:
        import libdispatch  # noqa: F401
        hidden += ["libdispatch"]
    except ImportError:
        pass

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    excludes=["torch", "transformers", "tkinter", "matplotlib", "IPython", "pytest", "PySide6.QtWebEngineCore",
              "PySide6.Qt3DCore", "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="GTA6Altyazi",
    console=False,
    icon=str(ROOT / "packaging" / "assets" / "icon.ico") if IS_WIN else None,
    version=None,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="GTA6Altyazi", upx=False)

if IS_MAC:
    import importlib.util
    spec_v = importlib.util.spec_from_file_location("v", ROOT / "altyazi" / "__init__.py")
    ver = importlib.util.module_from_spec(spec_v)
    spec_v.loader.exec_module(ver)
    app = BUNDLE(
        coll,
        name="GTA6 Altyazı.app",
        icon=str(ROOT / "packaging" / "assets" / "icon.icns"),
        bundle_identifier="com.gta6altyazi.app",
        version=ver.__version__,
        info_plist={
            "CFBundleDisplayName": "GTA6 Altyazı",
            "CFBundleShortVersionString": ver.__version__,
            "CFBundleVersion": ver.__version__,
            "LSMinimumSystemVersion": "13.0",
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.games",
            # İzin pencerelerinde görünen açıklamalar
            "NSCameraUsageDescription": "Capture kartından oyun görüntüsünü okumak için.",
            "NSMicrophoneUsageDescription": "Capture kartının oyun sesini hoparlöre aktarmak için.",
            "NSLocalNetworkUsageDescription": "TV uygulamasını kurmak ve Türkçe altyazıyı TV'ye ve telefona göndermek için.",
            "NSBonjourServices": ["_adb-tls-connect._tcp", "_adb-tls-pairing._tcp"],
            "NSAppleEventsUsageDescription": "Güvenlik duvarı izni için yönetici şifresini sormak üzere.",
        },
    )
