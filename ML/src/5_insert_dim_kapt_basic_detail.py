import os
import csv
import json
import pymysql
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path("/home/ubuntu/jeonse-main/ai_server/ML")
load_dotenv(BASE_DIR / ".env")

CSV_PATH = BASE_DIR / "data/public/20251205_단지_기본정보.csv"

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DB"),
    "charset": "utf8mb4",
    "autocommit": False,
}

BATCH_SIZE = 1000  # extra_json이 커서 1000 정도가 안전

UPSERT_SQL = """
INSERT INTO dim_kapt_basic_detail (
  kaptCode, kaptName, bjdCode,
  sidoName, sggName, emdName, riName,

  basic_hoCnt,
  basic_kaptDongCnt,
  basic_kaptdaCnt,
  basic_kaptUsedate,
  basic_codeHeatNm,
  basic_codeSaleNm,
  basic_kaptTarea,
  basic_privArea,
  basic_kaptTopFloor,

  dtl_kaptMgrCnt,
  dtl_kaptdWtimebus,
  dtl_kaptdWtimesub,
  dtl_subwayLine,
  dtl_subwayStation,
  dtl_groundElChargerCnt,
  dtl_undergroundElChargerCnt,
  dtl_useYn,

  extra_json
)
VALUES (
  %s,%s,%s,
  %s,%s,%s,%s,

  %s,%s,%s,%s,%s,%s,%s,%s,%s,

  %s,%s,%s,%s,%s,%s,%s,%s,

  %s
)
ON DUPLICATE KEY UPDATE
  kaptName=VALUES(kaptName),
  bjdCode=VALUES(bjdCode),
  sidoName=VALUES(sidoName),
  sggName=VALUES(sggName),
  emdName=VALUES(emdName),
  riName=VALUES(riName),

  basic_hoCnt=VALUES(basic_hoCnt),
  basic_kaptDongCnt=VALUES(basic_kaptDongCnt),
  basic_kaptdaCnt=VALUES(basic_kaptdaCnt),
  basic_kaptUsedate=VALUES(basic_kaptUsedate),
  basic_codeHeatNm=VALUES(basic_codeHeatNm),
  basic_codeSaleNm=VALUES(basic_codeSaleNm),
  basic_kaptTarea=VALUES(basic_kaptTarea),
  basic_privArea=VALUES(basic_privArea),
  basic_kaptTopFloor=VALUES(basic_kaptTopFloor),

  dtl_kaptMgrCnt=VALUES(dtl_kaptMgrCnt),
  dtl_kaptdWtimebus=VALUES(dtl_kaptdWtimebus),
  dtl_kaptdWtimesub=VALUES(dtl_kaptdWtimesub),
  dtl_subwayLine=VALUES(dtl_subwayLine),
  dtl_subwayStation=VALUES(dtl_subwayStation),
  dtl_groundElChargerCnt=VALUES(dtl_groundElChargerCnt),
  dtl_undergroundElChargerCnt=VALUES(dtl_undergroundElChargerCnt),
  dtl_useYn=VALUES(dtl_useYn),

  extra_json=VALUES(extra_json)
"""


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


def to_decimal(v):
    # MySQL DECIMAL은 float보다 문자열/float 모두 OK. 여기선 float로 통일.
    return to_float(v)


def pick(row, key):
    return clean(row.get(key))


def extract_bjd_code(row):
    """
    CSV에 bjdCode가 직접 없을 수 있음.
    - '법정동주소'에서 10자리 코드를 뽑는 건 불가능(주소에 코드가 없음)
    => 여기선 우선 NULL로 두고, 나중에 dim_kapt_list(kaptCode->bjdCode)로 채우는 전략 추천.
    """
    return None


