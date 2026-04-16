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

# paddlepaddle를 먼저 명시적으로 설치한다.
# paddleocr가 내부 의존성으로 paddleX를 설치할 때
# 이미 설치된 paddlepaddle 버전 기준으로 맞춰지므로
# PaddlePredictorOption API 불일치 문제를 방지한다.
RUN pip install --no-cache-dir \
    -i https://www.paddlepaddle.org.cn/packages/stable/cpu/ \
    paddlepaddle==3.2.0

# GPU 서버에서는 torch의 CUDA wheel 축이 중요하다.
# 기본 PyPI torch==2.7.0 경로는 cu126 조합으로 풀릴 수 있어
# ODL hybrid GPU 런타임에서 CUDA 불일치를 유발했다.
# 따라서 Docker 빌드 시 torch는 cu128 wheel로 명시 설치한다.
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cu128 \
    torch==2.10.0

RUN pip install --no-cache-dir -r requirements.txt

COPY . .
