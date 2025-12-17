from fastapi import FastAPI
from pathlib import Path
from difflib import SequenceMatcher

from app.schema import PredictRequest, PredictResponse
from app.address import merge_address
from app.db import (
    db_ping,
    fetch_kapt_candidates,
    fetch_kapt_detail,
    fetch_latest_official_price_avg,
)
from app.model import ServiceModel

app = FastAPI(title="jeonse-risk-ai", version="v1")

MODEL: ServiceModel | None = None


def sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio() * 100.0


def pick_best_candidate(cands, address_text: str, apart_hint: str | None):
    """
    점수 낮아도 무조건 1등 선택.
    - apart_hint 있으면 kaptName vs apart_hint 유사도 가중
    - 아니면 kaptName vs address_text 유사도
    """
    if not cands:
        return None

    scored = []
    for c in cands:
        name = (c.get("kaptName") or "").strip()
        base_text = apart_hint.strip() if apart_hint and apart_hint.strip() else address_text
        score = sim(base_text, name)
        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best = scored[0]
    best["_match_score"] = float(best_score)
    return best


@app.on_event("startup")
def startup():
    global MODEL
    base = Path(__file__).resolve().parents[2]   # service_api/ -> ML/
    model_path = base / "models" / "lgb_service_v1.txt"
    meta_path  = base / "models" / "lgb_service_v1.meta.json"

    print("[BOOT] model_path:", model_path)
    print("[BOOT] meta_path :", meta_path)

    MODEL = ServiceModel(model_path=model_path, meta_path=meta_path)

    ping = db_ping()
    if not ping.get("ok"):
        print("[WARN] DB ping failed:", ping)
    else:
        print("[BOOT] DB ping OK")


@app.get("/health")
def health():
    return {"ok": True, "service": "jeonse-risk-ai", "port": 3003}


@app.get("/db_check")
def db_check():
    return db_ping()


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    # 0) 입력 합치기
    address_text = merge_address(req.road_address, req.jibun_address, req.building_name)

    # 1) 후보 조회
    cands = fetch_kapt_candidates(address_text=address_text, apart_hint=req.building_name)

    if not cands:
        # 후보 없으면 바로 fallback(공시가격도 bjdCode가 없어서 찾기 어려움)
        return PredictResponse(
            ok=False,
            error="KAPT_CANDIDATE_EMPTY",
            message="주소로 단지 후보를 찾지 못했습니다. apart(아파트명)을 함께 보내면 정확도가 올라갑니다.",
        )

    # 2) 무조건 1등 선택
    best = pick_best_candidate(cands, address_text, req.building_name)
    kaptCode = best["kaptCode"]
    bjdCode  = best["bjdCode"]
    match_score = best.get("_match_score", 0.0)

    resolved = {
        "kaptCode": kaptCode,
        "kaptName": best.get("kaptName"),
        "bjdCode": bjdCode,
        "sidoName": best.get("sidoName"),
        "sggName": best.get("sggName"),
        "emdName": best.get("emdName"),
        "auto_selected": True,
        "match_score": match_score,
    }

    # 3) 단지 상세 피처 조회
    detail = fetch_kapt_detail(kaptCode)

    # 3-A) 모델 예측 가능하면 모델로
    if detail:
        # meta.features에 맞춰 row를 만들어야 함
        # (없는 건 0으로 들어감)
        row = {
            "area_m2": req.area_m2,
            "floor": req.floor,
            "build_year": detail.get("build_year", detail.get("basic_kaptUsedate", 0)),
            "basic_hoCnt": detail.get("basic_hoCnt", 0),
            "basic_kaptDongCnt": detail.get("basic_kaptDongCnt", 0),
            "basic_kaptTopFloor": detail.get("basic_kaptTopFloor", 0),
            "dtl_kaptMgrCnt": detail.get("dtl_kaptMgrCnt", 0),
            "dtl_groundElChargerCnt": detail.get("dtl_groundElChargerCnt", 0),
            "dtl_undergroundElChargerCnt": detail.get("dtl_undergroundElChargerCnt", 0),
            # 파생 피처(네 meta에 있을 수 있어서 넣어줌)
            "floor_ratio": (req.floor / detail.get("basic_kaptTopFloor", 1)) if detail.get("basic_kaptTopFloor", 0) else 0,
            "building_age_years": 0,  # 계약연도 없으니 v1은 0 (원하면 백에서 계약월 받으면 개선 가능)
        }

        prob = MODEL.predict_proba(row)
        label = int(prob >= MODEL.threshold)

        return PredictResponse(
            ok=True,
            method="model",
            risk_label=label,
            risk_prob=prob,
            threshold=MODEL.threshold,
            resolved=resolved,
        )

    # 3-B) 단지 상세 없으면 전세가율 fallback
    op_avg = fetch_latest_official_price_avg(
        bjd_code=bjdCode,
        area_m2=req.area_m2,
        apt_name_hint=req.building_name
    )

    if not op_avg:
        return PredictResponse(
            ok=False,
            method="ratio_fallback",
            threshold=90.0,
            resolved=resolved,
            error="OFFICIAL_PRICE_NOT_FOUND",
            message="공시가격을 찾지 못했습니다. (면적/아파트명/주소를 확인해주세요.)",
        )

    jeonse_ratio = (req.deposit_won / op_avg) * 100.0
    label = int(jeonse_ratio >= 90.0)

    return PredictResponse(
        ok=True,
        method="ratio_fallback",
        risk_label=label,
        risk_prob=None,
        threshold=90.0,
        jeonse_ratio=jeonse_ratio,
        official_price_avg=op_avg,
        resolved=resolved,
    )
