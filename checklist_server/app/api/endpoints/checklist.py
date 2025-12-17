from fastapi import APIRouter, HTTPException

from app.services.generator import generate_checklist_llm, generate_checklist_mock
from app.schemas.checklist import ChecklistRequest, ChecklistResponse

router = APIRouter()

# -------------------------
# LLM 기반 체크리스트 생성
# -------------------------
@router.post("/generate", response_model=ChecklistResponse)
def generate(req: ChecklistRequest):
    try:
        # 서비스 로직 호출
        return generate_checklist_llm(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------
# MOCK 체크리스트 생성
# -------------------------
@router.post("/generate_mock", response_model=ChecklistResponse)
def generate_mock_api(req: ChecklistRequest):
    try:
        # 서비스 로직 호출
        return generate_checklist_mock(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))