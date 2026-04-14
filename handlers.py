import os
import re
import logging
import asyncio
import tempfile
import subprocess
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

TRIM_WAIT  = 1
WM_LOGO    = 2
WM_VIDEO   = 3
SUB_SRT    = 4
SUB_VIDEO  = 5
MIX_AUDIO  = 6
MIX_VIDEO  = 7
JOIN_FIRST = 8
JOIN_SECOND= 9
RENAME_FILE= 10
RENAME_NAME= 11

TMPDIR = Path(tempfile.gettempdir()) / "vbot"
TMPDIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)

async def download_file(update: Update, context: ContextTypes.DEFAULT_TYPE, suffix="") -> Path:
    msg = update.message
    if msg.video:
        f = msg.video
    elif msg.document:
        f = msg.document
    elif msg.audio:
        f = msg.audio
    elif msg.photo:
        f = msg.photo[-1]
    else:
        f = msg.effective_attachment

    tg_file = await context.bot.get_file(f.file_id)
    dest = TMPDIR / f"{f.file_id}{suffix}"
    await tg_file.download_to_drive(str(dest))
    return dest

def ffprobe_duration(path: str) -> float:
    r = run(["ffprobe","-v","error","-show_entries","format=duration",
             "-of","default=noprint_wrappers=1:nokey=1", path])
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0

async def send_progress(msg, text: str):
    try:
        await msg.edit_text(text)
    except Exception:
        pass

# ─────────────────────────────────────────────
# /start  /help
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎬 *Video Tools Bot*\n\n"
        "Welcome! Here are all available commands:\n\n"
        "📉 /compress – Compress video (HEVC H.265)\n"
        "✂️ /trim – Trim a video clip\n"
        "📸 /ss – Single screenshot from video\n"
        "📸 /ss12 – 12 screenshots at equal intervals\n"
        "🎵 /audio – Extract MP3 from video\n"
        "📝 /sub – Extract soft subtitles (.srt)\n\n"
        "🖼️ /watermark – Add logo/watermark to video\n"
        "📜 /addsub – Soft-code .srt subtitles into video\n"
        "🔀 /mixaudio – Replace video audio\n"
        "🎞️ /join – Join two videos together\n\n"
        "🚀 /download `<url>` – Download from URL\n"
        "✏️ /rename – Rename a file\n"
        "📦 /zip – Zip a file\n"
        "📦 /unzip – Unzip a .zip file\n\n"
        "❌ /cancel – Cancel current operation\n"
        "❓ /help – Show this menu"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Operation cancelled.")
    return -1  # ConversationHandler.END

# ─────────────────────────────────────────────
# /compress
# ─────────────────────────────────────────────

async def compress_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not (msg.video or msg.document):
        await msg.reply_text("📎 Send the video as a reply or attach it with the /compress command.")
        return

    prog = await msg.reply_text("⏳ Downloading video…")
    inp = await download_file(update, context, suffix=".mp4")
    out = TMPDIR / f"compressed_{inp.name}"

    await send_progress(prog, "⚙️ Compressing with HEVC H.265…")
    r = run(["ffmpeg","-y","-i",str(inp),
             "-c:v","libx265","-crf","28","-preset","fast",
             "-c:a","aac","-b:a","128k", str(out)])

    if r.returncode != 0 or not out.exists():
        await send_progress(prog, f"❌ Compression failed.\n`{r.stderr[-500:]}`")
        return

    orig = inp.stat().st_size / 1024 / 1024
    comp = out.stat().st_size / 1024 / 1024
    await send_progress(prog, f"📤 Uploading… ({comp:.1f} MB, was {orig:.1f} MB)")
    await msg.reply_document(document=open(out,"rb"), filename=f"compressed_{msg.video.file_name if msg.video else 'video.mp4'}")
    await prog.delete()
    inp.unlink(missing_ok=True); out.unlink(missing_ok=True)

# ─────────────────────────────────────────────
# /trim
# ─────────────────────────────────────────────

