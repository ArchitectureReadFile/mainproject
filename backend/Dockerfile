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
COPY constraints-cpu.txt .

# CPU-only 운영으로 고정한다.
# opendataloader/docling, sentence-transformers가 torch를 전이 의존성으로 끌어올 수 있어
# requirements 전체 설치를 CPU index + constraints로 함께 잠근다.
RUN pip install --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -c constraints-cpu.txt \
    -r requirements.txt

COPY . .
