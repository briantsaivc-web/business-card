"""
db.py  ——  v3  Supabase PostgreSQL  (drop-in 替換 SQLite 版)

API 介面與 v2.5 SQLite 版完全相同：
  init_db()  upsert_contact()  get_contact()
  search_contacts()  find_duplicates()  export_df()

新增：
  get_supabase()   — 取得 client（供 migrate.py 使用）
  SUPABASE_FIELDS  — 欄位清單（供外部參考）

設定（.env 或 Streamlit secrets）：
  SUPABASE_URL=https://xxxx.supabase.co
  SUPABASE_KEY=eyJ...   (anon public key)
"""

import os
from datetime import datetime
from functools import lru_cache
from typing import Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ── Supabase client ────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_supabase():
    """
    回傳 Supabase client。
    優先讀 .env；Streamlit Cloud 環境讀 st.secrets。
    """
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")

    # Streamlit Cloud fallback
    if not url or not key:
        try:
            import streamlit as st
            url = url or st.secrets.get("SUPABASE_URL", "")
            key = key or st.secrets.get("SUPABASE_KEY", "")
        except Exception:
            pass

    if not url or not key:
        raise RuntimeError(
            "缺少 Supabase 憑證。\n"
            "請在 .env 設定：\n"
            "  SUPABASE_URL=https://xxxx.supabase.co\n"
            "  SUPABASE_KEY=eyJ..."
        )

    from supabase import create_client
    return create_client(url, key)


# ── 欄位定義（與 v2.5 SQLite 完全一致）─────────────────────────────────────────

SUPABASE_FIELDS = [
    "id", "company", "company_en", "name_zh", "name_en", "title", "department",
    "mobile", "phone", "fax", "email", "address", "website", "tags", "notes",
    "front_image_path", "back_image_path", "drive_file_id",
    "ocr_raw_text", "created_at", "updated_at",
]

EDITABLE_FIELDS = [
    "company", "company_en", "name_zh", "name_en", "title", "department",
    "mobile", "phone", "fax", "email", "address", "website", "tags", "notes",
]

# 建表 SQL（供 init_db() 呼叫一次）
_CREATE_TABLE_SQL = """
create table if not exists contacts (
  id               text primary key,
  company          text not null default '',
  company_en       text not null default '',
  name_zh          text not null default '',
  name_en          text not null default '',
  title            text not null default '',
  department       text not null default '',
  mobile           text not null default '',
  phone            text not null default '',
  fax              text not null default '',
  email            text not null default '',
  address          text not null default '',
  website          text not null default '',
  tags             text not null default '',
  notes            text not null default '',
  front_image_path text not null default '',
  back_image_path  text not null default '',
  drive_file_id    text not null default '',
  ocr_raw_text     text not null default '',
  created_at       text not null default '',
  updated_at       text not null default ''
);

-- 全文搜尋索引（加速 search_contacts）
create index if not exists contacts_search_idx on contacts
  using gin (
    to_tsvector('simple',
      coalesce(name_zh,'') || ' ' || coalesce(name_en,'') || ' ' ||
      coalesce(company,'') || ' ' || coalesce(company_en,'') || ' ' ||
      coalesce(title,'') || ' ' || coalesce(email,'') || ' ' ||
      coalesce(mobile,'') || ' ' || coalesce(tags,'')
    )
  );
"""


# ── 公開 API ───────────────────────────────────────────────────────────────────

def init_db() -> None:
    """
    建立 contacts 資料表（若不存在）。
    Streamlit Cloud 每次重啟都會呼叫，必須冪等。
    """
    try:
        sb = get_supabase()
        # 用 rpc 執行 DDL；Supabase 免費版有 exec_sql RPC
        sb.rpc("exec_sql", {"sql": _CREATE_TABLE_SQL}).execute()
    except Exception as e:
        err = str(e)
        # 若 RPC 不存在，改用 REST 建表（Supabase 新專案預設有 Table Editor，可手動建）
        if "exec_sql" in err or "404" in err:
            _warn_manual_init()
        # 若資料表已存在，忽略
        elif "already exists" in err:
            pass
        else:
            raise


