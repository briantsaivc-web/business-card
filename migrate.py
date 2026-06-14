"""
migrate.py  ——  SQLite → Supabase 一次性遷移

用法：
  python migrate.py                        # 預覽（不寫入）
  python migrate.py --run                  # 真正遷移
  python migrate.py --run --batch 200      # 自訂批次大小（預設 100）
  python migrate.py --run --skip-existing  # 已存在的 id 跳過（預設為更新）

遷移前請確認：
  1. .env 已設定 SUPABASE_URL 和 SUPABASE_KEY
  2. Supabase 已建表（執行過 init_supabase.sql 或 app 首次啟動完成 init_db()）
  3. data/contacts.db 存在（v2.5 的 SQLite）
"""

import argparse
import sqlite3
import time
from pathlib import Path

SQLITE_PATH = Path("data/contacts.db")

FIELDS = [
    "id", "company", "company_en", "name_zh", "name_en", "title", "department",
    "mobile", "phone", "fax", "email", "address", "website", "tags", "notes",
    "front_image_path", "back_image_path", "drive_file_id",
    "ocr_raw_text", "created_at", "updated_at",
]


def read_sqlite(path: Path) -> list[dict]:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM contacts ORDER BY created_at").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clean_row(row: dict) -> dict:
    out = {}
    for f in FIELDS:
        val = row.get(f, "")
        out[f] = "" if val is None else str(val)
    return out


def migrate(run: bool, batch_size: int, skip_existing: bool):
    if not SQLITE_PATH.exists():
        print(f"❌ 找不到 {SQLITE_PATH}")
        return

    rows = read_sqlite(SQLITE_PATH)
    total = len(rows)
    print(f"SQLite 共 {total} 筆")

    if not run:
        print("\n[預覽模式] 前 3 筆：")
        for r in rows[:3]:
            print(f"  {r.get('id','')} | {r.get('name_zh','')} | {r.get('company','')} | {r.get('email','')}")
        print(f"\n執行遷移請加 --run")
        return

    from db import get_supabase
    sb = get_supabase()

    success = skipped = failed = 0
    batches = [rows[i:i+batch_size] for i in range(0, total, batch_size)]

    print(f"\n開始遷移，共 {len(batches)} 批（每批 {batch_size} 筆）…\n")

    for b_idx, batch in enumerate(batches):
        payload = [clean_row(r) for r in batch]
        try:
            if skip_existing:
                sb.table("contacts").upsert(
                    payload, on_conflict="id", ignore_duplicates=True
                ).execute()
            else:
                sb.table("contacts").upsert(payload, on_conflict="id").execute()
            success += len(batch)
        except Exception as e:
            # 批次失敗時逐筆重試
            print(f"  批次 {b_idx+1} 失敗，逐筆重試…（{e}）")
            for row in payload:
                try:
                    sb.table("contacts").upsert(row, on_conflict="id").execute()
                    success += 1
                except Exception as e2:
                    print(f"    ❌ {row.get('id','')} {row.get('name_zh','')} — {e2}")
                    failed += 1

        print(f"  批次 {b_idx+1}/{len(batches)} 完成  已成功：{success}  失敗：{failed}")
        time.sleep(0.3)   # 避免 Supabase rate limit

    print(f"\n✅ 遷移完成：成功 {success}，跳過 {skipped}，失敗 {failed}")
    if failed:
        print("⚠️  有失敗筆數，請檢查上方錯誤訊息。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SQLite → Supabase 遷移工具")
    parser.add_argument("--run",           action="store_true", help="真正執行遷移（不加只預覽）")
    parser.add_argument("--batch",         type=int, default=100, help="批次大小（預設 100）")
    parser.add_argument("--skip-existing", action="store_true", help="跳過已存在的 id（預設更新）")
    args = parser.parse_args()

    migrate(run=args.run, batch_size=args.batch, skip_existing=args.skip_existing)
