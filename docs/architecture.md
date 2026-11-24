# Architecture

One repo, one Python package (`fxocr`), one Docker image, several front-ends.

```
            ┌────────────── front-ends (thin) ──────────────┐
 Telegram → │ fxocr.bot      (now)                          │
 Browser  → │ fxocr.web      (planned)                      │──→ fxocr.core.runner.ocr_image_bytes()
 HTTP     → │ fxocr.api      (planned)                      │          │
            └───────────────────────────────────────────────┘          ▼
                                             worker subprocess (rlimits, no secrets)
                                               imaging.sanitize → clean PNG
                                               engine.run_ocr   → LiteParse (tesseract | ocria-nano)
```

## Rules for front-ends

1. **Never decode user files in the front-end process.** Call `ocr_image_bytes(data, CoreConfig)`.
   It enforces size, type, pixel limits, the sandbox and timeouts.
2. Do your own transport-level checks first (declared size, rate limit, auth for the API).
3. Wrap calls in a concurrency gate (`fxocr.bot.limits.JobGate` can move to core when a second
   front-end needs it).
4. Escape output for whatever you render into (HTML, Markdown, JSON is fine as-is).
5. Branding lives in data (`fxocr.APP_NAME`, `bot/messages.py`), not in logic, because names/URLs may change.

## Planned front-ends

- **API** (`fxocr.api`): FastAPI app, `POST /v1/ocr` (multipart image → `{text, engine, ms}`),
  API keys + per-key rate limits, same image as the bot with a different `command:`.
  Optional JSON output with bounding boxes once `engine.run_ocr` exposes LiteParse's JSON mode.
- **Website** (`web/`): two options, decided later:
  - client-side: static page using LiteParse's WASM build; images never leave the browser,
    no server load, nothing to abuse;
  - server-side: a small page calling the API above.
- Future core features: PDF input (page cap), JSON with bounding boxes, language/translate
  post-processing, subtitle-bitmap → SRT.

## Deployment

`compose.yaml` runs the bot. New front-ends become extra services in the same file using the same
image. Secrets come from `.env` only.
