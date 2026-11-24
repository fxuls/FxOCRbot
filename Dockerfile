# FxOCRbot. One image for every front-end; the compose service picks the command.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LITEPARSE_MODEL_DIR=/opt/models \
    FXOCR_DATA_DIR=/data \
    HOME=/tmp

RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin fxocr \
 && mkdir -p /opt/models /data && chown 10001:10001 /data

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir '.[bot]' && rm -rf /root/.cache

# OCRia-nano-1 weights are NOT part of this repo and have their own licence (docs/engines.md).
# They are downloaded only when explicitly requested: WITH_OCRIA_NANO=1 in .env, or
# docker compose build --build-arg WITH_OCRIA_NANO=1. PP-OCRv6 models ship inside the rapidocr wheel.
ARG WITH_OCRIA_NANO=0
RUN if [ "$WITH_OCRIA_NANO" = "1" ]; then lit models pull ocria-nano; fi

USER 10001
CMD ["fxocr-bot"]
