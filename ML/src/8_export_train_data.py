import os
from pathlib import Path

import pandas as pd
import pymysql
from dotenv import load_dotenv

# =========================
# 환경 설정
# =========================
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "snapshot"
DATA_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DB"),
    "charset": "utf8mb4",
}

TABLE_NAME = "train_jeonse_risk_bin_tx"

PARQUET_PATH = DATA_DIR / f"{TABLE_NAME}.parquet"
CSV_PATH = DATA_DIR / f"{TABLE_NAME}.csv"

# =========================
# 메인 로직
# =========================
def main():
    print(f"📡 DB 연결 중… ({DB_CONFIG['host']})")

    conn = pymysql.connect(**DB_CONFIG)

    query = f"""
    SELECT *
    FROM {TABLE_NAME}
    """

    print(f"📥 테이블 로드 중: {TABLE_NAME}")
    df = pd.read_sql(query, conn)

    conn.close()

    print("✅ 로드 완료")
    print(f"  rows   : {len(df):,}")
    print(f"  columns: {len(df.columns)}")

    # =========================
    # Parquet 저장 (추천)
    # =========================
    df.to_parquet(PARQUET_PATH, index=False)
    print(f"💾 Parquet 저장 완료 → {PARQUET_PATH}")

    # =========================
    # CSV 저장 (보조)
    # =========================
    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
    print(f"💾 CSV 저장 완료 → {CSV_PATH}")

    # =========================
    # 라벨 분포 확인
    # =========================
    print("\n📊 risk_label 분포")
    print(df["risk_label"].value_counts().sort_index())

if __name__ == "__main__":
    main()
