# 发现者（Discoverer）— 后端 Dockerfile
# 锁定 Debian 12(bookworm)，避免最新 trixie 的包名变动导致 apt 失败
FROM python:3.11-slim-bookworm

# 换国内 apt 源（阿里云）—— 大陆服务器拉国外 Debian 源极慢，必换
RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g; s|http://security.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources; \
    fi; \
    if [ -f /etc/apt/sources.list ]; then \
        sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g; s|http://security.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list; \
    fi

# 系统依赖：weasyprint + 中文字体 + 编译工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
    libffi-dev libcairo2 libcairo2-dev libpango1.0-dev \
    libgdk-pixbuf-2.0-dev shared-mime-info fonts-noto-cjk \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖（国内 PyPI 源加速）
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -r /tmp/requirements.txt

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