def main():
    assert CSV_PATH.exists(), f"CSV 파일 없음: {CSV_PATH}"

    conn = pymysql.connect(**DB_CONFIG)

    total = inserted = skipped = 0

    try:
        with conn.cursor() as cur, CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            batch = []
            for line_no, row in enumerate(reader, start=2):
                # 키 정규화
                row = { (k or "").strip().lstrip("\ufeff"): (v.strip() if isinstance(v, str) else v) for k, v in row.items() }

                kaptCode = pick(row, "단지코드")
                if not kaptCode:
                    skipped += 1
                    continue

                kaptName = pick(row, "단지명")

                # 행정구역
                sidoName = pick(row, "시도")
                sggName  = pick(row, "시군구")
                emdName  = pick(row, "동리") or pick(row, "읍면")
                riName   = pick(row, "읍면") if (pick(row, "동리") is None) else None  # 애매하면 NULL

                # bjdCode는 이 CSV만으로는 안정적으로 만들기 어려움 -> 일단 NULL
                bjdCode = extract_bjd_code(row)

                # basic 매핑(너 테이블 스키마 기준)
                # 세대수 = basic_hoCnt
                basic_hoCnt = to_int(pick(row, "세대수"))
                # 동수 = basic_kaptDongCnt
                basic_kaptDongCnt = to_int(pick(row, "동수"))
                # 분양세대수 = basic_kaptdaCnt (MVP에 의미있다고 가정)
                basic_kaptdaCnt = to_int(pick(row, "분양세대수"))
                # 사용승인일 = basic_kaptUsedate
                basic_kaptUsedate = pick(row, "사용승인일")
                # 난방방식 = basic_codeHeatNm
                basic_codeHeatNm = pick(row, "난방방식")
                # 분양형태 = basic_codeSaleNm
                basic_codeSaleNm = pick(row, "분양형태")
                # 총주차대수/면적 같은 건 CSV에 있지만 스키마에 exact match가 없으니 extra로 보관
                basic_kaptTarea = None
                basic_privArea = None
                # 최고층수 = basic_kaptTopFloor
                basic_kaptTopFloor = to_int(pick(row, "최고층수"))

                # dtl 매핑 (근처 정류장/지하철 등 CSV에는 없어서 대부분 NULL)
                # 일반관리-인원 -> dtl_kaptMgrCnt 로 매핑(관리 인력 수)
                dtl_kaptMgrCnt = to_int(pick(row, "일반관리-인원"))
                dtl_kaptdWtimebus = None
                dtl_kaptdWtimesub = None
                dtl_subwayLine = None
                dtl_subwayStation = None

                # 전기차 충전기
                dtl_groundElChargerCnt = to_int(pick(row, "전기차 충전시설 설치대수(지상)")) or to_int(pick(row, "전기차 충전시설 설치대수(지하)")) and None
                # 위 줄은 애매하니 아래처럼 정확히:
                ground_cnt = to_int(pick(row, "전기차 충전시설 설치대수(지상)"))
                under_cnt  = to_int(pick(row, "전기차 충전시설 설치대수(지하)"))
                dtl_groundElChargerCnt = ground_cnt
                dtl_undergroundElChargerCnt = under_cnt

                # 사용 여부(dt_useYn): CSV에 없으니 NULL
                dtl_useYn = None

                # extra_json: row 전체 저장 (문자열로 JSON)
                # json.dumps는 ensure_ascii=False 해야 한글 깨짐 없음
                extra_json = json.dumps(
                    {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()},
                    ensure_ascii=False
                )

                values = (
                    kaptCode, kaptName, bjdCode,
                    sidoName, sggName, emdName, riName,

                    basic_hoCnt,
                    basic_kaptDongCnt,
                    basic_kaptdaCnt,
                    basic_kaptUsedate,
                    basic_codeHeatNm,
                    basic_codeSaleNm,
                    basic_kaptTarea,
                    basic_privArea,
                    basic_kaptTopFloor,

                    dtl_kaptMgrCnt,
                    dtl_kaptdWtimebus,
                    dtl_kaptdWtimesub,
                    dtl_subwayLine,
                    dtl_subwayStation,
                    dtl_groundElChargerCnt,
                    dtl_undergroundElChargerCnt,
                    dtl_useYn,

                    extra_json
                )

                batch.append(values)
                total += 1

                if len(batch) >= BATCH_SIZE:
                    cur.executemany(UPSERT_SQL, batch)
                    conn.commit()
                    inserted += len(batch)
                    batch.clear()

            if batch:
                cur.executemany(UPSERT_SQL, batch)
                conn.commit()
                inserted += len(batch)
                batch.clear()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print("✅ dim_kapt_basic_detail UPSERT 완료")
    print(f"  total_rows(csv_read) = {total}")
    print(f"  upserted_rows(db)    = {inserted}")
    print(f"  skipped_rows         = {skipped}")


if __name__ == "__main__":
    main()
