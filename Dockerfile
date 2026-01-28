FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg build-essential cmake git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN git clone https://github.com/ggerganov/whisper.cpp . && \
    cmake -B build && \
    cmake --build build -j --config Release && \
    cp build/bin/whisper-cli . && \
    sh ./models/download-ggml-model.sh small

# Force upgrade yt-dlp to latest
RUN pip install -U yt-dlp google-genai requests

COPY summarizer.py .
RUN mkdir /data 

CMD ["python", "summarizer.py"]