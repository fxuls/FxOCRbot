"""End-to-end through the sandboxed worker (needs liteparse; tesseract engine needs no model pull)."""

import asyncio
import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from fxocr.core.config import CoreConfig
from fxocr.core.runner import ocr_image_bytes

CFG = CoreConfig(engine="tesseract", timeout_s=60)


def _text_png(text: str) -> bytes:
    im = Image.new("RGB", (900, 120), "white")
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 48)
    except OSError:
        font = ImageFont.load_default(size=48)
    ImageDraw.Draw(im).text((20, 30), text, fill="black", font=font)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_reads_text():
    r = asyncio.run(ocr_image_bytes(_text_png("HELLO FXOCR 2026"), CFG))
    assert r.ok, r.error
    assert "HELLO" in r.text.upper()


@pytest.mark.parametrize("data,code", [
    (b"%PDF-1.7 not an image", "unsupported_type"),
    (b"\x89PNG\r\n\x1a\n" + b"\x00" * 500, "corrupt"),
])
def test_hostile_inputs_fail_cleanly(data, code):
    r = asyncio.run(ocr_image_bytes(data, CFG))
    assert not r.ok and r.error == code


def test_oversize_rejected_without_spawning():
    cfg = CoreConfig(engine="tesseract", max_file_bytes=1024)
    r = asyncio.run(ocr_image_bytes(b"\xff\xd8\xff" + b"\0" * 4096, cfg))
    assert r.error == "too_large"


def test_worker_does_not_receive_bot_token(monkeypatch):
    from fxocr.core.runner import _worker_env
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:secret")
    assert "TELEGRAM_BOT_TOKEN" not in _worker_env(CFG)
