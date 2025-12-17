# train_service_v1.py
from __future__ import annotations

from pathlib import Path
import json
import numpy as np
import pandas as pd

from sklearn.model_selection import GroupKFold
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    precision_recall_curve,
    confusion_matrix,
    classification_report,
)

import lightgbm as lgb


# =========================
# Config
# =========================
BASE_DIR = Path(__file__).resolve().parents[1]   # .../ML
SNAP_DIR = BASE_DIR / "data" / "snapshot"
OUT_DIR  = BASE_DIR / "models"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PARQUET_PATH = SNAP_DIR / "train_jeonse_risk_bin_tx.parquet"
CSV_PATH     = SNAP_DIR / "train_jeonse_risk_bin_tx.csv"

TARGET = "risk_label"
GROUP  = "kaptCode"
ID_COL = "id"

RANDOM_STATE = 42

# 서비스 입력: address(required), area_m2(optional), floor(optional)
# address는 모델에 직접 넣지 않고, address -> kaptCode 매칭 후 단지/입지 피처로 사용
SERVICE_OPTIONAL_INPUTS = ["area_m2", "floor"]

# 서비스에서 재현 가능한 베이스 피처들
# - 거래 시점 의존 피처(deal_ym 등)는 서비스 v1에서 제외
# - bjdCode는 과도하게 세분화되어 fold 변동/과적합 유발 가능 -> v1 제외 권장
SERVICE_BASE_FEATURES = [
    # user optional inputs
    "area_m2",
    "floor",

    # building/complex (DB에서 kaptCode로 조회 가능)
    "build_year",
    "basic_hoCnt",
    "basic_kaptDongCnt",
    "basic_kaptTopFloor",
    "basic_kaptUsedate",
    "basic_codeHeatNm",
    "basic_codeSaleNm",

    # detail
    "dtl_kaptMgrCnt",
    "dtl_groundElChargerCnt",
    "dtl_undergroundElChargerCnt",

    # location
    "sggName",
    "emdName",
]

# 서비스 파생 피처(서비스에서도 동일 계산 가능)
DERIVED_FEATURES = [
    "floor_ratio",
    "building_age_years",
]

# building_age_years 계산 기준 (훈련/추론 동일해야 함)
CURRENT_YEAR = 2025

# threshold 튜닝 목표
THRESHOLD_OBJECTIVE = "f1"
# 예: "recall_at_precision_0.7" 로 바꾸면 precision 0.7 이상에서 recall 최대 threshold 선택


# =========================
# Load
# =========================
def load_data() -> pd.DataFrame:
    if PARQUET_PATH.exists():
        df = pd.read_parquet(PARQUET_PATH)
        print(f"Loaded parquet: {PARQUET_PATH}")
    elif CSV_PATH.exists():
        df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
        print(f"Loaded csv: {CSV_PATH}")
    else:
        raise FileNotFoundError(f"snapshot 파일이 없습니다: {PARQUET_PATH} 또는 {CSV_PATH}")
    return df


# =========================
# Helpers
# =========================
def to_numeric_inplace(df: pd.DataFrame, cols: list[str]) -> None:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")


def add_missing_indicators(df: pd.DataFrame, cols: list[str]) -> list[str]:
    """결측 여부(0/1) 인디케이터 컬럼 추가. 원 컬럼은 NaN 유지."""
    added = []
    for c in cols:
        if c in df.columns:
            new_c = f"{c}_isna"
            df[new_c] = df[c].isna().astype(np.int8)
            added.append(new_c)
    return added


# =========================
# Feature engineering (service-safe)
# =========================
def add_service_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # numeric casting (NaN 유지)
    to_numeric_inplace(df, [
        "floor", "area_m2", "build_year",
        "basic_kaptTopFloor",
    ])

    # floor_ratio = floor / topfloor
    df["floor_ratio"] = df["floor"] / df["basic_kaptTopFloor"]
    df.loc[df["basic_kaptTopFloor"].isna() | (df["basic_kaptTopFloor"] <= 0), "floor_ratio"] = np.nan

    # building_age_years = CURRENT_YEAR - build_year
    df["building_age_years"] = (CURRENT_YEAR - df["build_year"]).clip(lower=0)

    return df


