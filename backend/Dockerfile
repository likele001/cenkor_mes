FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        default-libmysqlclient-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY backend/ .

RUN mkdir -p /app/data/storage

EXPOSE 8000

COPY docker/scripts/entrypoint-api.sh /entrypoint-api.sh
COPY docker/scripts/init-demo.sh /usr/local/bin/init-demo.sh
RUN chmod +x /entrypoint-api.sh /usr/local/bin/init-demo.sh

ENTRYPOINT ["/entrypoint-api.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
