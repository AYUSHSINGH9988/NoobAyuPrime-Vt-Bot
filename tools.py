import os
import time
import asyncio
import subprocess

# Helper: Asynchronous command execution
async def run_cmd(cmd):
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return process.returncode, stdout, stderr

# 1. Fast Compression (HEVC H.265)
async def compress_video(input_file, output_file):
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-i", input_file,
        "-c:v", "libx265", "-crf", "28", "-preset", "ultrafast", # Ultrafast for Hugging Face
        "-c:a", "aac", "-b:a", "128k",
        output_file
    ]
    await run_cmd(cmd)
    return output_file if os.path.exists(output_file) else None

# 2. Video Trimmer
async def trim_video(input_file, output_file, start_time, end_time):
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-ss", start_time, "-to", end_time,
        "-i", input_file,
        "-c", "copy", # Copying stream is instant, no re-encoding
        output_file
    ]
    await run_cmd(cmd)
    return output_file if os.path.exists(output_file) else None

# 3. Audio Extraction (Video to MP3)
async def extract_audio(input_file, output_file):
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-i", input_file,
        "-q:a", "0", "-map", "a",
        output_file
    ]
    await run_cmd(cmd)
    return output_file if os.path.exists(output_file) else None

# 4. Watermark Adder
async def add_watermark(video_file, watermark_file, output_file):
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-i", video_file, "-i", watermark_file,
        "-filter_complex", "overlay=W-w-10:H-h-10", # Bottom right corner
        "-c:a", "copy",
        output_file
    ]
    await run_cmd(cmd)
    return output_file if os.path.exists(output_file) else None

# 5. Metadata Extractors (Sync functions as they are very fast)
def get_duration(video_path):
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1", video_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
    try:
        return int(float(result.stdout.strip()))
    except ValueError:
        return 0

def generate_thumbnail(video_path, thumb_path):
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-ss", "00:00:02", "-i", video_path,
        "-vframes", "1",
        thumb_path
    ]
    subprocess.run(cmd)
    return thumb_path if os.path.exists(thumb_path) else None