async def trim_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "✂️ Usage: `/trim <start> <end>`\nExample: `/trim 00:00:10 00:00:30`\n\nThen send your video.",
            parse_mode=ParseMode.MARKDOWN)
        return -1

    context.user_data["trim_start"] = args[0]
    context.user_data["trim_end"]   = args[1]
    await update.message.reply_text("📎 Now send the video to trim.")
    return TRIM_WAIT

async def trim_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t_start = context.user_data.get("trim_start","0")
    t_end   = context.user_data.get("trim_end","10")
    prog = await update.message.reply_text("⏳ Downloading…")
    inp = await download_file(update, context, suffix=".mp4")
    out = TMPDIR / f"trimmed_{inp.name}"

    await send_progress(prog,"✂️ Trimming video…")
    r = run(["ffmpeg","-y","-i",str(inp),"-ss",t_start,"-to",t_end,
             "-c","copy", str(out)])

    if r.returncode != 0 or not out.exists():
        await send_progress(prog,f"❌ Trim failed.\n`{r.stderr[-400:]}`")
        return -1

    await send_progress(prog,"📤 Uploading…")
    await update.message.reply_document(open(out,"rb"), filename="trimmed.mp4")
    await prog.delete()
    inp.unlink(missing_ok=True); out.unlink(missing_ok=True)
    return -1

# ─────────────────────────────────────────────
# /ss  (single screenshot)
# ─────────────────────────────────────────────

async def screenshot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not (msg.video or msg.document):
        await msg.reply_text("📎 Send the video with caption `/ss <timestamp>` e.g. `/ss 00:00:05`",
                             parse_mode=ParseMode.MARKDOWN)
        return

    timestamp = (context.args[0] if context.args else None) or "00:00:05"
    prog = await msg.reply_text("⏳ Downloading…")
    inp  = await download_file(update, context, suffix=".mp4")
    out  = TMPDIR / f"ss_{inp.stem}.jpg"

    await send_progress(prog,"📸 Capturing screenshot…")
    r = run(["ffmpeg","-y","-ss",timestamp,"-i",str(inp),
             "-vframes","1","-q:v","2", str(out)])

    if r.returncode != 0 or not out.exists():
        await send_progress(prog,f"❌ Failed.\n`{r.stderr[-400:]}`")
        return

    await send_progress(prog,"📤 Uploading…")
    await msg.reply_photo(photo=open(out,"rb"), caption=f"🕐 Timestamp: {timestamp}")
    await prog.delete()
    inp.unlink(missing_ok=True); out.unlink(missing_ok=True)

# ─────────────────────────────────────────────
# /ss12  (12 screenshots)
# ─────────────────────────────────────────────

async def screenshot_multi_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not (msg.video or msg.document):
        await msg.reply_text("📎 Send the video attached with the /ss12 command.")
        return

    prog = await msg.reply_text("⏳ Downloading…")
    inp  = await download_file(update, context, suffix=".mp4")
    dur  = ffprobe_duration(str(inp))
    if dur == 0:
        await send_progress(prog,"❌ Could not read video duration.")
        return

    await send_progress(prog,"📸 Generating 12 screenshots…")
    shots = []
    for i in range(1, 13):
        ts  = dur * i / 13
        out = TMPDIR / f"ss12_{inp.stem}_{i:02d}.jpg"
        run(["ffmpeg","-y","-ss",str(ts),"-i",str(inp),
             "-vframes","1","-q:v","2", str(out)])
        if out.exists():
            shots.append(out)

    if not shots:
        await send_progress(prog,"❌ No screenshots generated.")
        return

    from telegram import InputMediaPhoto
    media = [InputMediaPhoto(open(s,"rb")) for s in shots]
    # Telegram allows max 10 per group; split into chunks
    await send_progress(prog,"📤 Uploading screenshots…")
    for chunk in [media[:10], media[10:]]:
        if chunk:
            await msg.reply_media_group(chunk)
    await prog.delete()
    inp.unlink(missing_ok=True)
    for s in shots: s.unlink(missing_ok=True)

# ─────────────────────────────────────────────
# /audio  – extract MP3
# ─────────────────────────────────────────────

