# OCR engines

Three engines, selectable **per user** in the bot with `/engine` (inline buttons). `FXOCR_ENGINE`
sets the default for users who haven't chosen. The registry (names, descriptions shown to users)
is `src/fxocr/core/engines.py`; execution is `src/fxocr/core/engine.py`.

| | `ocria-nano` | `ppocr` | `tesseract` |
|---|---|---|---|
| Model | OCRia-nano-1 (LlamaIndex), via [LiteParse](https://github.com/run-llama/liteparse) | PP-OCRv6 small (PaddleOCR) via [RapidOCR](https://github.com/RapidAI/RapidOCR) | Tesseract via LiteParse |
| Licence | OCRia-nano-1 Model License (modified Open RAIL-M) | Apache-2.0 | Apache-2.0 |
| Install | `WITH_OCRIA_NANO=1` at build (`lit models pull ocria-nano`, ~60 MB) | bundled in the `rapidocr` wheel | bundled with LiteParse |
| Best at | documents, screenshots, tables, **many scripts** (Latin, CJK, Arabic/Hebrew, ~17 more), low-res/rotated input | **photos, posters, signs, stylised text**, tables | clean printed Latin text |
| Weak at | stylised titles, single-character table cells, word spacing in display type | only English + Chinese | non-Latin scripts, photos, rotated/low-res |
| Time per image (2-CPU container, incl. worker start) | ~0.5–2.5 s | ~2–5 s | ~1–2 s |
| Peak RAM per job | ~0.1 GB | ~0.8 GB on large images | ~0.1 GB |

Measured on a small set of documents, screenshots and film posters (2026-11), not a benchmark.

## Notes

- Each job runs in a fresh worker process, so engine start-up is included in every timing.
- ONNX Runtime reserves far more virtual memory than it uses: the worker's address-space cap
  (`FXOCR_WORKER_MEM_MB`, default 8 GB) must stay high; real RAM is capped by the container (2 GB).
  Below ~4 GB OCRia-nano hangs and PP-OCR fails with `bad_alloc`.
- If the OCRia-nano weights aren't installed, the engine is hidden from `/engine` and users who
  had chosen it fall back to the default.

## Licences

The OCRia-nano-1 weights are not open source and are not distributed with this repo; they are
downloaded at build time only when enabled. Their licence restricts certain uses (including
competing OCR / document-parsing services and use above revenue/funding thresholds) and adds
obligations when hosting for third parties. **Read the licence on the model's Hugging Face page
and make sure your deployment complies before enabling it.** This is not legal advice.
