# 发现者（Discoverer）— 后端 Dockerfile
FROM python:3.11-slim

# 系统依赖：weasyprint + 中文字体 + 编译工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 \
    libffi-dev libcairo2 libcairo2-dev libpango1.0-dev \
    libgdk-pixbuf-2.0-dev shared-mime-info fonts-noto-cjk \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 应用代码
COPY backend/ /app/
COPY data/ /app/data/
WORKDIR /app

# 数据目录（运行时挂载覆盖）
RUN mkdir -p /app/data/daily /app/data/signals /app/data/indices

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/system/status || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
