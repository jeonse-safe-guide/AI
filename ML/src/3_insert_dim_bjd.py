# insert_dim_bjd.py
import os
import csv
import pymysql
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path("/home/ubuntu/jeonse-main/ai_server/ML")
load_dotenv(BASE_DIR / ".env")

CSV_PATH = BASE_DIR / "data/public/국토교통부_법정동코드_20250805.csv"

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
INSERT INTO dim_bjd (
  bjd_code, bjd_name, is_active,
  sido_name, sgg_name, emd_name, ri_name,
  sgg_cd
)
VALUES (
  %s,%s,%s,
  %s,%s,%s,%s,
  %s
)
"""

BATCH_SIZE = 5000


def parse_bjd_name(name: str):
    """
    '서울특별시 종로구 청운동' → (sido, sgg, emd, ri)
    """
    if not name:
        return None, None, None, None

    parts = name.strip().split()
    sido = parts[0] if len(parts) >= 1 else None
    sgg  = parts[1] if len(parts) >= 2 else None
    emd  = parts[2] if len(parts) >= 3 else None
    ri   = parts[3] if len(parts) >= 4 else None

    return sido, sgg, emd, ri


def main():
    assert CSV_PATH.exists(), f"CSV 파일 없음: {CSV_PATH}"

    conn = pymysql.connect(**DB_CONFIG)

    total = inserted = 0

    try:
        with conn.cursor() as cur, CSV_PATH.open("r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            batch = []
            for row in reader:
                total += 1

                bjd_code = row["법정동코드"].strip()
                bjd_name = row["법정동명"].strip()
                is_active = 1 if row["폐지여부"].strip() == "존재" else 0

                sido, sgg, emd, ri = parse_bjd_name(bjd_name)

                sgg_cd = bjd_code[:5]

                batch.append((
                    bjd_code,
                    bjd_name,
                    is_active,
                    sido,
                    sgg,
                    emd,
                    ri,
                    sgg_cd,
                ))

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

    print("✅ dim_bjd INSERT 완료")
    print(f"  total_rows(csv)   = {total}")
    print(f"  inserted_rows(db) = {inserted}")


if __name__ == "__main__":
    main()
