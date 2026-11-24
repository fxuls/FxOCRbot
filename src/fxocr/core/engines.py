"""Engine registry: ids, user-facing descriptions, availability. Pure data + cheap checks.

Front-ends use this to list/switch engines; the worker uses engine.run_ocr to execute them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EngineInfo:
    id: str
    name: str
    tagline: str
    good: str
    weak: str
    speed: str
    licence: str


ENGINES: dict[str, EngineInfo] = {
    e.id: e
    for e in (
        EngineInfo(
            id="ocria-nano",
            name="OCRia-nano-1",
            tagline="Best all-rounder for documents and screenshots",
            good="Documents, screenshots, tables; many scripts: Latin, Chinese/Japanese/Korean, "
                 "Arabic/Hebrew and ~17 more; low-res or rotated photos",
            weak="Stylised titles (posters, logos); single-digit table cells; word spacing in big display type",
            speed="~0.5–2.5 s",
            licence="OCRia-nano-1 Model License (LlamaIndex)",
        ),
        EngineInfo(
            id="ppocr",
            name="PP-OCRv6",
            tagline="Best on photos, posters and stylised text",
            good="Signs, posters, product photos, bold/stylised text, tables; English + Chinese",
            weak="Only English and Chinese (no Korean, Arabic, Cyrillic…); slowest",
            speed="~2–5 s",
            licence="Apache-2.0 (PaddleOCR models via RapidOCR)",
        ),
        EngineInfo(
            id="tesseract",
            name="Tesseract",
            tagline="The classic: clean printed Latin text",
            good="Clean scans and screenshots of English/Latin text; keeps column layout",
            weak="Non-Latin scripts, photos, rotated or low-res images, stylised text",
            speed="~1–2 s",
            licence="Apache-2.0",
        ),
    )
}


def _model_dir() -> Path:
    return Path(os.environ.get("LITEPARSE_MODEL_DIR") or Path.home() / ".cache" / "liteparse" / "models")


def is_available(engine_id: str) -> bool:
    if engine_id == "tesseract":
        return True
    if engine_id == "ocria-nano":
        d = _model_dir()
        return d.is_dir() and any(d.rglob("rec_latin.onnx"))
    if engine_id == "ppocr":
        try:
            import importlib.util
            return importlib.util.find_spec("rapidocr") is not None
        except Exception:
            return False
    return False


def available() -> list[EngineInfo]:
    return [e for e in ENGINES.values() if is_available(e.id)]
