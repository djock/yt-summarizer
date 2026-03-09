FROM python:3.11-slim AS builder

ARG WHISPER_CPP_REF=master

RUN apt-get update && apt-get install -y \
    build-essential cmake git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN git clone --depth 1 --branch ${WHISPER_CPP_REF} https://github.com/ggerganov/whisper.cpp . && \
    cmake -B build && \
    cmake --build build -j --config Release && \
    cp build/bin/whisper-cli . && \
    sh ./models/download-ggml-model.sh small

FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg curl nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /build/whisper-cli /app/whisper-cli
COPY --from=builder /build/models/ggml-small.bin /app/models/ggml-small.bin

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py /app/
RUN mkdir -p /data /app/models

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import config, fetch, notify, summarize, state, transcribe" || exit 1

CMD ["python", "summarizer.py"]
