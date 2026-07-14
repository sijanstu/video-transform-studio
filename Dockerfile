FROM python:3.11-slim

WORKDIR /app

# FFmpeg is required by the app and is not in the slim image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Hosts (Render, Hugging Face Spaces, Fly, Cloud Run) inject $PORT.
ENV PORT=7860
EXPOSE 7860

CMD gunicorn --bind 0.0.0.0:${PORT} --workers 1 --timeout 300 app:app
