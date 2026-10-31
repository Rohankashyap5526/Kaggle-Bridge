FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCP_TRANSPORT=streamable-http \
    KAGGLE_BRIDGE_DATA_DIR=/data

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
RUN useradd --create-home --uid 10001 appuser && \
    mkdir -p /data && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 8000
CMD ["python", "server.py"]
