import os
import csv
import pymysql
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path("/home/ubuntu/jeonse-main/ai_server/ML")
load_dotenv(BASE_DIR / ".env")

CSV_PATH = BASE_DIR / "data/public/국토교통부_주택 공시가격 정보(2025).csv"

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
INSERT INTO raw_official_price_unit (
  ref_year, ref_month,
  bjd_code, road_addr,
  main_no, sub_no,
  apt_name, dong_name, ho_name, area_m2,
  official_price,
  complex_code, dong_code, ho_code,
  bldg_pk
)
VALUES (
  %s,%s,
  %s,%s,
  %s,%s,
  %s,%s,%s,%s,
  %s,
  %s,%s,%s,
  %s
)
"""

BATCH_SIZE = 5000


def clean(v):
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip()
        return v if v != "" else None
    return v


def to_int(v):
    v = clean(v)
    if v is None:
        return None
    s = str(v).replace(",", "")
    try:
        return int(float(s))
    except Exception:
        return None


def to_float(v):
    v = clean(v)
    if v is None:
        return None
    s = str(v).replace(",", "")
    try:
        return float(s)
    except Exception:
        return None


def trunc255(s):
    s = clean(s)
    if s is None:
        return None
    return s[:255]


def main():
    assert CSV_PATH.exists(), f"CSV 파일 없음: {CSV_PATH}"

    conn = pymysql.connect(**DB_CONFIG)

    total = inserted = skipped = 0
    try:
        with conn.cursor() as cur, CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            batch = []
            for line_no, row in enumerate(reader, start=2):
                # key 정규화 (BOM/공백)
                row = {(k or "").strip().lstrip("\ufeff"): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}

                ref_year = to_int(row.get("기준연도"))
                ref_month = to_int(row.get("기준월"))
                bjd_code = clean(row.get("법정동코드"))

                if ref_year is None or ref_month is None or not bjd_code:
                    skipped += 1
                    continue

                values = (
                    ref_year,
                    ref_month,

                    bjd_code,
                    trunc255(row.get("도로명주소")),

                    to_int(row.get("본번")),
                    to_int(row.get("부번")),

                    clean(row.get("단지명")),
                    clean(row.get("동명")),
                    clean(row.get("호명")),
                    to_float(row.get("전용면적")),

                    to_int(row.get("공시가격")),

                    clean(row.get("단지코드")),
                    clean(row.get("동코드")),
                    clean(row.get("호코드")),

                    clean(row.get("건축물대장PK")),
                )

                batch.append(values)
                total += 1

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

    print("✅ raw_official_price_unit INSERT 완료")
    print(f"  total_rows(read)   = {total}")
    print(f"  inserted_rows(db)  = {inserted}")
    print(f"  skipped_rows       = {skipped}")


if __name__ == "__main__":
    main()
