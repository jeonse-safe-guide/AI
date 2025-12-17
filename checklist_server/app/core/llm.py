from typing import Any, Optional
import google.generativeai as genai
from .config import settings

# 1) API 키 검증
if not settings.GEMINI_API_KEY and not settings.MOCK_MODE:
    raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되어 있지 않습니다.")

# 2) Gemini 설정
if not settings.MOCK_MODE:
    genai.configure(api_key=settings.GEMINI_API_KEY)


def _recursive_remove_key(d: Any, targets: list[str]):
    """
    딕셔너리(JSON 스키마)를 재귀적으로 탐색하며
    targets 리스트에 있는 키(예: title, $defs)를 삭제합니다.
    """
    if isinstance(d, dict):
        # 리스트 복사본으로 순회하며 삭제
        for key in list(d.keys()):
            if key in targets:
                del d[key]
        for value in d.values():
            _recursive_remove_key(value, targets)
    elif isinstance(d, list):
        for item in d:
            _recursive_remove_key(item, targets)


def generate_llm_response(
    model: str,
    contents: str,
    config: Optional[dict] = None,
    *,
    force_mock: bool = False,
) -> Any:
    """
    LLM 호출 wrapper.
    """
    # ------------------ 1) Mock 모드 ------------------
    if force_mock or settings.MOCK_MODE:
        return {
            "text": """
            {
                "items": [
                    {
                        "id": 1,
                        "category": "registry",
                        "title": "MOCK: 계약 당일 재발급한 등기부등본 최종 확인",
                        "description": "MOCK 모드: 전세금 보호를 위해 계약 당일 등기부등본을 재발급 받아 소유자·권리 변동 여부를 최종 확인하세요."
                    },
                    {
                        "id": 2,
                        "category": "pre_contract",
                        "title": "MOCK: 임대인 본인 계좌로만 계약금 송금",
                        "description": "MOCK 모드: 계약 전, 임대인의 명의와 동일한 계좌인지 확인하고 제3자 계좌 송금은 절대 금지하세요."
                    },
                    {
                        "id": 3,
                        "category": "site",
                        "title": "MOCK: 현장 방문 시 누수·결로 점검",
                        "description": "MOCK 모드: 집 내부의 누수, 결로, 곰팡이 여부를 직접 확인하고 문제 있으면 특약에 보수 기한을 명시하세요."
                    },
                    {
                        "id": 4,
                        "category": "contract",
                        "title": "MOCK: 보증금 반환 확약 특약 추가",
                        "description": "MOCK 모드: 전세계약서에 보증금 반환 기한 및 지연 시 이자 지급 등의 보호 특약을 반드시 포함하세요."
                    }
                ]
            }
            """
        }

   # ------------------ 2) 실제 LLM 호출 ------------------
    try:
        model_instance = genai.GenerativeModel(model)

        final_config = config.copy() if config else {}
        
        # 호환성: response_json_schema -> response_schema
        if "response_json_schema" in final_config:
            final_config["response_schema"] = final_config.pop("response_json_schema")
        
        # MIME type 기본값
        if "response_mime_type" not in final_config and "response_schema" in final_config:
            final_config["response_mime_type"] = "application/json"

        # [안전장치] 여전히 남아있을 수 있는 불필요한 키 제거
        if "response_schema" in final_config:
            # $ref를 유발하는 $defs나 title이 혹시 있다면 삭제
            _recursive_remove_key(final_config["response_schema"], ["title", "$defs"])

        response = model_instance.generate_content(
            contents,
            generation_config=final_config
        )
        return response
        
    except Exception as e:
        print(f"Gemini API Error Detail: {e}")
        raise RuntimeError(f"Gemini API 호출 실패: {e}")