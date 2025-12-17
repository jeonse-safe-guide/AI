import os
import pymysql
from dotenv import load_dotenv

from pathlib import Path
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

conn = pymysql.connect(
    host=os.getenv("MYSQL_HOST"),
    port=int(os.getenv("MYSQL_PORT")),
    user=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    database=os.getenv("MYSQL_DB"),
    charset="utf8mb4",
)

with conn.cursor() as cur:
    cur.execute("SHOW TABLES;")
    print(cur.fetchall())

conn.close()
print("✅ DB 연결 성공")
