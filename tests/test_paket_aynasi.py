"""Paket aynası: GameTranslator'ın BOM'lu düz sözlük paketi uygulamanın biçimine çevrilir."""

import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import paket_aynasi  # noqa: E402

from altyazi.packs import key, load  # noqa: E402


def test_flat_bom_pack_is_converted(tmp_path):
    flat = {"Press any button to continue": "Devam etmek için herhangi bir tuşa basın", "Empty": " "}
    raw = b"\xef\xbb\xbf" + json.dumps(flat, ensure_ascii=False).encode("utf-8")
    gz = paket_aynasi.without_bom(gzip.compress(raw), "final-fantasy-vii-rebirth")
    assert paket_aynasi.entries_of(gz) == ("Final Fantasy VII Rebirth", 1)
    path = tmp_path / "final-fantasy-vii-rebirth.json.gz"
    path.write_bytes(gz)
    pack = load(path)
    assert pack.entries[key("Press any button to continue")] == "Devam etmek için herhangi bir tuşa basın"


def test_normal_pack_untouched():
    d = {"title": "X", "entries": {"0123456789abcdef": "Merhaba"}}
    gz = gzip.compress(json.dumps(d).encode("utf-8"))
    assert paket_aynasi.without_bom(gz, "x") == gz


def test_merge_prefers_first_pack():
    gt = {"title": "Grand Theft Auto VI", "entries": {"aaaaaaaaaaaaaaaa": "GT", "bbbbbbbbbbbbbbbb": "GT2"}}
    cs = {"title": "GTA 6", "version": 7, "entries": {"aaaaaaaaaaaaaaaa": "CS", "cccccccccccccccc": "CS3"},
          "segments": {"dddddddddddddddd": "parça"}}
    gz = paket_aynasi.merged(gzip.compress(json.dumps(gt).encode()), gzip.compress(json.dumps(cs).encode()))
    d = json.loads(gzip.decompress(gz))
    assert d["entries"] == {"aaaaaaaaaaaaaaaa": "GT", "bbbbbbbbbbbbbbbb": "GT2", "cccccccccccccccc": "CS3"}
    assert d["segments"] == {"dddddddddddddddd": "parça"} and d["title"] == "Grand Theft Auto VI"
    assert paket_aynasi.entries_of(gz) == ("Grand Theft Auto VI", 4)
