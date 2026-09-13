FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Create application user new user for /data permissions sepereate from my current user data for assesment purpose 
RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data

ENV DATABASE_PATH=/data/app.db \
    PORT=5000 \
    LOG_LEVEL=INFO

VOLUME ["/data"]

EXPOSE 5000

HEALTHCHECK --interval=15s \
    --timeout=3s \
    --start-period=5s \
    --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run as non-root user
USER appuser

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
