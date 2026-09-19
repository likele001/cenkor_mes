FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

# 数据库驱动基于纯 Python 的 PyMySQL，无需 mysqlclient / gcc 编译链。
# 仅保留所需的运行时系统库：libgomp1 为 numpy/scipy/chromadb 等 OpenMP 所需。
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --upgrade pip --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip install --no-cache-dir -r requirements.txt --index-url https://pypi.tuna.tsinghua.edu.cn/simple

COPY backend/ .

RUN mkdir -p /app/data/storage

EXPOSE 8000

COPY docker/scripts/entrypoint-api.sh /entrypoint-api.sh
COPY docker/scripts/init-demo.sh /usr/local/bin/init-demo.sh
RUN chmod +x /entrypoint-api.sh /usr/local/bin/init-demo.sh

ENTRYPOINT ["/entrypoint-api.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]