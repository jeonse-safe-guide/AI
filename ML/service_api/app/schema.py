# app/schema.py
from pydantic import BaseModel
from typing import Optional, Dict, Any


class PredictRequest(BaseModel):
    road_address: Optional[str] = None     # 도로명주소
    jibun_address: Optional[str] = None    # 지번주소
    building_name: Optional[str] = None    # 아파트/건물명

    deposit_won: int                       # 원 단위
    area_m2: float
    floor: int


class PredictResponse(BaseModel):
    ok: bool
    method: Optional[str] = None
    risk_label: Optional[int] = None
    risk_prob: Optional[float] = None
    threshold: Optional[float] = None

    jeonse_ratio: Optional[float] = None
    official_price_avg: Optional[int] = None

    resolved: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    message: Optional[str] = None
