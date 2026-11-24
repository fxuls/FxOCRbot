"""Engine execution. Input must already be a sanitised PNG (see imaging.sanitize).

Runs only inside the worker process.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

MAX_TEXT_CHARS = 100_000


def run_ocr(png_path: Path, engine: str, timeout_s: int) -> str:
    if engine in ("tesseract", "ocria-nano"):
        return _liteparse(png_path, engine)
    if engine == "ppocr":
        return _ppocr(png_path)
    raise ValueError(f"unknown engine {engine!r}")


def _liteparse(png_path: Path, engine: str) -> str:
    from liteparse import LiteParse  # lazy: only the worker needs it

    parser = LiteParse(
        ocr_backend=engine,
        output_format="text",  # keeps column layout; front-ends show it monospaced
        quiet=True,
        num_workers=1,
        max_pages=1,
        ocr_failure_fatal=True,
    )
    return tidy(parser.parse(str(png_path)).text or "")


def _ppocr(png_path: Path) -> str:
    from rapidocr import RapidOCR  # lazy

    eng = RapidOCR(params={
        "Global.log_level": "critical",
        "EngineConfig.onnxruntime.intra_op_num_threads": 2,
        "EngineConfig.onnxruntime.inter_op_num_threads": 1,
    })
    res = eng(str(png_path))
    if res.boxes is None or res.txts is None:
        return ""
    items = []
    for box, txt in zip(res.boxes.tolist(), res.txts):
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        items.append((min(xs), max(xs), min(ys), max(ys), str(txt)))
    return tidy(boxes_to_text(items))


def boxes_to_text(items: list[tuple[float, float, float, float, str]]) -> str:
    """Rebuild reading order from (x0, x1, y0, y1, text) boxes: group into rows, sort left→right.

    Boxes whose vertical centres are within half a line height join the same row. Wide horizontal
    gaps become a few spaces so table columns stay apart.
    """
    if not items:
        return ""
    items = sorted(items, key=lambda b: (b[2] + b[3]) / 2)
    rows: list[list[tuple]] = []
    for it in items:
        cy = (it[2] + it[3]) / 2
        h = max(it[3] - it[2], 1)
        if rows:
            last = rows[-1]
            lcy = sum((b[2] + b[3]) / 2 for b in last) / len(last)
            lh = sum(max(b[3] - b[2], 1) for b in last) / len(last)
            if abs(cy - lcy) <= 0.5 * min(h, lh):
                last.append(it)
                continue
        rows.append([it])

    lines = []
    for row in rows:
        row.sort(key=lambda b: b[0])
        parts = [row[0][4]]
        for prev, cur in zip(row, row[1:]):
            h = max(cur[3] - cur[2], 1)
            gap = cur[0] - prev[1]
            parts.append("    " if gap > 1.5 * h else " ")
            parts.append(cur[4])
        lines.append("".join(parts))
    return "\n".join(lines)


def tidy(text: str) -> str:
    lines = [ln.rstrip() for ln in text.replace("\r\n", "\n").split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    out = textwrap.dedent("\n".join(lines))
    while "\n\n\n" in out:
        out = out.replace("\n\n\n", "\n\n")
    return out[:MAX_TEXT_CHARS]
