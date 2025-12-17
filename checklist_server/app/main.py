from fastapi import FastAPI
from .api.endpoints import checklist

app = FastAPI(
    title="Checklist Server",
    version="0.1.0",
    description="전세 위험 분석 기반 체크리스트 생성 API 서버"
)

# 1. Health Check (간단해서 여기에 유지)
@app.get("/health")
def health():
    return {"status": "ok", "service": "Checklist Server"}

# 2. Router 등록
app.include_router(checklist.router, prefix="", tags=["Checklist"])