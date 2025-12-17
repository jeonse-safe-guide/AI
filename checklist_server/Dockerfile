# 1. 가볍고 안정적인 Python 3.12 slim 버전 사용
FROM python:3.12-slim

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. 의존성 파일 먼저 복사 (캐싱 효율을 위해)
COPY requirements.txt .

# 4. 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# 5. 소스 코드 전체 복사
COPY . .

# 6. 포트 노출 (문서화 용도)
EXPOSE 8000

# 7. 서버 실행 명령
# 주의: Docker 안에서는 host를 반드시 "0.0.0.0"으로 설정해야 외부에서 접속 가능합니다.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]