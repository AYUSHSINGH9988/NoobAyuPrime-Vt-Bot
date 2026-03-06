import os
import time
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import yt_dlp
import tools # Humara video processing engine (tools.py)

# Environment Variables for Hugging Face
API_ID = os.environ.get("API_ID", "YOUR_API_ID")
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")

app = Client("AyuPrimeBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Ensure downloads directory exists
os.makedirs("downloads", exist_ok=True)

# State Management Dictionaries
user_data = {}   # To store downloaded file paths temporarily
user_states = {} # To track if bot is waiting for user's reply (like rename, trim)

# ==========================================
# 1. START COMMAND
# ==========================================
@app.on_message(filters.command("start"))
async def start_cmd(client, message: Message):
    welcome_text = (
        "🔥 **AyuPrime Video Tools Bot me aapka swagat hai!**\n\n"
        "Mujhe koi bhi Video file, Document, ya (YouTube/Insta) ka URL bhejo aur magic dekho."
    )
    await message.reply_text(welcome_text)

# ==========================================
# 2. URL DOWNLOADER (yt-dlp)
# ==========================================
@app.on_message(filters.text & filters.regex(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"))
async def handle_url(client, message: Message):
    status_msg = await message.reply_text("🔗 Link detect hua! Download kar raha hoon...")
    url = message.text
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': f'downloads/{message.from_user.id}_%(title)s.%(ext)s',
        'quiet': True
    }
    
    try:
        def download_vid():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)
        
        file_path = await asyncio.to_thread(download_vid)
        user_data[message.from_user.id] = {"file_path": file_path}
        await send_options(message.chat.id, status_msg)
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Download failed: {str(e)}")

# ==========================================
# 3. TELEGRAM FILE HANDLER
# ==========================================
@app.on_message(filters.video | filters.document)
async def handle_files(client, message: Message):
    status_msg = await message.reply_text("📥 File receive ho gayi! Server pe download kar raha hoon...")
    file_path = await message.download(file_name=f"downloads/{message.from_user.id}_{message.id}.mp4")
    
    user_data[message.from_user.id] = {"file_path": file_path}
    await send_options(message.chat.id, status_msg)

# ==========================================
# 4. INLINE MENU GENERATOR
# ==========================================
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

# ==========================================
# 5. BUTTON CLICK HANDLER (Immediate Actions)
# ==========================================
@app.on_callback_query()
async def callback_handler(client, query: CallbackQuery):
    user_id = query.from_user.id
    
    if user_id not in user_data or not os.path.exists(user_data[user_id]["file_path"]):
        await query.answer("❌ File nahi mili. Phir se bhejo.", show_alert=True)
        return

    input_file = user_data[user_id]["file_path"]
    action = query.data

    # Check if the action requires user input (State Management)
    if action == "rename":
        user_states[user_id] = {"action": "rename", "file_path": input_file}
        await query.message.edit_text("✏️ **Rename Mode:** Naya naam reply me bhejo (jaise: `My_Video.mp4`):")
        return
        
    elif action == "trim":
        user_states[user_id] = {"action": "trim", "file_path": input_file}
        await query.message.edit_text("✂️ **Trim Mode:** Time bhejo is format me `HH:MM:SS-HH:MM:SS`\nExample: `00:00:10-00:01:30`")
        return
        
    elif action == "watermark":
        user_states[user_id] = {"action": "watermark", "file_path": input_file}
        await query.message.edit_text("🖼️ **Watermark Mode:** Ek photo (Image/Document) reply me bhejo:")
        return

    # Immediate Actions Processing
    await query.message.edit_text(f"⏳ Processing: `{action}`. Kripya wait karein...")
    output_file = f"downloads/output_{user_id}.mp4"
    result_path = None
    is_video = True

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
            
        if not result_path:
            await query.message.edit_text("❌ Processing me error aayi.")
            return

        await query.message.edit_text("📤 Processing complete! Uploading...")

        # Strict Video Upload
        if is_video:
            thumb = tools.generate_thumbnail(result_path, f"downloads/thumb_{user_id}.jpg")
            duration = tools.get_duration(result_path)
            
            await client.send_video(
                chat_id=query.message.chat.id,
                video=result_path,
                thumb=thumb,
                duration=duration,
                supports_streaming=True, 
                caption="**Processed by AyuPrime** ✅"
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
        # Cleanup
        if os.path.exists(input_file):
            os.remove(input_file)
        if result_path and result_path != input_file and os.path.exists(result_path):
            os.remove(result_path)
        if user_id in user_data:
            del user_data[user_id]
        await query.message.delete()

# ==========================================
# 6. ADVANCED REPLY HANDLER (Rename, Trim, Watermark)
# ==========================================
@app.on_message((filters.text | filters.photo | filters.document) & ~filters.command(["start"]))
async def process_user_reply(client, message: Message):
    user_id = message.from_user.id
    
    if user_id not in user_states:
        return # Not waiting for this user
        
    state = user_states[user_id]
    action = state["action"]
    input_file = state["file_path"]
    
    status_msg = await message.reply_text(f"⏳ Processing your `{action}` request...")
    output_file = f"downloads/output_{user_id}.mp4"
    result_path = None
    
    try:
        if action == "rename" and message.text:
            new_name = message.text.strip()
            if new_name.startswith("http"):
                await status_msg.edit_text("❌ Link nahi, naya naam bhejo.")
                return
            result_path = f"downloads/{new_name}"
            os.rename(input_file, result_path) 
            
        elif action == "trim" and message.text:
            times = message.text.strip().split("-")
            if len(times) != 2:
                await status_msg.edit_text("❌ Format galat hai. Use: `HH:MM:SS-HH:MM:SS`")
                return
            result_path = await tools.trim_video(input_file, output_file, times[0], times[1])
            
        elif action == "watermark" and (message.photo or message.document):
            await status_msg.edit_text("📥 Downloading watermark image...")
            watermark_file = await message.download(file_name=f"downloads/wm_{user_id}.png")
            
            await status_msg.edit_text("🖼️ Applying watermark... (CPU heavy task)")
            result_path = await tools.add_watermark(input_file, watermark_file, output_file)
            os.remove(watermark_file)
            
        else:
            await status_msg.edit_text("❌ Galat input format.")
            return

        if result_path and os.path.exists(result_path):
            await status_msg.edit_text("📤 Uploading your processed video...")
            thumb = tools.generate_thumbnail(result_path, f"downloads/thumb_{user_id}.jpg")
            duration = tools.get_duration(result_path)
            
            await client.send_video(
                chat_id=message.chat.id,
                video=result_path,
                thumb=thumb,
                duration=duration,
                supports_streaming=True, 
                caption=f"**AyuPrime Tool:** `{action.capitalize()}` ✅",
                reply_to_message_id=message.id
            )
            
            if result_path != input_file:
                os.remove(result_path)
            if thumb and os.path.exists(thumb):
                os.remove(thumb)

    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")
        
    finally:
        if user_id in user_states:
            del user_states[user_id]
        if os.path.exists(input_file):
            os.remove(input_file)
        if user_id in user_data:
            del user_data[user_id]
        await status_msg.delete()

if __name__ == "__main__":
    print("AyuPrime Bot is running...")
    app.run()
