"""Isolated OCR worker: `python -I -m fxocr.core.worker` (spawned by runner.py).

Reads the untrusted upload from stdin, writes one JSON object to stdout. Runs with rlimits set by
the parent, in a private temp dir, so a hostile image can at worst kill this short-lived process.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path


def main() -> int:
    from fxocr.core.config import CoreConfig
    from fxocr.core.engine import run_ocr
    from fxocr.core.imaging import ImageRejected, sanitize

    t0 = time.monotonic()
    cfg = CoreConfig.from_env()
    data = sys.stdin.buffer.read(cfg.max_file_bytes + 1)

    with tempfile.TemporaryDirectory(prefix="fxocr-") as tmp:
        clean = Path(tmp) / "page.png"
        try:
            w, h = sanitize(
                data, clean,
                max_bytes=cfg.max_file_bytes, max_pixels=cfg.max_pixels, max_side=cfg.max_side,
            )
        except ImageRejected as exc:
            return _emit({"ok": False, "error": exc.code})
        del data
        try:
            text = run_ocr(clean, cfg.engine, cfg.timeout_s)
        except Exception as exc:  # engine failure: report a code, keep details in stderr only
            print(f"ocr failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return _emit({"ok": False, "error": "ocr_failed"})

    return _emit({
        "ok": True,
        "text": text,
        "engine": cfg.engine,
        "width": w,
        "height": h,
        "ms": int((time.monotonic() - t0) * 1000),
    })


def _emit(obj: dict) -> int:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    os.umask(0o077)
    sys.exit(main())
