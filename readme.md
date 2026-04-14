# 🎬 Video Tools Bot

A full-featured Telegram bot for video editing, extraction, downloading, and more.

---

## 📋 Commands

| Command | Description |
|---|---|
| `/compress` | Compress video with HEVC H.265 |
| `/trim <start> <end>` | Trim video e.g. `/trim 00:00:10 00:01:00` |
| `/ss [timestamp]` | Single screenshot e.g. `/ss 00:00:05` |
| `/ss12` | 12 screenshots at equal intervals |
| `/audio` | Extract MP3 from video |
| `/sub` | Extract soft subtitles as .srt |
| `/watermark` | Add logo/image watermark (2-step: send logo → send video) |
| `/addsub` | Soft-code .srt subtitles into video (2-step: send SRT → send video) |
| `/mixaudio` | Replace video audio (2-step: send audio → send video) |
| `/join` | Join two videos (2-step: send video1 → send video2) |
| `/download <url>` | Download from YouTube, Instagram, direct links |
| `/rename` | Rename any file (2-step: send file → send new name) |
| `/zip` | Zip a file |
| `/unzip` | Unzip a .zip file |
| `/cancel` | Cancel current multi-step operation |
| `/help` | Show all commands |

---

## 🚀 Deployment on Heroku (Docker / Container Stack)

### Prerequisites
- [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli) installed
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- Git installed

### Steps

```bash
# 1. Clone / create your repo
git init
git add .
git commit -m "Initial commit"

# 2. Login to Heroku
heroku login

# 3. Create a new Heroku app
heroku create your-app-name

# 4. Set the stack to container (for Docker)
heroku stack:set container -a your-app-name

# 5. Set your bot token as an environment variable
heroku config:set BOT_TOKEN=your_telegram_bot_token_here -a your-app-name

# 6. Push to Heroku
git push heroku main

# 7. Scale the worker dyno (it's a background worker, NOT a web process)
heroku ps:scale worker=1 -a your-app-name

# 8. Check logs
heroku logs --tail -a your-app-name
```

---

## 🐳 Run with Docker Locally

```bash
# Build image
docker build -t video-bot .

# Run container
docker run -e BOT_TOKEN=your_token_here video-bot
```

---

## 💻 Run Locally (without Docker)

### Requirements
- Python 3.11+
- `ffmpeg` installed (`sudo apt install ffmpeg` or `brew install ffmpeg`)
- `zip` / `unzip` utilities
- `yt-dlp` (installed via pip)

```bash
# Install Python dependencies
pip install -r requirements.txt

# Set env variable
export BOT_TOKEN=your_telegram_bot_token_here

# Run
python bot.py
```

---

## ⚠️ Notes

- **File Size Limit**: Telegram bots can only send/receive files up to **50 MB** without the Bot API server. For larger files, consider self-hosting the [Bot API server](https://core.telegram.org/bots/api#using-a-local-bot-api-server).
- **Heroku Ephemeral Storage**: Heroku dynos use temporary storage. Files are processed and deleted immediately — this is by design.
- **yt-dlp**: YouTube/Instagram downloads depend on `yt-dlp` being up to date. If downloads break, run `pip install -U yt-dlp`.
- **Heroku Free Tier**: Heroku no longer has a free tier. Use the Eco dyno ($5/month) or the Basic dyno.

---

## 📁 File Structure

```
video_bot/
├── bot.py           # Main entry point, registers all handlers
├── handlers.py      # All command handler functions
├── requirements.txt # Python dependencies
├── Dockerfile       # Docker image definition
├── heroku.yml       # Heroku container deployment config
├── Procfile         # Heroku process definition (fallback)
├── runtime.txt      # Python version for Heroku
└── .gitignore
```