async def audio_extract_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not (msg.video or msg.document):
        await msg.reply_text("📎 Send the video attached with /audio command.")
        return

    prog = await msg.reply_text("⏳ Downloading…")
    inp  = await download_file(update, context, suffix=".mp4")
    out  = TMPDIR / f"{inp.stem}.mp3"

    await send_progress(prog,"🎵 Extracting audio…")
    r = run(["ffmpeg","-y","-i",str(inp),"-q:a","0","-map","a", str(out)])

    if r.returncode != 0 or not out.exists():
        await send_progress(prog,f"❌ Extraction failed.\n`{r.stderr[-400:]}`")
        return

    await send_progress(prog,"📤 Uploading MP3…")
    await msg.reply_audio(audio=open(out,"rb"), filename=f"{inp.stem}.mp3")
    await prog.delete()
    inp.unlink(missing_ok=True); out.unlink(missing_ok=True)

# ─────────────────────────────────────────────
# /sub  – extract subtitles
# ─────────────────────────────────────────────

async def subtitle_extract_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not (msg.video or msg.document):
        await msg.reply_text("📎 Send the video attached with /sub command.")
        return

    prog = await msg.reply_text("⏳ Downloading…")
    inp  = await download_file(update, context, suffix=".mkv")
    out  = TMPDIR / f"{inp.stem}.srt"

    await send_progress(prog,"📝 Extracting subtitles…")
    r = run(["ffmpeg","-y","-i",str(inp),"-map","0:s:0", str(out)])

    if r.returncode != 0 or not out.exists():
        await send_progress(prog,"❌ No soft subtitles found in this video.")
        return

    await send_progress(prog,"📤 Uploading SRT…")
    await msg.reply_document(open(out,"rb"), filename=f"{inp.stem}.srt")
    await prog.delete()
    inp.unlink(missing_ok=True); out.unlink(missing_ok=True)

# ─────────────────────────────────────────────
# /watermark
# ─────────────────────────────────────────────

async def watermark_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🖼️ Send your logo/watermark image first.")
    return WM_LOGO

async def watermark_receive_logo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prog = await update.message.reply_text("⏳ Saving logo…")
    logo = await download_file(update, context, suffix=".png")
    context.user_data["wm_logo"] = str(logo)
    await send_progress(prog,"✅ Logo saved! Now send the video.")
    return WM_VIDEO

async def watermark_receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logo = context.user_data.get("wm_logo")
    prog = await update.message.reply_text("⏳ Downloading video…")
    inp  = await download_file(update, context, suffix=".mp4")
    out  = TMPDIR / f"wm_{inp.name}"

    await send_progress(prog,"🖼️ Adding watermark…")
    r = run(["ffmpeg","-y","-i",str(inp),"-i",logo,
             "-filter_complex","overlay=W-w-10:H-h-10",
             "-codec:a","copy", str(out)])

    if r.returncode != 0 or not out.exists():
        await send_progress(prog,f"❌ Failed.\n`{r.stderr[-400:]}`")
        return -1

    await send_progress(prog,"📤 Uploading…")
    await update.message.reply_document(open(out,"rb"), filename="watermarked.mp4")
    await prog.delete()
    inp.unlink(missing_ok=True); out.unlink(missing_ok=True)
    context.user_data.clear()
    return -1

# ─────────────────────────────────────────────
# /addsub
# ─────────────────────────────────────────────

async def add_subtitle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📜 Send your .srt subtitle file first.")
    return SUB_SRT

async def add_subtitle_receive_srt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc or not doc.file_name.lower().endswith(".srt"):
        await update.message.reply_text("⚠️ Please send a valid .srt file.")
        return SUB_SRT

    prog = await update.message.reply_text("⏳ Saving SRT…")
    srt  = await download_file(update, context, suffix=".srt")
    context.user_data["srt_path"] = str(srt)
    await send_progress(prog,"✅ SRT saved! Now send the video.")
    return SUB_VIDEO

