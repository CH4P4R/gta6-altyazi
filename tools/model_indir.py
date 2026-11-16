"""Yerel çeviri modelini indirip CTranslate2 biçimine dönüştürür (bir kere çalıştırılır).

    python tools/model_indir.py

Dönüştürme için geçici olarak transformers + torch gerekir (~2 GB). Bittikten sonra
uygulama sadece ctranslate2 + sentencepiece kullanır.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT = "Helsinki-NLP/opus-mt-tc-big-en-tr"


def main() -> int:
    for stream in (sys.stdout, sys.stderr):   # Windows konsolunda Türkçe karakterler
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT)
    ap.add_argument("--cikti", default="models/opus-mt-en-tr")
    a = ap.parse_args()
    out = Path(a.cikti)

    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError:
        print("Dönüştürme araçları kuruluyor (transformers, torch CPU)...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "transformers", "sentencepiece",
                               "huggingface_hub", "torch", "--index-url", "https://download.pytorch.org/whl/cpu",
                               "--extra-index-url", "https://pypi.org/simple"])

    from ctranslate2.converters import TransformersConverter
    from huggingface_hub import hf_hub_download

    print(f"{a.model} indiriliyor ve dönüştürülüyor...")
    TransformersConverter(a.model).convert(str(out), quantization="int8_float16", force=True)
    for name in ("source.spm", "target.spm"):
        shutil.copy(hf_hub_download(a.model, name), out / name)

    import ctranslate2
    import sentencepiece as spm

    dev = "cuda" if ctranslate2.get_cuda_device_count() else "cpu"
    tr = ctranslate2.Translator(str(out), device=dev)
    sp_s = spm.SentencePieceProcessor(model_file=str(out / "source.spm"))
    sp_t = spm.SentencePieceProcessor(model_file=str(out / "target.spm"))
    toks = sp_s.encode("Get in the car, we're leaving now!", out_type=str) + ["</s>"]
    res = tr.translate_batch([toks])
    print("Deneme:", sp_t.decode(res[0].hypotheses[0]), f"({dev})")
    print(f"Hazır: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
