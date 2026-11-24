"""Front-end-agnostic OCR core.

Every front-end (bot, future web/API) goes through `fxocr.core.runner.ocr_image_bytes`, which
validates and re-encodes untrusted input inside a resource-limited worker process before any OCR
engine sees it. Front-ends must never hand raw user bytes to Pillow or LiteParse themselves.
"""
