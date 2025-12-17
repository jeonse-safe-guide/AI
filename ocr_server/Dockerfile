# 1. Python 3.10 (EasyOCR 호환성 위해 3.10 추천)
FROM python:3.10-slim

# 2. 필수 시스템 패키지 설치 (이게 없으면 OCR 에러 남!)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 3. 작업 디렉토리 설정
WORKDIR /app

# 4. 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 소스 복사
COPY . .

# 6. 포트 노출 (문서화 용도)
EXPOSE 8000

# 7. 실행 명령
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]