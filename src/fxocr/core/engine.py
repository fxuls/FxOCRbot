"""Thin wrapper over LiteParse. Input must already be a sanitised PNG (see imaging.sanitize)."""

from __future__ import annotations

import textwrap
from pathlib import Path

MAX_TEXT_CHARS = 100_000


def run_ocr(png_path: Path, engine: str, timeout_s: int) -> str:
    from liteparse import LiteParse  # imported lazily: only the worker process needs it

    parser = LiteParse(
        ocr_backend=engine,
        output_format="text",  # keeps column layout; front-ends show it monospaced
        quiet=True,
        num_workers=1,
        max_pages=1,
        ocr_failure_fatal=True,
    )
    result = parser.parse(str(png_path))
    return tidy(result.text or "")


def tidy(text: str) -> str:
    lines = [ln.rstrip() for ln in text.replace("\r\n", "\n").split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    out = textwrap.dedent("\n".join(lines))
    # collapse 3+ blank lines
    while "\n\n\n" in out:
        out = out.replace("\n\n\n", "\n\n")
    return out[:MAX_TEXT_CHARS]
