FROM python:3.11-slim

ENV LANG=ko_KR.UTF-8
ENV LC_ALL=ko_KR.UTF-8

# 시스템 패키지
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jre-headless \
    libreoffice \
    libreoffice-writer \
    locales \
    fonts-noto-cjk \
    fonts-nanum \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libxcb1 \
    libgomp1 \
    curl \
 && sed -i '/ko_KR.UTF-8/s/^# //g' /etc/locale.gen \
 && locale-gen \
 && fc-cache -f -v \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# CPU-only 운영으로 고정한다.
# sentence-transformers가 torch를 필요로 하므로
# Docker 빌드에서 CPU wheel을 명시 설치해 재현 가능성을 유지한다.
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    torch==2.10.0

RUN pip install --no-cache-dir -r requirements.txt

COPY . .