async def add_subtitle_receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    srt  = context.user_data.get("srt_path")
    prog = await update.message.reply_text("⏳ Downloading video…")
    inp  = await download_file(update, context, suffix=".mp4")
    out  = TMPDIR / f"subbed_{inp.name}"

    await send_progress(prog,"📜 Muxing subtitles…")
    r = run(["ffmpeg","-y","-i",str(inp),"-i",srt,
             "-c","copy","-c:s","mov_text",
             "-metadata:s:s:0","language=eng", str(out)])

    if r.returncode != 0 or not out.exists():
        await send_progress(prog,f"❌ Failed.\n`{r.stderr[-400:]}`")
        return -1

    await send_progress(prog,"📤 Uploading…")
    await update.message.reply_document(open(out,"rb"), filename="with_subtitles.mp4")
    await prog.delete()
    inp.unlink(missing_ok=True); out.unlink(missing_ok=True)
    context.user_data.clear()
    return -1

# ─────────────────────────────────────────────
# /mixaudio
# ─────────────────────────────────────────────

async def audio_mix_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔀 Send the new audio file first.")
    return MIX_AUDIO

async def audio_mix_receive_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prog = await update.message.reply_text("⏳ Saving audio…")
    aud  = await download_file(update, context, suffix=".mp3")
    context.user_data["mix_audio"] = str(aud)
    await send_progress(prog,"✅ Audio saved! Now send the video.")
    return MIX_VIDEO

async def audio_mix_receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    aud  = context.user_data.get("mix_audio")
    prog = await update.message.reply_text("⏳ Downloading video…")
    inp  = await download_file(update, context, suffix=".mp4")
    out  = TMPDIR / f"mixed_{inp.name}"

    await send_progress(prog,"🔀 Replacing audio…")
    r = run(["ffmpeg","-y","-i",str(inp),"-i",aud,
             "-map","0:v:0","-map","1:a:0",
             "-c:v","copy","-shortest", str(out)])

    if r.returncode != 0 or not out.exists():
        await send_progress(prog,f"❌ Failed.\n`{r.stderr[-400:]}`")
        return -1

    await send_progress(prog,"📤 Uploading…")
    await update.message.reply_document(open(out,"rb"), filename="audio_replaced.mp4")
    await prog.delete()
    inp.unlink(missing_ok=True); out.unlink(missing_ok=True)
    context.user_data.clear()
    return -1

# ─────────────────────────────────────────────
# /join
# ─────────────────────────────────────────────

async def join_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎞️ Send the *first* video.", parse_mode=ParseMode.MARKDOWN)
    return JOIN_FIRST

async def join_first(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prog = await update.message.reply_text("⏳ Saving first video…")
    v1   = await download_file(update, context, suffix="_1.mp4")
    context.user_data["join_v1"] = str(v1)
    await send_progress(prog,"✅ First video saved! Now send the *second* video.")
    return JOIN_SECOND

async def join_second(update: Update, context: ContextTypes.DEFAULT_TYPE):
    v1   = context.user_data.get("join_v1")
    prog = await update.message.reply_text("⏳ Saving second video…")
    v2   = await download_file(update, context, suffix="_2.mp4")
    out  = TMPDIR / "joined.mp4"
    lst  = TMPDIR / "filelist.txt"
    lst.write_text(f"file '{v1}'\nfile '{str(v2)}'\n")

    await send_progress(prog,"🎞️ Joining videos…")
    r = run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(lst),
             "-c","copy", str(out)])

    if r.returncode != 0 or not out.exists():
        await send_progress(prog,f"❌ Failed.\n`{r.stderr[-400:]}`")
        return -1

    await send_progress(prog,"📤 Uploading…")
    await update.message.reply_document(open(out,"rb"), filename="joined.mp4")
    await prog.delete()
    Path(v1).unlink(missing_ok=True); v2.unlink(missing_ok=True)
    out.unlink(missing_ok=True); lst.unlink(missing_ok=True)
    context.user_data.clear()
    return -1

# ─────────────────────────────────────────────
# /download
# ─────────────────────────────────────────────

