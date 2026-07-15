# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Stage 1 : builder - installation des dependances Python
# ---------------------------------------------------------------------------
FROM python:3.10-slim AS builder

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY app/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2 : image finale, minimale et non-root
# ---------------------------------------------------------------------------
FROM python:3.10-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --shell /bin/false --create-home appuser

WORKDIR /app

COPY --from=builder /install /usr/local
COPY app/ /app/

RUN chown -R appuser:appgroup /app

USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 5000

CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:5000", "app:app"]
