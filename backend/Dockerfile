FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# pywin32는 Linux 컨테이너에서는 스킵됨 (조건부 의존성)
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# DB 디렉토리 생성
RUN mkdir -p /app/data

EXPOSE 8000

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
