# FxOCRbot. One image for every front-end; the compose service picks the command.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LITEPARSE_MODEL_DIR=/opt/models \
    HOME=/tmp

RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin fxocr \
 && mkdir -p /opt/models

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir '.[bot]' && rm -rf /root/.cache

# OCRia-nano-1 weights are NOT part of this repo and have their own licence (docs/engines.md).
# They are downloaded only when explicitly requested: docker compose build --build-arg WITH_OCRIA_NANO=1
ARG WITH_OCRIA_NANO=0
RUN if [ "$WITH_OCRIA_NANO" = "1" ]; then lit models pull ocria-nano; fi

USER 10001
CMD ["fxocr-bot"]
