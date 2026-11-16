# -*- mode: python ; coding: utf-8 -*-
# PyInstaller tarifi: pyinstaller packaging/gta6altyazi.spec  (depo kökünden)
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
IS_WIN = sys.platform == "win32"

datas = [(str(ROOT / "config.yaml"), "."), (str(ROOT / "LICENSE"), "."), (str(ROOT / "NOTICE"), ".")]
for rel in ("tv-android/release", "tv-web/release", "tv-web/build/tizen", "models/opus-mt-en-tr", "models/ocr",
            "tools/platform-tools"):
    p = ROOT / rel
    if p.exists():
        datas.append((str(p), rel))
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

hidden = collect_submodules("anthropic") + collect_submodules("paramiko") + [
    "sounddevice", "segno", "rapidfuzz.fuzz", "rapidfuzz.process"]
if IS_WIN:
    hidden += ["windows_capture"]

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