def clean_and_cast(df: pd.DataFrame, feature_cols: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """
    - 지정 feature만 남김
    - object/string -> category
    - 숫자형은 numeric으로 가능한 것만
    - 결측은 NaN 유지
    - 상수 컬럼 전역 제거
    """
    df = df.copy()

    keep = [c for c in [ID_COL, TARGET, GROUP] if c in df.columns] + feature_cols
    df = df[keep]

    # numeric candidates
    numeric_candidates = [
        "area_m2", "floor", "build_year",
        "basic_hoCnt", "basic_kaptDongCnt", "basic_kaptTopFloor",
        "dtl_kaptMgrCnt", "dtl_groundElChargerCnt", "dtl_undergroundElChargerCnt",
        "building_age_years", "floor_ratio",
        "area_m2_isna", "floor_isna", "dtl_kaptMgrCnt_isna",
        "dtl_groundElChargerCnt_isna", "dtl_undergroundElChargerCnt_isna",
    ]
    to_numeric_inplace(df, [c for c in numeric_candidates if c in df.columns])

    # category cols
    cat_cols = []
    for c in df.columns:
        if c in [ID_COL, TARGET, GROUP]:
            continue
        if df[c].dtype == "object" or str(df[c].dtype).startswith("string"):
            df[c] = df[c].astype("string").str.strip()
            df[c] = df[c].replace(["", "nan", "None", "<NA>"], pd.NA)
            df[c] = df[c].astype("category")
            cat_cols.append(c)

    # global constant drop
    X_tmp = df.drop(columns=[ID_COL, TARGET, GROUP], errors="ignore")
    nunique = X_tmp.nunique(dropna=False)
    const_cols = nunique[nunique <= 1].index.tolist()
    if const_cols:
        print(f"[INFO] Drop constant cols (global) {len(const_cols)}: {const_cols}")
        df = df.drop(columns=const_cols)
        cat_cols = [c for c in cat_cols if c not in const_cols]

    return df, cat_cols


def build_service_dataset(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    df = add_service_derived_features(df_raw)

    # 결측 인디케이터(서비스에서 옵션/미제공이 실제로 발생할 컬럼 중심)
    isna_cols = add_missing_indicators(df, [
        "area_m2",
        "floor",
        "dtl_kaptMgrCnt",
        "dtl_groundElChargerCnt",
        "dtl_undergroundElChargerCnt",
    ])

    feature_cols = [c for c in (SERVICE_BASE_FEATURES + DERIVED_FEATURES + isna_cols) if c in df.columns]
    df, cat_cols = clean_and_cast(df, feature_cols)

    final_features = [c for c in df.columns if c not in [ID_COL, TARGET, GROUP]]
    return df, final_features, cat_cols


# =========================
# Threshold tuning
# =========================
def find_threshold(y_true: np.ndarray, y_prob: np.ndarray, objective: str = "f1") -> float:
    prec, rec, thr = precision_recall_curve(y_true, y_prob)
    if len(thr) == 0:
        return 0.5

    if objective == "f1":
        f1 = 2 * (prec[:-1] * rec[:-1]) / (prec[:-1] + rec[:-1] + 1e-12)
        best_idx = int(np.nanargmax(f1))
        return float(thr[best_idx])

    if objective.startswith("recall_at_precision_"):
        p_target = float(objective.split("_")[-1])
        mask = prec[:-1] >= p_target
        if mask.any():
            idx_in_mask = int(np.nanargmax(rec[:-1][mask]))
            thr_idx = np.where(mask)[0][idx_in_mask]
            return float(thr[thr_idx])
        return 0.5

    return 0.5


# =========================
# Main
# =========================
def main():
    df_raw = load_data()
    print("Raw shape:", df_raw.shape)
    print("Label dist:\n", df_raw[TARGET].value_counts(dropna=False))

    df, feature_cols, cat_cols = build_service_dataset(df_raw)

    print("Service-v1 shape:", df.shape)
    print("Num features:", len(feature_cols))
    print("Categorical cols:", cat_cols)
    print("Features:", feature_cols)

    # ✅ X를 먼저 만든 뒤 missing rate 출력 (UnboundLocalError 방지)
    X = df[feature_cols]
    y = df[TARGET].astype(int).values
    groups = df[GROUP].astype(str).values

    print("\n[Missing rate top10]")
    print(X.isna().mean().sort_values(ascending=False).head(10))

    if X.shape[1] == 0:
        raise RuntimeError("학습에 사용할 피처가 0개입니다. feature_cols를 확인하세요.")

    # LightGBM params (서비스 v1 baseline)
    params = dict(
        n_estimators=4000,
        learning_rate=0.02,
        num_leaves=31,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=RANDOM_STATE,
        n_jobs=-1,
        force_row_wise=True,
        reg_lambda=0.5,
        min_child_samples=15,
        verbosity=-1,  # 경고/로그 줄이기
    )

    gkf = GroupKFold(n_splits=5)

    oof_prob = np.zeros(len(df), dtype=float)
    fold_scores = []

    for fold, (tr_idx, va_idx) in enumerate(gkf.split(X, y, groups=groups), 1):
        X_tr, X_va = X.iloc[tr_idx].copy(), X.iloc[va_idx].copy()
        y_tr, y_va = y[tr_idx], y[va_idx]

        # fold train 기준 상수 컬럼 제거
        nunique = X_tr.nunique(dropna=False)
        const_cols = nunique[nunique <= 1].index.tolist()
        if const_cols:
            X_tr = X_tr.drop(columns=const_cols)
            X_va = X_va.drop(columns=const_cols)

        clf = lgb.LGBMClassifier(**params)
        clf.fit(
            X_tr, y_tr,
            categorical_feature=[c for c in cat_cols if c in X_tr.columns],
        )

        prob = clf.predict_proba(X_va)[:, 1]
        oof_prob[va_idx] = prob

        auc = roc_auc_score(y_va, prob)
        ap  = average_precision_score(y_va, prob)
        fold_scores.append((auc, ap))
        print(f"[Fold {fold}] ROC-AUC={auc:.4f}  PR-AUC={ap:.4f}  rows={len(va_idx)}")

    print("\n[CV Mean] ROC-AUC:", round(float(np.mean([s[0] for s in fold_scores])), 4))
    print("[CV Mean] PR-AUC :", round(float(np.mean([s[1] for s in fold_scores])), 4))

    # threshold (OOF 기반)
    thr = find_threshold(y, oof_prob, objective=THRESHOLD_OBJECTIVE)
    print(f"\n[OOF] Threshold objective={THRESHOLD_OBJECTIVE}  -> threshold={thr:.4f}")

    pred = (oof_prob >= thr).astype(int)
    print("\n[OOF] Confusion Matrix")
    print(confusion_matrix(y, pred))
    print("\n[OOF] Classification Report")
    print(classification_report(y, pred, digits=4))

    # 최종 모델: 전체 데이터 학습
    final_clf = lgb.LGBMClassifier(**params)
    final_clf.fit(
        X, y,
        categorical_feature=[c for c in cat_cols if c in X.columns],
    )

    # 저장
    model_path = OUT_DIR / "lgb_service_v1.txt"
    final_clf.booster_.save_model(str(model_path))

    meta = {
        "model_name": "lgb_service_v1",
        "current_year": CURRENT_YEAR,
        "target": TARGET,
        "group_key": GROUP,
        "threshold_objective": THRESHOLD_OBJECTIVE,
        "threshold": float(thr),
        "features": feature_cols,
        "categorical_features": [c for c in cat_cols if c in feature_cols],
        "optional_user_inputs": SERVICE_OPTIONAL_INPUTS,
        "notes": [
            "Service inputs: address(required) + area_m2(optional) + floor(optional).",
            "Address text is NOT used as a raw feature. Address resolves kaptCode + complex features in DB.",
            "No deal_ym/month_sin/cos. building_age_years uses CURRENT_YEAR - build_year.",
            "Missing values are kept as NaN; 일부는 *_isna indicator로 보강.",
        ],
    }

    meta_path = OUT_DIR / "lgb_service_v1.meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # 중요도 출력
    importances = pd.Series(final_clf.feature_importances_, index=feature_cols).sort_values(ascending=False)
    print("\nTop30 Feature Importances (final service-v1 model)")
    print(importances.head(30))

    print(f"\n[SAVED] model -> {model_path}")
    print(f"[SAVED] meta  -> {meta_path}")


if __name__ == "__main__":
    main()
