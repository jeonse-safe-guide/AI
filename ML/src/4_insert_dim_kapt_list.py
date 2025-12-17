# insert_dim_kapt_list.py
import os
import csv
import pymysql
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path("/home/ubuntu/jeonse-main/ai_server/ML")
load_dotenv(BASE_DIR / ".env")

CSV_PATH = BASE_DIR / "data/public/seoul_apt_list_v3.csv"

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
INSERT INTO dim_kapt_list (
  kaptCode, kaptName,
  bjdCode,
  sidoName, sggName, emdName, riName
)
VALUES (
  %s, %s,
  %s,
  %s, %s, %s, %s
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


def main():
    assert CSV_PATH.exists(), f"CSV 파일 없음: {CSV_PATH}"

    conn = pymysql.connect(**DB_CONFIG)

    total = inserted = 0

    try:
        with conn.cursor() as cur, CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            batch = []
            for row in reader:
                total += 1

                values = (
                    clean(row.get("kaptCode")),
                    clean(row.get("kaptName")),
                    clean(row.get("bjdCode")),
                    clean(row.get("sidoName")),
                    clean(row.get("sggName")),
                    clean(row.get("emdName")),
                    clean(row.get("riName")),
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

    print("✅ dim_kapt_list INSERT 완료")
    print(f"  total_rows(csv)   = {total}")
    print(f"  inserted_rows(db) = {inserted}")


if __name__ == "__main__":
    main()
