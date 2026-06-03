FROM mwader/static-ffmpeg:7.1.1 AS ffmpeg

FROM python:3.13-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_PYTHON_DOWNLOADS=0 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project --no-editable

COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.13-slim-bookworm AS runtime

LABEL org.opencontainers.image.source=https://github.com/bueckerlars/vshift

COPY --from=ffmpeg /ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg /ffprobe /usr/local/bin/ffprobe

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY config ./config

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["vshift-server"]
