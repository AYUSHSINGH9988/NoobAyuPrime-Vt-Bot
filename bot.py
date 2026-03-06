import os
import time
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import tools # Humara banaya hua engine
import yt_dlp

# Environment Variables for Hugging Face
API_ID = os.environ.get("API_ID", "YOUR_API_ID")
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")

app = Client("AyuPrimeBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Temporary storage for user states
user_data = {}

@app.on_message(filters.command("start"))
async def start_cmd(client, message: Message):
    welcome_text = (
        "🔥 **AyuPrime Video Tools Bot me aapka swagat hai!**\n\n"
        "Mujhe koi bhi Video file, Document, ya (YouTube/Insta) ka URL bhejo aur magic dekho."
    )
    await message.reply_text(welcome_text)

# Handle URLs for Downloading (Feature: URL Downloader)
@app.on_message(filters.text & filters.regex(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"))
async def handle_url(client, message: Message):
    status_msg = await message.reply_text("🔗 Link detect hua! Download kar raha hoon...")
    url = message.text
    
    # yt-dlp options for best video quality
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': f'downloads/{message.from_user.id}_%(title)s.%(ext)s',
        'quiet': True
    }
    
    try:
        # Run yt-dlp in a separate thread so it doesn't block the bot
        def download_vid():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)
        
        file_path = await asyncio.to_thread(download_vid)
        
        user_data[message.from_user.id] = {"file_path": file_path}
        await send_options(message.chat.id, status_msg)
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Download failed: {str(e)}")


# Handle Telegram Files (Videos & Documents)
@app.on_message(filters.video | filters.document)
async def handle_files(client, message: Message):
    status_msg = await message.reply_text("📥 File receive ho gayi! Telegram se download kar raha hoon...")
    
    # Ensure directory exists
    os.makedirs("downloads", exist_ok=True)
    file_path = await message.download(file_name=f"downloads/{message.from_user.id}_{message.id}.mp4")
    
    user_data[message.from_user.id] = {"file_path": file_path}
    await send_options(message.chat.id, status_msg)

# Helper: Send the Advanced Menu
async def send_options(chat_id, status_msg: Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📉 Compress (HEVC)", callback_data="compress"),
         InlineKeyboardButton("🎵 Extract Audio", callback_data="extract_audio")],
        [InlineKeyboardButton("✂️ Trim Video", callback_data="trim"),
         InlineKeyboardButton("📸 Screenshot", callback_data="screenshot")],
        [InlineKeyboardButton("🖼️ Add Watermark", callback_data="watermark"),
         InlineKeyboardButton("✏️ Rename", callback_data="rename")],
        [InlineKeyboardButton("📤 Upload As Is", callback_data="upload_direct")]
    ])
    await status_msg.edit_text("⚙️ **AyuPrime Processing Menu:**\nSelect the tool you want to use:", reply_markup=keyboard)


# Handle Button Clicks
@app.on_callback_query()
async def callback_handler(client, query: CallbackQuery):
    user_id = query.from_user.id
    
    if user_id not in user_data or not os.path.exists(user_data[user_id]["file_path"]):
        await query.answer("❌ File nahi mili. Phir se bhejo.", show_alert=True)
        return

    input_file = user_data[user_id]["file_path"]
    action = query.data
    await query.message.edit_text(f"⏳ Processing: `{action}`. Kripya wait karein...")

    output_file = f"downloads/output_{user_id}.mp4"
    result_path = None
    is_video = True # Flag to check if final output is video

    try:
        if action == "compress":
            result_path = await tools.compress_video(input_file, output_file)
        
        elif action == "extract_audio":
            output_file = f"downloads/output_{user_id}.mp3"
            result_path = await tools.extract_audio(input_file, output_file)
            is_video = False
            
        elif action == "screenshot":
            output_file = f"downloads/thumb_{user_id}.jpg"
            result_path = tools.generate_thumbnail(input_file, output_file)
            is_video = False
            
        elif action == "upload_direct":
            result_path = input_file
            
        # (Yahan Trim aur Watermark ke liye hume user se time/image maangni hogi next message me, 
        # abhi architecture set karne ke liye hum direct process assume kar rahe hain)
        
        if not result_path:
            await query.message.edit_text("❌ Processing me error aayi.")
            return

        await query.message.edit_text("📤 Processing complete! Uploading...")

        # Final Upload Logic - strictly uploading as Video for video files
        if is_video:
            thumb = tools.generate_thumbnail(result_path, f"downloads/thumb_{user_id}.jpg")
            duration = tools.get_duration(result_path)
            
            await client.send_video(
                chat_id=query.message.chat.id,
                video=result_path,
                thumb=thumb,
                duration=duration,
                supports_streaming=True, # No Document Format!
                caption="**Processed by AyuPrime Video Tools** ✅"
            )
            if thumb and os.path.exists(thumb):
                os.remove(thumb)
                
        elif action == "extract_audio":
            await client.send_audio(chat_id=query.message.chat.id, audio=result_path)
            
        elif action == "screenshot":
            await client.send_photo(chat_id=query.message.chat.id, photo=result_path)

    except Exception as e:
        await query.message.edit_text(f"❌ Error: {str(e)}")

    finally:
        # Cleanup storage to keep that 50GB free!
        if os.path.exists(input_file):
            os.remove(input_file)
        if result_path and result_path != input_file and os.path.exists(result_path):
            os.remove(result_path)
        if user_id in user_data:
            del user_data[user_id]
        
        await query.message.delete()
