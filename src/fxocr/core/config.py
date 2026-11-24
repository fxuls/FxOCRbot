"""Settings shared by every front-end. All values come from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from fxocr.core.engines import ENGINES


def _int(name: str, default: int, lo: int, hi: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        val = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if not lo <= val <= hi:
        raise ValueError(f"{name} must be between {lo} and {hi}, got {val}")
    return val


@dataclass(frozen=True)
class CoreConfig:
    engine: str = "tesseract"
    max_file_bytes: int = 10 * 1024 * 1024
    max_pixels: int = 40_000_000
    max_side: int = 4000
    timeout_s: int = 60
    worker_mem_mb: int = 8192

    @classmethod
    def from_env(cls) -> "CoreConfig":
        engine = os.environ.get("FXOCR_ENGINE", "tesseract").strip() or "tesseract"
        if engine not in ENGINES:
            raise ValueError(f"FXOCR_ENGINE must be one of {tuple(ENGINES)}, got {engine!r}")
        return cls(
            engine=engine,
            max_file_bytes=_int("FXOCR_MAX_FILE_MB", 10, 1, 20) * 1024 * 1024,
            max_pixels=_int("FXOCR_MAX_PIXELS", 40_000_000, 100_000, 100_000_000),
            max_side=_int("FXOCR_MAX_SIDE", 4000, 500, 10_000),
            timeout_s=_int("FXOCR_TIMEOUT_S", 60, 5, 600),
            worker_mem_mb=_int("FXOCR_WORKER_MEM_MB", 8192, 256, 16_384),
        )
