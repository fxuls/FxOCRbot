# OCR engines

Both engines run through [LiteParse](https://github.com/run-llama/liteparse) (Apache-2.0).
Select with `FXOCR_ENGINE`.

| | `tesseract` (default) | `ocria-nano` |
|---|---|---|
| Licence | Apache-2.0 (bundled with LiteParse) | **OCRia-nano-1 Model License** (modified Open RAIL-M), by LlamaIndex |
| Install | nothing extra | build with `WITH_OCRIA_NANO=1` (runs `lit models pull ocria-nano`, ~60 MB) |
| Latin text, screenshots | good | good, more robust on low-res/rotated input |
| CJK / Arabic / Hebrew / other scripts | poor | much better (script router, per-script recognisers) |
| Speed (one image, CPU) | ~0.4–1.5 s | ~0.4–0.8 s |
| Known weaknesses | non-Latin scripts, rotated/low-res photos | single-character table cells, word spacing in display type, stylised text |

## ⚠️ OCRia-nano-1 licence and public bots

The OCRia-nano-1 weights are **not open source** and are not distributed with this repo. Their
licence (read the full text on the model's Hugging Face page) includes, among others:

- a restriction on use "to provide, or as part of, a **Competing Service**, whatever Your revenue
  or funding", where a Competing Service is one that offers OCR / document parsing and competes
  with LlamaIndex products (LlamaParse, LlamaCloud). Only research purposes are exempt;
- revenue/funding thresholds ($2M) above which a commercial licence is needed;
- obligations when hosting the model for third parties (pass on the use restrictions, attribution).

A free public OCR bot may fall under "Competing Service". **The public deployment therefore uses
`tesseract` unless LlamaIndex grants permission.** Private/personal deployments should make their
own assessment. This is not legal advice.
