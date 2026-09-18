FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先装依赖，利用层缓存
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY pytest.ini ./pytest.ini

EXPOSE 8000

# 容器内默认连接 compose 中的 PostgreSQL（DATABASE_URL 已与服务名对齐）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
