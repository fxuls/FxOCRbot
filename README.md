# FxOCRbot

Everything OCR in one repo. Today: a **Telegram bot** that reads the text in images you send it.
Planned: a **website** and an **HTTP API** on the same core.

> The project is called FxOCRbot; the public bot username and any website URL may change, so
> nothing in the code depends on them.

## Telegram bot

- `/info`: what the bot does, limits, privacy.
- `/engine`: compares the OCR engines (OCRia-nano-1, PP-OCRv6, Tesseract) and switches yours with
  a tap. Each result shows which engine read it.
- Send a **photo** or an **image file** (JPEG, PNG, WEBP; up to 10 MB) in a private chat. The bot
  replies with the text it found. Long results come back as a `.txt` file.
- Anything else (videos, PDFs, documents, stickers, voice…) gets "unsupported file type, images
  only".
- Tip: send images **as a file** (📎 → File). Telegram compresses normal photos, which costs accuracy.

## Layout

```
src/fxocr/
  core/        front-end-agnostic OCR: config, untrusted-image sanitising, sandboxed worker, engine
  core/engines.py  engine registry (ids, user-facing descriptions)
  bot/         Telegram front-end (python-telegram-bot), per-user engine prefs
  (web/, api/  planned: see docs/architecture.md)
tests/         pytest, including hostile-input tests
compose.yaml   hardened container for the bot
```

## Run it

```bash
cp .env.example .env            # put your @BotFather token in TELEGRAM_BOT_TOKEN
docker compose up -d --build
docker compose logs -f
```

Engines: see [docs/engines.md](docs/engines.md). `FXOCR_ENGINE` sets the default
(`tesseract`, `ppocr` or `ocria-nano`); OCRia-nano-1 also needs `WITH_OCRIA_NANO=1` at build time,
and its weights have their own licence, so read that doc first.

## Develop

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[bot,dev]'
.venv/bin/python -m pytest -q
```

## Security

The bot accepts files from strangers. See [SECURITY.md](SECURITY.md) for the threat model and
controls. Report vulnerabilities privately via GitHub's "Report a vulnerability" (Security tab).

## Licence

MIT for this code. Third-party components and model weights keep their own licences; see `LICENSE`.
