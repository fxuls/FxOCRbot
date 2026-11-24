"""FxOCRbot Telegram bot: /info, and OCR of images sent in private chats.

Security model (see SECURITY.md):
- Only images (JPEG/PNG/WEBP, identified by magic bytes, never by name/MIME) are processed.
- Size is checked from Telegram's metadata before download, and again after.
- Decoding and OCR happen in a separate, resource-limited worker process (fxocr.core.runner);
  the bot process never parses user files.
- All output is HTML-escaped; per-user rate limits and a bounded global queue cap abuse.
"""

from __future__ import annotations

import io
import logging
import os
import sys

from telegram import BotCommand, Message, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from fxocr import APP_NAME, __version__
from fxocr.bot import messages as M
from fxocr.bot.limits import Busy, JobGate, RateLimiter
from fxocr.core.config import CoreConfig, _int
from fxocr.core.imaging import sniff
from fxocr.core.runner import ocr_image_bytes

log = logging.getLogger("fxocr.bot")

INLINE_MAX = 3900  # Telegram caps messages at 4096 chars; longer results go out as a .txt file


class Bot:
    def __init__(self, core: CoreConfig):
        self.core = core
        self.rate = _int("FXOCR_USER_RATE", 6, 1, 1000)
        self.window = _int("FXOCR_USER_WINDOW_S", 60, 1, 86_400)
        self.limiter = RateLimiter(self.rate, self.window)
        self.gate = JobGate(_int("FXOCR_CONCURRENCY", 2, 1, 32), _int("FXOCR_QUEUE_MAX", 20, 0, 1000))
        self.max_mb = core.max_file_bytes // (1024 * 1024)

    # ---- commands -------------------------------------------------------------------------
    async def cmd_info(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        if msg is None:
            return
        await msg.reply_text(
            M.info(self.core.engine, self.max_mb, self.rate, self.window),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )

    # ---- inputs ---------------------------------------------------------------------------
    async def on_photo(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        photo = msg.photo[-1]  # largest size Telegram kept
        await self._process(msg, ctx, photo.file_id, photo.file_size)

    async def on_document(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        doc = msg.document
        mime = (doc.mime_type or "").lower()
        # Cheap pre-filter so we don't download obvious non-images. Not a security check: the
        # real decision is made on the file's bytes after download.
        if not mime.startswith("image/"):
            await msg.reply_text(M.UNSUPPORTED, do_quote=True)
            return
        if mime in ("image/heic", "image/heif", "image/avif"):
            await msg.reply_text(M.HEIF, do_quote=True)
            return
        await self._process(msg, ctx, doc.file_id, doc.file_size)

    async def on_text(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await update.effective_message.reply_text(M.TEXT_HINT)

    async def on_other(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        msg = update.effective_message
        if msg is None:
            return
        await msg.reply_text(M.UNSUPPORTED, do_quote=True)

    # ---- pipeline -------------------------------------------------------------------------
    async def _process(self, msg: Message, ctx: ContextTypes.DEFAULT_TYPE, file_id: str, size: int | None) -> None:
        uid = msg.from_user.id if msg.from_user else msg.chat_id

        if size is not None and size > self.core.max_file_bytes:
            await msg.reply_text(M.too_large(self.max_mb), do_quote=True)
            return
        if not self.limiter.allow(uid):
            if self.limiter.should_warn(uid):
                await msg.reply_text(M.rate_limited(self.limiter.retry_after(uid)), do_quote=True)
            log.info("rate-limited user=%s", uid)
            return

        status = await msg.reply_text(M.WORKING, do_quote=True)
        try:
            tg_file = await ctx.bot.get_file(file_id)
            data = bytes(await tg_file.download_as_bytearray())
        except Exception as exc:
            log.warning("download failed user=%s: %s", uid, type(exc).__name__)
            await status.edit_text(M.FAILED)
            return

        if len(data) > self.core.max_file_bytes:
            await status.edit_text(M.too_large(self.max_mb))
            return
        kind = sniff(data[:32])
        if kind == "heif":
            await status.edit_text(M.HEIF)
            return
        if kind is None:
            log.info("rejected non-image user=%s bytes=%d", uid, len(data))
            await status.edit_text(M.UNSUPPORTED)
            return

        try:
            async with self.gate.slot():
                await ctx.bot.send_chat_action(msg.chat_id, ChatAction.TYPING)
                result = await ocr_image_bytes(data, self.core)
        except Busy:
            await status.edit_text(M.BUSY)
            return
        finally:
            del data

        log.info("ocr user=%s kind=%s ok=%s err=%s ms=%d chars=%d",
                 uid, kind, result.ok, result.error, result.ms, len(result.text))
        if not result.ok:
            await status.edit_text(M.ERRORS.get(result.error, M.FAILED))
            return
        if not result.text.strip():
            await status.edit_text(M.NO_TEXT)
            return
        if len(result.text) <= INLINE_MAX:
            await status.edit_text(M.result_html(result.text), parse_mode=ParseMode.HTML)
            return
        await status.edit_text("📄 Lots of text: sent as a file.")
        await msg.reply_document(
            document=io.BytesIO(result.text.encode("utf-8")),
            filename="ocr.txt",
            do_quote=True,
        )

    # ---- plumbing -------------------------------------------------------------------------
    async def on_error(self, update: object, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        # Type + message only: never dump update contents (user data) into logs.
        err = ctx.error
        log.error("handler error: %s: %s", type(err).__name__, str(err)[:300])


async def _post_init(app: Application) -> None:
    await app.bot.set_my_commands([BotCommand("info", "What this bot does and how to use it")])
    me = await app.bot.get_me()
    log.info("%s %s running as @%s", APP_NAME, __version__, me.username)


def build_app(token: str, core: CoreConfig) -> Application:
    bot = Bot(core)
    app = (
        Application.builder()
        .token(token)
        .concurrent_updates(True)
        .post_init(_post_init)
        .build()
    )
    private = filters.ChatType.PRIVATE
    app.add_handler(CommandHandler(["info", "start", "help"], bot.cmd_info))
    app.add_handler(MessageHandler(private & filters.PHOTO, bot.on_photo))
    app.add_handler(MessageHandler(private & filters.Document.ALL, bot.on_document))
    app.add_handler(MessageHandler(private & filters.TEXT & ~filters.COMMAND, bot.on_text))
    app.add_handler(MessageHandler(private & filters.COMMAND, bot.cmd_info))  # unknown command
    # Everything else in a private chat (video, audio, voice, stickers, GIFs, contacts, …).
    app.add_handler(MessageHandler(private & ~filters.StatusUpdate.ALL, bot.on_other))
    app.add_error_handler(bot.on_error)
    return app


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("FXOCR_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # httpx logs full request URLs at INFO, and Telegram URLs contain the bot token.
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("TELEGRAM_BOT_TOKEN is not set (see .env.example)", file=sys.stderr)
        sys.exit(2)
    core = CoreConfig.from_env()
    log.info("engine=%s max_file=%dMB", core.engine, core.max_file_bytes // (1024 * 1024))
    app = build_app(token, core)
    app.run_polling(allowed_updates=[Update.MESSAGE], drop_pending_updates=True)


if __name__ == "__main__":
    main()
