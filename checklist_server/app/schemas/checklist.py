from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from enum import Enum

# ============================================
# Risk Code Whitelist
# ============================================
class RiskCode(str, Enum):
    HIGH_RATIO = "HIGH_RATIO"
    MEDIUM_RATIO = "MEDIUM_RATIO"
    VIOLATION = "VIOLATION"
    RESTRICTION = "RESTRICTION"
    AUCTION = "AUCTION"
    PROVISIONAL_REG = "PROVISIONAL_REG"
    TRUST = "TRUST"
    MORTGAGE_HIGH = "MORTGAGE_HIGH"
    MORTGAGE_MEDIUM = "MORTGAGE_MEDIUM"
    HIGH_DEBT_RATIO = "HIGH_DEBT_RATIO"
    OTHER_RIGHTS = "OTHER_RIGHTS"
    OWNERSHIP_TRANSFER_EXISTS = "OWNERSHIP_TRANSFER_EXISTS"
    MARKET_PRICE_NOT_FOUND = "MARKET_PRICE_NOT_FOUND"
    BUILDING_LEDGER_NOT_FOUND = "BUILDING_LEDGER_NOT_FOUND"
    OWNER_MISMATCH = "OWNER_MISMATCH"
    USAGE_MISMATCH = "USAGE_MISMATCH"
    AREA_MISMATCH = "AREA_MISMATCH"

# ============================================
# Request Models
# ============================================
SeverityType = Literal["DANGER", "WARNING", "SAFE"]

class RiskItem(BaseModel):
    code: RiskCode = Field(..., description="위험 요소 코드")
    msg: str = Field(..., description="위험 요소 설명 메시지")
    severity: Optional[SeverityType] = Field(
        None,
        description="위험도 등급 (DANGER, WARNING, SAFE). 생략 시 후처리 가능"
    )

class ChecklistRequest(BaseModel):
    risks: List[RiskItem] = Field(
        default_factory=list,
        description="위험 요소 리스트 (RiskItem 배열)"
    )
    inputPrice: int = Field(
        gt=0,
        description="전세 보증금 (원 단위, 양의 정수)"
    )

# ============================================
# Response Models
# ============================================
CategoryType = Literal["registry", "contract", "site", "pre_contract"]

class ChecklistItem(BaseModel):
    id: int = Field(..., description="체크리스트 항목 고유 ID (1부터 시작)")
    category: CategoryType = Field(..., description="카테고리: registry / contract / site / pre_contract")
    title: str = Field(..., description="체크리스트 제목")
    description: Optional[str] = Field(
        None,
        description="체크리스트 상세 설명 (없을 수 있음)"
    )

class ChecklistResponse(BaseModel):
    items: List[ChecklistItem] = Field(
        ...,
        description="최종 생성된 체크리스트 항목 배열"
    )

class ErrorResponse(BaseModel):
    message: str = Field(..., description="에러 메시지")
    error: str = Field(..., description="오류 상세 정보")