import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Settings:
    # 프로젝트 루트 (app 폴더의 상위)
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    
    # 템플릿 디렉토리 (app/templates)
    TEMPLATE_DIR = BASE_DIR / "app" / "templates"

    # API Keys & Mode
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    MOCK_MODE = os.getenv("LLM_MOCK_MODE", "false").lower() == "true"

settings = Settings()