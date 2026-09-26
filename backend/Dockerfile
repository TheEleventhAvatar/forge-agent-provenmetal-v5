# =========================
# Stage 1: Python dependencies
# =========================
FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

COPY requirements.txt .

RUN pip install \
    --no-cache-dir \
    --prefix=/install \
    -r requirements.txt


# =========================
# Stage 2: Runtime
# =========================
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

# KiCad + minimal recommended packages
RUN apt-get update \
    && echo "deb http://deb.debian.org/debian bookworm-backports main" \
        > /etc/apt/sources.list.d/backports.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        -t bookworm-backports \
        kicad \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies from builder
COPY --from=builder /install /usr/local

WORKDIR /app

COPY app ./app

EXPOSE 10000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]