def _warn_manual_init():
    """提示使用者到 Supabase SQL Editor 手動建表。"""
    msg = (
        "\n⚠️  Supabase 自動建表失敗（exec_sql RPC 不存在）。\n"
        "請到 Supabase → SQL Editor，執行 init_supabase.sql 後重新啟動。\n"
    )
    print(msg)
    try:
        import streamlit as st
        st.error(msg)
        st.code(_CREATE_TABLE_SQL, language="sql")
        st.stop()
    except Exception:
        pass


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _clean(contact: dict) -> dict:
    """確保所有欄位都是字串，補齊缺漏欄位。"""
    out = {}
    for f in SUPABASE_FIELDS:
        val = contact.get(f, "")
        out[f] = "" if (val is None or (isinstance(val, float) and str(val) == "nan")) else str(val)
    if not out["created_at"]:
        out["created_at"] = _now()
    out["updated_at"] = _now()
    return out


def upsert_contact(contact: Dict[str, str]) -> None:
    """新增或更新一筆聯絡人（以 id 為主鍵）。"""
    sb = get_supabase()
    payload = _clean(contact)
    sb.table("contacts").upsert(payload, on_conflict="id").execute()


def get_contact(contact_id: str) -> Optional[Dict[str, str]]:
    sb = get_supabase()
    res = sb.table("contacts").select("*").eq("id", contact_id).maybe_single().execute()
    return res.data


def search_contacts(q: str = "", limit: int = 200) -> List[Dict[str, str]]:
    sb = get_supabase()
    q = (q or "").strip()
    if not q:
        res = (
            sb.table("contacts")
            .select("*")
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []

    # ilike 跨欄位搜尋（Supabase 支援 or_ 鏈式）
    like = f"%{q}%"
    res = (
        sb.table("contacts")
        .select("*")
        .or_(
            f"company.ilike.{like},"
            f"company_en.ilike.{like},"
            f"name_zh.ilike.{like},"
            f"name_en.ilike.{like},"
            f"title.ilike.{like},"
            f"department.ilike.{like},"
            f"mobile.ilike.{like},"
            f"phone.ilike.{like},"
            f"email.ilike.{like},"
            f"address.ilike.{like},"
            f"tags.ilike.{like},"
            f"notes.ilike.{like}"
        )
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def find_duplicates(
    email: str = "", mobile: str = "", name_zh: str = "", company: str = ""
) -> List[Dict[str, str]]:
    """
    重複偵測：email / mobile 完全匹配，或姓名+公司同時匹配。
    與 v2.5 邏輯完全相同。
    """
    sb = get_supabase()
    clauses = []

    if email and "@" in email:
        clauses.append(f"email.eq.{email}")
    if mobile and len(mobile) >= 8:
        clauses.append(f"mobile.eq.{mobile}")
    if not clauses and not (name_zh and company):
        return []

    results = []

    # email / mobile 完全匹配
    if clauses:
        res = (
            sb.table("contacts")
            .select("*")
            .or_(",".join(clauses))
            .limit(10)
            .execute()
        )
        results.extend(res.data or [])

    # 姓名 + 公司同時匹配
    if name_zh and company:
        res = (
            sb.table("contacts")
            .select("*")
            .eq("name_zh", name_zh)
            .eq("company", company)
            .limit(10)
            .execute()
        )
        for r in (res.data or []):
            if not any(x["id"] == r["id"] for x in results):
                results.append(r)

    return results[:10]


def export_df() -> pd.DataFrame:
    sb = get_supabase()
    res = sb.table("contacts").select("*").order("updated_at", desc=True).execute()
    rows = res.data or []
    if not rows:
        return pd.DataFrame(columns=SUPABASE_FIELDS)
    return pd.DataFrame(rows)[SUPABASE_FIELDS]

def delete_contact(contact_id: str):
    conn = get_conn()
    conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    conn.commit()
