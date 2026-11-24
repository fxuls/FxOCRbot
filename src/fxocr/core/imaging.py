"""Untrusted-image handling: identify by magic bytes, bound the decode, re-encode clean.

Only call `sanitize` inside the resource-limited worker (see runner.py). The output is a fresh
RGB PNG with no metadata, so the OCR engine never parses attacker-controlled bytes.
"""

from __future__ import annotations

import io
import warnings
from pathlib import Path

from PIL import Image, ImageOps

# Pillow format names we accept, keyed by our own kind label.
ALLOWED = {"jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}


class ImageRejected(Exception):
    """Input refused. `code` is stable and safe to show/map to a user message."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def sniff(head: bytes) -> str | None:
    """Return the image kind from leading magic bytes, or None. Never trust names/MIME types."""
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if len(head) >= 12 and head[4:8] == b"ftyp" and head[8:12] in (
        b"heic", b"heix", b"hevc", b"heim", b"heis", b"mif1", b"msf1", b"avif",
    ):
        return "heif"  # recognised so we can give a helpful message, but not accepted
    return None


def sanitize(data: bytes, out_path: Path, *, max_bytes: int, max_pixels: int, max_side: int) -> tuple[int, int]:
    """Validate `data` and write a clean RGB PNG to `out_path`. Returns the output (w, h)."""
    if not data:
        raise ImageRejected("empty")
    if len(data) > max_bytes:
        raise ImageRejected("too_large", f"{len(data)} bytes")

    kind = sniff(data[:32])
    if kind == "heif":
        raise ImageRejected("heif")
    if kind not in ALLOWED:
        raise ImageRejected("unsupported_type")

    # Pillow warns at MAX_IMAGE_PIXELS and raises at 2x; we check ourselves before decoding and
    # also turn the warning into an error as a second line of defence.
    Image.MAX_IMAGE_PIXELS = max_pixels
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            im = Image.open(io.BytesIO(data), formats=[ALLOWED[kind]])
            if im.format != ALLOWED[kind]:
                raise ImageRejected("unsupported_type", f"pillow saw {im.format}")
            w, h = im.size
            if w <= 0 or h <= 0:
                raise ImageRejected("corrupt", "zero size")
            if w * h > max_pixels:
                raise ImageRejected("too_many_pixels", f"{w}x{h}")
            im.seek(0)  # animated WEBP/APNG: first frame only
            im.load()
            im = ImageOps.exif_transpose(im)
            clean = _to_rgb(im)
        except ImageRejected:
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise ImageRejected("too_many_pixels", str(exc)) from exc
        except Exception as exc:  # truncated/corrupt/hostile file: one opaque code
            raise ImageRejected("corrupt", type(exc).__name__) from exc

    if max(clean.size) > max_side:
        clean.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

    # Brand-new image, no info/exif/icc carried over.
    fresh = Image.new("RGB", clean.size)
    fresh.paste(clean)
    fresh.save(out_path, format="PNG", optimize=False)
    return fresh.size


def _to_rgb(im: Image.Image) -> Image.Image:
    """Flatten alpha onto white (dark text on transparency would otherwise turn black-on-black)."""
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        rgba = im.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.getchannel("A"))
        return bg
    return im.convert("RGB")
