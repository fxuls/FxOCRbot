"""User-facing text. Kept in one place so the bot's name/branding can change without code edits.

Messages are sent as Telegram HTML. Anything derived from user input or OCR output MUST be passed
through html.escape before being placed in these templates.
"""

from __future__ import annotations

import html

from fxocr import APP_NAME
from fxocr.core.engines import EngineInfo

SUPPORTED = "JPEG, PNG and WEBP"


def info(engine: EngineInfo, max_mb: int, rate: int, window_s: int) -> str:
    return (
        f"<b>{html.escape(APP_NAME)}</b>: send me an image and I'll reply with the text in it.\n\n"
        "<b>How to use</b>\n"
        "• Send a photo, or an image <i>as a file</i> (📎 → File) for the best accuracy: "
        "Telegram compresses normal photos.\n"
        f"• Supported: {SUPPORTED}, up to {max_mb} MB. Other file types are refused.\n"
        f"• Limit: {rate} images per {window_s} s.\n\n"
        f"<b>OCR engine</b>: {html.escape(engine.name)} ({html.escape(engine.tagline.lower())}).\n"
        "Use /engine to compare the engines and switch.\n\n"
        "<b>Privacy</b>\n"
        "Images are processed on the fly and deleted right after. I don't store your images or the "
        "extracted text. Basic usage logs (Telegram user ID, file size, timing) are kept to prevent "
        "abuse; your engine choice is remembered.\n\n"
        "Commands: /info, /engine"
    )


def engines(current: str, options: list[EngineInfo]) -> str:
    parts = ["<b>OCR engines</b>: tap a button to switch. Your choice is remembered.\n"]
    for e in options:
        mark = "✅ " if e.id == current else ""
        parts.append(
            f"{mark}<b>{html.escape(e.name)}</b>: {html.escape(e.tagline)}\n"
            f"  👍 {html.escape(e.good)}\n"
            f"  👎 {html.escape(e.weak)}\n"
            f"  ⏱ {html.escape(e.speed)} per image · licence: {html.escape(e.licence)}\n"
        )
    parts.append("Tip: if one engine misreads an image, switch and send it again.")
    return "\n".join(parts)


def switched(e: EngineInfo) -> str:
    return f"Switched to {e.name}"


def footer(e: EngineInfo | None, ms: int) -> str:
    name = e.name if e else "?"
    return f"<i>{html.escape(name)} · {ms / 1000:.1f} s · /engine to switch</i>"


UNSUPPORTED = (
    f"⚠️ Unsupported file type. Only images are allowed ({SUPPORTED}).\n"
    "Send a photo, or an image file."
)
HEIF = (
    "⚠️ HEIC/HEIF/AVIF images aren't supported. Send it as a normal photo instead "
    "(Telegram converts it), or export it as JPEG/PNG."
)
GROUP_HINT = "Send me images in a private chat and I'll read the text."
TEXT_HINT = "Send me an image (photo or image file) and I'll read the text in it. /info for details."
WORKING = "🔎 Reading…"
NO_TEXT = "I couldn't find any text in that image."
BUSY = "😮‍💨 I'm busy right now. Please try again in a minute."
FAILED = "❌ Sorry, something went wrong reading that image. Please try again."


def too_large(max_mb: int) -> str:
    return f"⚠️ That file is too large. The limit is {max_mb} MB."


def rate_limited(seconds: int) -> str:
    return f"⏳ Slow down a little: try again in {seconds} s."


ERRORS = {
    "unsupported_type": UNSUPPORTED,
    "heif": HEIF,
    "empty": UNSUPPORTED,
    "corrupt": "⚠️ I couldn't open that image. It may be damaged or not a real image.",
    "too_many_pixels": "⚠️ That image's dimensions are too large. Please send a smaller image.",
    "timeout": "⌛ That image took too long to read. Try a smaller or simpler image.",
    "too_complex": "⚠️ That image needed too much memory to read. Try a smaller image or another /engine.",
}
ENGINE_GONE = "That engine isn't available right now."


def result_html(text: str, foot: str = "") -> str:
    body = f"<pre>{html.escape(text)}</pre>"
    return f"{body}\n{foot}" if foot else body
