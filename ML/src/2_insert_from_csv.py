# 2_insert_from_csv_apt_only.py
import os
import csv
import pymysql
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

# ✅ "정규화된 APT 전용 CSV" 경로로 바꿔줘
CSV_PATH = Path("/home/ubuntu/jeonse-main/ai_server/ML/data/processed/lease_jeonse_apt_only.csv")

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DB"),
    "charset": "utf8mb4",
    "autocommit": False,
}

INSERT_SQL = """
INSERT INTO raw_rent_contract (
  house_type, lawd_cd, deal_ym, contract_date,
  year, month, day,
  dong_name, jibun, name,
  build_year, area_m2, floor,
  deposit, monthly_rent,
  region_code, source_file
)
VALUES (
  %s, %s, %s, %s,
  %s, %s, %s,
  %s, %s, %s,
  %s, %s, %s,
  %s, %s,
  %s, %s
)
"""

BATCH_SIZE = 5000


def clean_key(k):
    return (k or "").strip().lstrip("\ufeff")


def clean_val(v):
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip()
        return v if v != "" else None
    return v


def to_int(v):
    v = clean_val(v)
    if v is None:
        return None
    s = str(v).replace(",", "")
    try:
        return int(float(s))
    except Exception:
        return None


def to_decimal_str(v):
    v = clean_val(v)
    if v is None:
        return None
    return str(v).replace(",", "")


def parse_date(v):
    v = clean_val(v)
    if v is None:
        return None
    # 네 샘플은 YYYY-MM-DD
    try:
        return datetime.strptime(v, "%Y-%m-%d").date()
    except Exception:
        return None


def main():
    assert CSV_PATH.exists(), f"CSV 파일 없음: {CSV_PATH}"

    conn = pymysql.connect(**DB_CONFIG)

    total = inserted = skipped = 0
    try:
        with conn.cursor() as cur, CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            batch = []
            for line_no, raw_row in enumerate(reader, start=2):
                total += 1

                row = {clean_key(k): clean_val(v) for k, v in raw_row.items()}

                # ✅ APT만
                if row.get("house_type") != "APT":
                    skipped += 1
                    continue

                contract_date = parse_date(row.get("contract_date"))
                if contract_date is None:
                    skipped += 1
                    continue

                values = (
                    row.get("house_type"),
                    row.get("lawd_cd"),
                    row.get("deal_ym"),
                    contract_date,

                    to_int(row.get("year")),
                    to_int(row.get("month")),
                    to_int(row.get("day")),

                    row.get("dong_name"),
                    row.get("jibun"),
                    row.get("name"),

                    to_int(row.get("build_year")),
                    to_decimal_str(row.get("area_m2")),
                    to_int(row.get("floor")),

                    to_int(row.get("deposit")),
                    to_int(row.get("monthly_rent")),

                    row.get("region_code"),
                    CSV_PATH.name,
                )

                batch.append(values)

                if len(batch) >= BATCH_SIZE:
                    cur.executemany(INSERT_SQL, batch)
                    conn.commit()
                    inserted += len(batch)
                    batch.clear()

            if batch:
                cur.executemany(INSERT_SQL, batch)
                conn.commit()
                inserted += len(batch)
                batch.clear()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print("✅ DONE (APT only)")
    print(f"  total_rows(csv)   = {total}")
    print(f"  inserted_rows(db) = {inserted}")
    print(f"  skipped_rows      = {skipped}")


if __name__ == "__main__":
    main()
