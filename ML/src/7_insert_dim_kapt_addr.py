import os
import csv
import re
import pymysql
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

CSV_PATH = Path("/home/ubuntu/jeonse-main/ai_server/ML/data/public/20251205_단지_기본정보.csv")

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DB"),
    "charset": "utf8mb4",
    "autocommit": False,
}

# CSV 헤더에 "단지코드", "도로명주소", "법정동주소" 등이 존재한다고 했음
# 여기서는 "단지코드" + "도로명주소"만 쓰고, bjdCode는 dim_kapt_list로 보강함.

UPSERT_SQL = """
INSERT INTO dim_kapt_addr (kaptCode, road_addr, road_addr_norm)
VALUES (%s, %s, %s)
ON DUPLICATE KEY UPDATE
  road_addr = VALUES(road_addr),
  road_addr_norm = VALUES(road_addr_norm);
"""

def norm_road_addr(s: str) -> str:
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    # 공백/탭/줄바꿈 제거
    s = re.sub(r"\s+", "", s)
    # 괄호내용 제거 (예: (주상복합) 등)
    s = re.sub(r"\(.*?\)", "", s)
    # 특수문자 제거(하이픈 등) - 도로명주소에서 의미 없는 경우가 많음
    s = re.sub(r"[-·,]", "", s)
    return s

def main():
    assert CSV_PATH.exists(), f"CSV 없음: {CSV_PATH}"

    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()

    total = 0
    upserted = 0

    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        batch = []
        for row in reader:
            total += 1

            kapt = (row.get("단지코드") or "").strip()
            road = (row.get("도로명주소") or "").strip()

            if not kapt:
                continue

            road_norm = norm_road_addr(road)

            batch.append((kapt, road if road else None, road_norm))

            if len(batch) >= 2000:
                cur.executemany(UPSERT_SQL, batch)
                conn.commit()
                upserted += len(batch)
                batch.clear()

        if batch:
            cur.executemany(UPSERT_SQL, batch)
            conn.commit()
            upserted += len(batch)

    # bjdCode 보강: dim_kapt_list에 있는 bjdCode로 채움
    cur.execute("""
        UPDATE dim_kapt_addr a
        JOIN dim_kapt_list k ON a.kaptCode = k.kaptCode
        SET a.bjdCode = k.bjdCode
        WHERE a.bjdCode IS NULL;
    """)
    conn.commit()

    cur.close()
    conn.close()

    print("✅ dim_kapt_addr UPSERT 완료")
    print(f"  total_rows(csv_read) = {total}")
    print(f"  upserted_rows(db)    = {upserted}")

if __name__ == "__main__":
    main()
