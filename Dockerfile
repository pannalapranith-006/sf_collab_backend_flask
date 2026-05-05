FROM python:3.11-slim

WORKDIR /app

# =====================================================
# SYSTEM DEPENDENCIES
# =====================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-dejavu \
    fonts-liberation \
    fonts-freefont-ttf \
    libglib2.0-0 \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# =====================================================
# PYTHON DEPENDENCIES
# =====================================================
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gevent gevent-websocket

# =====================================================
# APP CODE
# =====================================================
COPY . .

# =====================================================
# ENVIRONMENT
# =====================================================
ENV PYTHONUNBUFFERED=1
ENV PORT=5000

# Gunicorn config for WebSockets
ENV GUNICORN_CMD_ARGS="\
    --bind=0.0.0.0:5000 \
    --workers=2 \
    --worker-class=geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
    --worker-connections=1000 \
    --timeout=120 \
    --log-level=info"


EXPOSE 5000

# =====================================================
# HEALTHCHECK
# =====================================================
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# =====================================================
# START
# =====================================================
RUN chmod +x /app/docker/entrypoint.sh
CMD ["gunicorn", "run:app"]
