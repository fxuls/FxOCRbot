import asyncio
import json

from fxocr.bot.prefs import Prefs
from fxocr.core.config import CoreConfig
from fxocr.core.engine import boxes_to_text
from fxocr.core.engines import ENGINES, is_available
from fxocr.core.runner import ocr_image_bytes


def test_registry_ids():
    assert set(ENGINES) == {"ocria-nano", "ppocr", "tesseract"}
    assert is_available("tesseract") and not is_available("nope")


def test_prefs_roundtrip_and_validation(tmp_path):
    p = tmp_path / "prefs.json"
    pr = Prefs(p)
    assert pr.engine_for(1, "tesseract") == "tesseract"
    pr.set_engine(1, "ppocr")
    assert Prefs(p).engine_for(1, "tesseract") == "ppocr"
    try:
        pr.set_engine(1, "../../etc/passwd")
        assert False
    except ValueError:
        pass


def test_prefs_ignores_tampered_file(tmp_path):
    p = tmp_path / "prefs.json"
    p.write_text(json.dumps({"engine": {"1": "evil", "2": "ppocr", "3": 5}}))
    pr = Prefs(p)
    assert pr.engine_for(1, "tesseract") == "tesseract"
    assert pr.engine_for(2, "tesseract") == "ppocr"
    p.write_text("{not json")
    assert Prefs(p).engine_for(2, "tesseract") == "tesseract"


def test_prefs_unwritable_dir_falls_back_to_memory(tmp_path):
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o500)
    pr = Prefs(ro / "sub" / "prefs.json")
    pr.set_engine(7, "ppocr")
    assert pr.engine_for(7, "tesseract") == "ppocr"


def test_boxes_to_text_rows_and_columns():
    items = [
        (300, 360, 10, 30, "Qty"), (10, 80, 12, 30, "Item"),     # same row, out of order
        (10, 200, 50, 70, "Seagate"), (300, 312, 51, 69, "2"),
    ]
    assert boxes_to_text(items).splitlines() == ["Item    Qty", "Seagate    2"]


def test_unknown_engine_rejected():
    r = asyncio.run(ocr_image_bytes(b"\xff\xd8\xff", CoreConfig(), engine="rm -rf"))
    assert r.error == "bad_engine"


def test_ppocr_reads_text():
    from tests.test_runner import _text_png
    r = asyncio.run(ocr_image_bytes(_text_png("HELLO FXOCR 2026"), CoreConfig(), engine="ppocr"))
    assert r.ok, r.error
    assert "HELLO" in r.text.upper() and r.engine == "ppocr"
