import os
import logging
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ConversationHandler, CallbackQueryHandler
)
from handlers import (
    start, help_command,
    compress_handler, trim_start, trim_video,
    screenshot_handler, screenshot_multi_handler,
    audio_extract_handler, subtitle_extract_handler,
    watermark_start, watermark_receive_logo, watermark_receive_video,
    add_subtitle_start, add_subtitle_receive_srt, add_subtitle_receive_video,
    audio_mix_start, audio_mix_receive_audio, audio_mix_receive_video,
    join_start, join_first, join_second,
    download_handler,
    rename_start, rename_receive_file, rename_receive_name,
    zip_handler, unzip_handler,
    cancel, button_callback
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
TRIM_WAIT     = 1
WM_LOGO       = 2
WM_VIDEO      = 3
SUB_SRT       = 4
SUB_VIDEO     = 5
MIX_AUDIO     = 6
MIX_VIDEO     = 7
JOIN_FIRST    = 8
JOIN_SECOND   = 9
RENAME_FILE   = 10
RENAME_NAME   = 11

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN environment variable not set!")

    app = ApplicationBuilder().token(token).build()

    # ── Simple commands ──────────────────────────────────────────────
    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("help",    help_command))
    app.add_handler(CommandHandler("compress",compress_handler))
    app.add_handler(CommandHandler("ss",      screenshot_handler))
    app.add_handler(CommandHandler("ss12",    screenshot_multi_handler))
    app.add_handler(CommandHandler("audio",   audio_extract_handler))
    app.add_handler(CommandHandler("sub",     subtitle_extract_handler))
    app.add_handler(CommandHandler("download",download_handler))
    app.add_handler(CommandHandler("zip",     zip_handler))
    app.add_handler(CommandHandler("unzip",   unzip_handler))

    # ── Trim conversation ────────────────────────────────────────────
    trim_conv = ConversationHandler(
        entry_points=[CommandHandler("trim", trim_start)],
        states={TRIM_WAIT: [MessageHandler(filters.VIDEO | filters.Document.VIDEO, trim_video)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(trim_conv)

    # ── Watermark conversation ────────────────────────────────────────
    wm_conv = ConversationHandler(
        entry_points=[CommandHandler("watermark", watermark_start)],
        states={
            WM_LOGO:  [MessageHandler(filters.PHOTO | filters.Document.IMAGE, watermark_receive_logo)],
            WM_VIDEO: [MessageHandler(filters.VIDEO | filters.Document.VIDEO, watermark_receive_video)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(wm_conv)

    # ── Add subtitle conversation ────────────────────────────────────
    sub_conv = ConversationHandler(
        entry_points=[CommandHandler("addsub", add_subtitle_start)],
        states={
            SUB_SRT:   [MessageHandler(filters.Document.ALL, add_subtitle_receive_srt)],
            SUB_VIDEO: [MessageHandler(filters.VIDEO | filters.Document.VIDEO, add_subtitle_receive_video)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(sub_conv)

    # ── Audio mix conversation ───────────────────────────────────────
    mix_conv = ConversationHandler(
        entry_points=[CommandHandler("mixaudio", audio_mix_start)],
        states={
            MIX_AUDIO: [MessageHandler(filters.AUDIO | filters.Document.AUDIO, audio_mix_receive_audio)],
            MIX_VIDEO: [MessageHandler(filters.VIDEO | filters.Document.VIDEO, audio_mix_receive_video)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(mix_conv)

    # ── Join conversation ────────────────────────────────────────────
    join_conv = ConversationHandler(
        entry_points=[CommandHandler("join", join_start)],
        states={
            JOIN_FIRST:  [MessageHandler(filters.VIDEO | filters.Document.VIDEO, join_first)],
            JOIN_SECOND: [MessageHandler(filters.VIDEO | filters.Document.VIDEO, join_second)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(join_conv)

    # ── Rename conversation ──────────────────────────────────────────
    rename_conv = ConversationHandler(
        entry_points=[CommandHandler("rename", rename_start)],
        states={
            RENAME_FILE: [MessageHandler(filters.ALL, rename_receive_file)],
            RENAME_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, rename_receive_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(rename_conv)

    app.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
