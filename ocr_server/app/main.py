from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import shutil
import os
import uuid
import json

from .schemas import OCRResponse
from .llm_client import analyze_images_with_llm

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR = "/workspace/temp_uploads"
if os.path.exists(TEMP_DIR):
    shutil.rmtree(TEMP_DIR)
os.makedirs(TEMP_DIR, exist_ok=True)

@app.get("/health")
async def health_check():
    """
    서버 상태를 확인하는 헬스 체크 엔드포인트
    """
    return {
        "status": "ok",
        "service": "OCR Server"
    }

@app.post("/ocr", response_model=OCRResponse)
async def ocr_registry(documents: List[UploadFile] = File(...)):
    saved_file_paths = []
    
    try:
        # 1. 파일 저장
        for file in documents:
            file_ext = os.path.splitext(file.filename)[1]
            if not file_ext: file_ext = ".jpg"
            
            safe_filename = f"{uuid.uuid4()}{file_ext}"
            file_path = os.path.join(TEMP_DIR, safe_filename)
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            saved_file_paths.append(file_path)
        
        print(f"📂 분석 요청: {len(saved_file_paths)}장")

        # 2. LLM 분석 요청
        result = await analyze_images_with_llm(saved_file_paths)

        # 3. 에러 처리
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result["error"])

        response_data = result["text"]
        
        # 만약 JSON이 아니라 문자열(String)로 왔다면? (파싱 실패 시)
        # API 스키마를 맞추기 위해 강제로 기본 객체를 만들어줍니다.
        if isinstance(response_data, str):
            print("⚠️ 경고: AI 응답이 JSON이 아닙니다. 기본값으로 대체합니다.")
            response_data = {
                "title": {
                    "road_address": "주소 인식 실패 (원본 텍스트 참조)",
                    "jibun_address": "",
                    "building_name": "",
                    "exclusive_area": "",
                    "building_usage": "",
                    "dong": "",
                    "ho": ""
                },
                "gaggu": [],
                "eulgu": [],
                "rawText": response_data[:3000]
            }

        return result["text"]

    except Exception as e:
        print(f"SERVER ERROR: {e}")
        raise HTTPException(status_code=500, detail={"message": "OCR 처리 중 오류 발생", "error": str(e)})
    
    finally:
        # 파일 삭제
        for path in saved_file_paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass