FROM python:3.11-slim

# 시스템 패키지
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jre-headless \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libxcb1 \
    libgomp1 \
    curl \
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

RUN pip install --no-cache-dir -r requirements.txt

COPY . .
