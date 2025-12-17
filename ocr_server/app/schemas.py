from pydantic import BaseModel, Field
from typing import List, Optional, Union

# 1. 표제부 (Title)
class TitleInfo(BaseModel):
    road_address: str = Field(..., description="도로명 주소")
    jibun_address: Optional[str] = Field(None, description="지번 주소")
    building_name: Optional[str] = Field(None, description="건물명")
    exclusive_area: Optional[str] = Field(None, description="전유 면적 (㎡)")
    building_usage: Optional[str] = Field(None, description="건물 용도")
    dong: Optional[str] = Field(None, description="동")
    ho: Optional[str] = Field(None, description="호수")

# 2. 갑구 (Gaggu - 소유권 및 침해)
class GagguItem(BaseModel):
    type: str = Field(..., description="권리 유형 (ownership_transfer, provisional_seizure 등)")
    registration_purpose: Optional[str] = Field(None, description="등기 목적")
    # 소유권 관련
    owner_name: Optional[str] = Field(None, description="소유자명")
    owner_ssn_prefix: Optional[str] = Field(None, description="주민번호 앞자리")
    # 침해 관련
    rights_holder: Optional[str] = Field(None, description="권리자(채권자)")
    debt_amount: Optional[float] = Field(None, description="청구금액")

# 3. 을구 (Eulgu - 근저당 등)
class EulguItem(BaseModel):
    type: str = Field(..., description="권리 유형 (mortgage 등)")
    registration_purpose: Optional[str] = Field(None, description="등기 목적")
    debt_max_amount: Optional[float] = Field(None, description="채권최고액")
    debtor: Optional[str] = Field(None, description="채무자")
    creditor: Optional[str] = Field(None, description="채권자(근저당권자)")

# 4. 전체 데이터 구조
class OCRResponseData(BaseModel):
    title: TitleInfo
    gaggu: List[GagguItem] = []
    eulgu: List[EulguItem] = []
    rawText: Optional[str] = Field(None, description="원본 텍스트")

# 5. 최종 응답 래퍼
class OCRResponse(BaseModel):
    data: OCRResponseData