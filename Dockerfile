FROM python:3.10-slim

WORKDIR /app

# Install FFmpeg for video processing
RUN apt-get update && \
    apt-get install -y ffmpeg wget curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Downloads directory
RUN mkdir -p downloads

# Hugging Face health check ke liye port expose karna
EXPOSE 7860

CMD ["python", "bot.py"]
