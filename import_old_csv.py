"""把舊資料 CSV 匯入 SQLite。
用法：py import_old_csv.py old_contacts.csv
CSV 欄位可用舊格式：id, company, nameZh, nameEn, title, mobile, phone, email, address, tags, notes, createdAt
"""
import sys
import pandas as pd
from db import upsert_contact, init_db

MAP = {
    "nameZh": "name_zh",
    "nameEn": "name_en",
    "createdAt": "created_at",
}


def main(path):
    init_db()
    df = pd.read_csv(path)
    count = 0
    for _, row in df.iterrows():
        rec = {}
        for k, v in row.items():
            key = MAP.get(k, k)
            rec[key] = "" if pd.isna(v) else str(v)
        upsert_contact(rec)
        count += 1
    print(f"Imported {count} contacts")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py import_old_csv.py old_contacts.csv")
        raise SystemExit(1)
    main(sys.argv[1])
