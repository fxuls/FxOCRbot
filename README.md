# FxOCRbot

Everything OCR in one repo. Today: a **Telegram bot** that reads the text in images you send it.
Planned: a **website** and an **HTTP API** on the same core.

> The project is called FxOCRbot; the public bot username and any website URL may change, so
> nothing in the code depends on them.

## Telegram bot

- `/info`: what the bot does, limits, privacy.
- Send a **photo** or an **image file** (JPEG, PNG, WEBP; up to 10 MB) in a private chat. The bot
  replies with the text it found. Long results come back as a `.txt` file.
- Anything else (videos, PDFs, documents, stickers, voice…) gets "unsupported file type, images
  only".
- Tip: send images **as a file** (📎 → File). Telegram compresses normal photos, which costs accuracy.

## Layout

```
src/fxocr/
  core/        front-end-agnostic OCR: config, untrusted-image sanitising, sandboxed worker, engine
  bot/         Telegram front-end (python-telegram-bot)
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

Engine: `FXOCR_ENGINE=tesseract` (default) or `ocria-nano`. **Read [docs/engines.md](docs/engines.md)
before enabling OCRia-nano-1**: its weights have their own licence, which restricts public OCR services.

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
