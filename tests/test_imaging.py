import io

import pytest
from PIL import Image

from fxocr.core.imaging import ImageRejected, sanitize, sniff

LIMITS = dict(max_bytes=10 * 1024 * 1024, max_pixels=40_000_000, max_side=4000)


def _img_bytes(fmt: str, size=(64, 32), mode="RGB", color=(255, 255, 255), **save) -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, color).save(buf, format=fmt, **save)
    return buf.getvalue()


@pytest.mark.parametrize("fmt,kind", [("JPEG", "jpeg"), ("PNG", "png"), ("WEBP", "webp")])
def test_sniff_and_sanitize_allowed(tmp_path, fmt, kind):
    data = _img_bytes(fmt)
    assert sniff(data[:32]) == kind
    out = tmp_path / "o.png"
    assert sanitize(data, out, **LIMITS) == (64, 32)
    with Image.open(out) as im:
        assert im.format == "PNG" and im.mode == "RGB"


@pytest.mark.parametrize("data", [
    b"",
    b"GIF89a" + b"\0" * 64,
    b"%PDF-1.7\n" + b"\0" * 64,
    b"PK\x03\x04" + b"\0" * 64,          # zip / docx / apk
    b"MZ" + b"\0" * 64,                  # windows exe
    b"\x7fELF" + b"\0" * 64,
    b"<html><script>alert(1)</script>",
    b"<svg xmlns='http://www.w3.org/2000/svg'/>",
])
def test_rejects_non_images(tmp_path, data):
    with pytest.raises(ImageRejected) as e:
        sanitize(data, tmp_path / "o.png", **LIMITS)
    assert e.value.code in ("empty", "unsupported_type")


def test_heif_gets_specific_code(tmp_path):
    data = b"\0\0\0\x18ftypheic" + b"\0" * 64
    with pytest.raises(ImageRejected) as e:
        sanitize(data, tmp_path / "o.png", **LIMITS)
    assert e.value.code == "heif"


def test_png_magic_with_garbage_is_corrupt(tmp_path):
    data = b"\x89PNG\r\n\x1a\n" + b"\xde\xad\xbe\xef" * 100
    with pytest.raises(ImageRejected) as e:
        sanitize(data, tmp_path / "o.png", **LIMITS)
    assert e.value.code == "corrupt"


def test_truncated_jpeg_is_corrupt(tmp_path):
    data = _img_bytes("JPEG", size=(800, 600))[:400]
    with pytest.raises(ImageRejected) as e:
        sanitize(data, tmp_path / "o.png", **LIMITS)
    assert e.value.code == "corrupt"


def test_decompression_bomb_rejected_before_decode(tmp_path):
    # 10000x10000 1-bit PNG: tiny on disk, 100 MP decoded.
    data = _img_bytes("PNG", size=(10_000, 10_000), mode="1", color=0)
    assert len(data) < 1_000_000
    with pytest.raises(ImageRejected) as e:
        sanitize(data, tmp_path / "o.png", **LIMITS)
    assert e.value.code == "too_many_pixels"


def test_too_large_file(tmp_path):
    data = _img_bytes("PNG") + b"\0" * 2048
    with pytest.raises(ImageRejected) as e:
        sanitize(data, tmp_path / "o.png", max_bytes=1024, max_pixels=40_000_000, max_side=4000)
    assert e.value.code == "too_large"


def test_polyglot_trailing_payload_is_dropped(tmp_path):
    payload = b"PK\x03\x04EVIL-ZIP-PAYLOAD<script>x</script>"
    data = _img_bytes("PNG") + payload
    out = tmp_path / "o.png"
    sanitize(data, out, **LIMITS)
    assert payload not in out.read_bytes()


def test_metadata_stripped(tmp_path):
    im = Image.new("RGB", (64, 32), "white")
    exif = im.getexif()
    exif[0x010E] = "SECRET-DESCRIPTION"  # ImageDescription
    buf = io.BytesIO()
    im.save(buf, format="JPEG", exif=exif.tobytes())
    out = tmp_path / "o.png"
    sanitize(buf.getvalue(), out, **LIMITS)
    raw = out.read_bytes()
    assert b"SECRET-DESCRIPTION" not in raw and b"eXIf" not in raw


def test_transparent_png_flattened_onto_white(tmp_path):
    data = _img_bytes("PNG", mode="RGBA", color=(0, 0, 0, 0))
    out = tmp_path / "o.png"
    sanitize(data, out, **LIMITS)
    with Image.open(out) as im:
        assert im.getpixel((0, 0)) == (255, 255, 255)


def test_downscaled_to_max_side(tmp_path):
    data = _img_bytes("PNG", size=(5000, 1000))
    out = tmp_path / "o.png"
    w, h = sanitize(data, out, max_bytes=10 * 1024 * 1024, max_pixels=40_000_000, max_side=2000)
    assert max(w, h) == 2000


def test_extension_disguise_is_irrelevant():
    # A JPEG is a JPEG whatever it's called; an exe named .png is still rejected (by magic).
    assert sniff(_img_bytes("JPEG")[:32]) == "jpeg"
    assert sniff(b"MZ\x90\x00" + b"\0" * 28) is None