async def download_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("🚀 Usage: `/download <url>`", parse_mode=ParseMode.MARKDOWN)
        return

    url  = context.args[0]
    prog = await update.message.reply_text(f"⏳ Downloading from:\n`{url}`", parse_mode=ParseMode.MARKDOWN)
    out  = str(TMPDIR / "%(title)s.%(ext)s")

    r = run(["yt-dlp","--no-playlist","-o", out, url])
    if r.returncode != 0:
        await send_progress(prog,f"❌ Download failed.\n`{r.stderr[-500:]}`")
        return

    # find downloaded file
    files = list(TMPDIR.glob("*"))
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        await send_progress(prog,"❌ No file found after download.")
        return

    latest = files[0]
    await send_progress(prog,"📤 Uploading…")
    await update.message.reply_document(open(latest,"rb"), filename=latest.name)
    await prog.delete()
    latest.unlink(missing_ok=True)

# ─────────────────────────────────────────────
# /rename
# ─────────────────────────────────────────────

async def rename_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✏️ Send the file you want to rename.")
    return RENAME_FILE

async def rename_receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    doc = msg.document or msg.video or msg.audio or msg.photo
    if not doc:
        await msg.reply_text("⚠️ Please send a valid file.")
        return RENAME_FILE

    prog = await msg.reply_text("⏳ Saving file…")
    f    = await download_file(update, context)
    context.user_data["rename_src"] = str(f)
    # Determine original extension
    orig_name = getattr(doc, "file_name", None) or f.name
    context.user_data["rename_ext"] = Path(orig_name).suffix
    await send_progress(prog,"✅ File saved! Now send the new filename (with or without extension).")
    return RENAME_NAME

async def rename_receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    src  = Path(context.user_data.get("rename_src",""))
    ext  = context.user_data.get("rename_ext","")
    name = update.message.text.strip()
    if not Path(name).suffix:
        name += ext

    prog = await update.message.reply_text("📤 Uploading renamed file…")
    await update.message.reply_document(open(src,"rb"), filename=name)
    await prog.delete()
    src.unlink(missing_ok=True)
    context.user_data.clear()
    return -1

# ─────────────────────────────────────────────
# /zip  /unzip
# ─────────────────────────────────────────────

async def zip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg.document:
        await msg.reply_text("📦 Send the file attached with /zip command.")
        return

    prog = await msg.reply_text("⏳ Downloading…")
    inp  = await download_file(update, context)
    out  = TMPDIR / f"{inp.name}.zip"

    await send_progress(prog,"📦 Zipping…")
    r = run(["zip","-j", str(out), str(inp)])
    if r.returncode != 0 or not out.exists():
        await send_progress(prog,"❌ Zip failed.")
        return

    await send_progress(prog,"📤 Uploading ZIP…")
    await msg.reply_document(open(out,"rb"), filename=out.name)
    await prog.delete()
    inp.unlink(missing_ok=True); out.unlink(missing_ok=True)

async def unzip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg.document:
        await msg.reply_text("📦 Send the .zip file attached with /unzip command.")
        return

    prog = await msg.reply_text("⏳ Downloading…")
    inp  = await download_file(update, context, suffix=".zip")
    dest = TMPDIR / f"unzipped_{inp.stem}"
    dest.mkdir(exist_ok=True)

    await send_progress(prog,"📦 Unzipping…")
    r = run(["unzip","-o", str(inp), "-d", str(dest)])
    if r.returncode != 0:
        await send_progress(prog,"❌ Unzip failed.")
        return

    files = list(dest.iterdir())
    if not files:
        await send_progress(prog,"❌ No files found in archive.")
        return

    await send_progress(prog,"📤 Uploading extracted files…")
    for f in files[:10]:  # cap at 10 files
        await msg.reply_document(open(f,"rb"), filename=f.name)
    await prog.delete()
    inp.unlink(missing_ok=True)
    for f in files: f.unlink(missing_ok=True)
    dest.rmdir()

# ─────────────────────────────────────────────
# Inline button callback (future extensibility)
# ─────────────────────────────────────────────

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(f"You selected: {query.data}")