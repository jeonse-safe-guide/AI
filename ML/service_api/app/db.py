import os
import pymysql
from contextlib import contextmanager
from typing import List, Dict, Optional


DB_CONFIG = dict(
    host=os.getenv("MYSQL_HOST"),
    port=int(os.getenv("MYSQL_PORT", "3306")),
    user=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    db=os.getenv("MYSQL_DB"),  # jeonse_hs
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
    autocommit=True,
)


@contextmanager
def get_conn():
    conn = pymysql.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()


def db_ping() -> Dict:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok")
                return {"ok": True, "result": cur.fetchone()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def fetch_kapt_candidates(address_text: str, apart_hint: Optional[str]) -> List[Dict]:
    """
    1) apart_hint(아파트명) 있으면 kaptName LIKE로 후보 축소
    2) 없으면 emdName이 주소에 포함되는 단지들 조회
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            if apart_hint and apart_hint.strip():
                sql = """
                SELECT kaptCode, kaptName, kaptName_norm, bjdCode, sidoName, sggName, emdName, sgg_cd
                FROM dim_kapt_list
                WHERE kaptName LIKE CONCAT('%%', %s, '%%')
                LIMIT 200
                """
                cur.execute(sql, (apart_hint.strip(),))
                rows = cur.fetchall()
                if rows:
                    return rows

            # fallback: emdName이 주소에 포함되는 단지들 (너무 많으면 LIMIT)
            sql = """
            SELECT kaptCode, kaptName, kaptName_norm, bjdCode, sidoName, sggName, emdName, sgg_cd
            FROM dim_kapt_list
            WHERE %s LIKE CONCAT('%%', emdName, '%%')
            LIMIT 400
            """
            cur.execute(sql, (address_text,))
            return cur.fetchall()


def fetch_kapt_detail(kaptCode: str) -> Optional[Dict]:
    """
    단지 상세(피처) 테이블
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            sql = "SELECT * FROM dim_kapt_basic_detail WHERE kaptCode=%s"
            cur.execute(sql, (kaptCode,))
            return cur.fetchone()


def fetch_latest_official_price_avg(bjd_code: str, area_m2: float, apt_name_hint: Optional[str]) -> Optional[int]:
    """
    raw_official_price_unit에서:
    - bjd_code 일치
    - 면적 ±3㎡
    - (가능하면) apt_name LIKE 힌트 적용
    - 최신 (ref_year, ref_month) 우선

    반환: official_price 평균 (원)
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 최신 기준연월 얻기
            sql_latest = """
            SELECT ref_year, ref_month
            FROM raw_official_price_unit
            WHERE bjd_code=%s
            ORDER BY ref_year DESC, ref_month DESC
            LIMIT 1
            """
            cur.execute(sql_latest, (bjd_code,))
            ym = cur.fetchone()
            if not ym:
                return None

            ref_year = ym["ref_year"]
            ref_month = ym["ref_month"]

            # 평균 공시가격
            if apt_name_hint and apt_name_hint.strip():
                sql = """
                SELECT AVG(official_price) AS op_avg
                FROM raw_official_price_unit
                WHERE bjd_code=%s
                  AND ref_year=%s AND ref_month=%s
                  AND ABS(area_m2 - %s) <= 3
                  AND apt_name LIKE CONCAT('%%', %s, '%%')
                """
                cur.execute(sql, (bjd_code, ref_year, ref_month, area_m2, apt_name_hint.strip()))
            else:
                sql = """
                SELECT AVG(official_price) AS op_avg
                FROM raw_official_price_unit
                WHERE bjd_code=%s
                  AND ref_year=%s AND ref_month=%s
                  AND ABS(area_m2 - %s) <= 3
                """
                cur.execute(sql, (bjd_code, ref_year, ref_month, area_m2))

            row = cur.fetchone()
            if not row or row["op_avg"] is None:
                return None
            return int(row["op_avg"])
