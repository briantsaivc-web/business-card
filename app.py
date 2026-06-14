"""
app.py  ——  名片管理 Web MVP
流程：在 Claude chat 上傳名片照片 → 取得 JSON → 貼到這裡確認儲存
"""
import hashlib
import os
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path

import json
import pandas as pd
import streamlit as st
from PIL import Image
from dotenv import load_dotenv

from db import init_db, upsert_contact, search_contacts, find_duplicates, export_df

load_dotenv()
init_db()

PHOTO_DIR = Path(os.getenv("LOCAL_PHOTO_DIR", "data/BusinessCards"))
PHOTO_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="名片管理", page_icon="📇", layout="wide")
st.markdown("""
<style>
.stButton > button { width: 100%; }
.saved-card { opacity: 0.55; }
</style>
""", unsafe_allow_html=True)

FIELD_LABELS = {
    "company": "公司（中文）", "company_en": "公司（英文）",
    "name_zh": "中文姓名", "name_en": "英文姓名",
    "title": "職稱", "department": "部門",
    "mobile": "手機", "phone": "辦公室電話",
    "fax": "傳真", "email": "Email",
    "address": "地址", "website": "網站",
    "tags": "標籤", "notes": "備註",
}
FIELDS_L = ["company", "company_en", "name_zh", "name_en", "title", "department", "email"]
FIELDS_R = ["mobile", "phone", "fax", "address", "website", "tags", "notes"]


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def save_photo(file_bytes: bytes, name: str, digest: str, role: str = "front") -> str:
    today = datetime.now()
    folder = PHOTO_DIR / str(today.year) / f"{today.month:02d}"
    folder.mkdir(parents=True, exist_ok=True)
    ext = Path(name).suffix.lower() or ".jpg"
    short = digest[:10]
    existing = list(folder.glob(f"*_{role}_{short}{ext}"))
    if existing:
        return str(existing[0])
    fname = f"{today.strftime('%Y%m%d_%H%M%S')}_{role}_{short}{ext}"
    path = folder / fname
    path.write_bytes(file_bytes)
    return str(path)


def do_save(contact_id: str, fields: dict, front_path: str = "", ocr_raw: str = ""):
    upsert_contact({
        "id": contact_id,
        **fields,
        "front_image_path": front_path,
        "back_image_path": "",
        "ocr_raw_text": ocr_raw,
        "created_at": "",
        "updated_at": "",
    })


# ── 主介面 ────────────────────────────────────────────────────
st.title("📇 名片管理")

tab_paste, tab_single, tab_search, tab_export = st.tabs(
    ["📋 貼上辨識結果", "➕ 單張新增", "🔍 查詢", "📥 匯出"]
)

# ══════════════════════════════════════════════════════════════
# Tab 1：貼上 Claude 辨識 JSON
# ══════════════════════════════════════════════════════════════
with tab_paste:
    st.markdown("""
**使用流程：**
1. 在 Claude chat 上傳名片照片（可一次多張）
2. Claude 回傳 JSON → 全選複製
3. 貼到下方 → 解析 → 逐筆確認欄位 → 儲存
""")

    json_input = st.text_area(
        "貼上 Claude 回傳的 JSON（單筆或 array 皆可）",
        height=180,
        placeholder='[{"company": "...", "name_zh": "...", ...}, {...}]',
        key="json_paste_area",
    )

    col_parse, col_clear = st.columns([2, 1])
    with col_parse:
        parse_btn = st.button("✅ 解析並填入", type="primary", use_container_width=True)
    with col_clear:
        if st.button("🗑 清除", use_container_width=True):
            st.session_state.pop("paste_cards", None)
            st.rerun()

    if parse_btn and json_input.strip():
        try:
            clean = json_input.strip().replace("```json", "").replace("```", "").strip()
            data = json.loads(clean)
            if isinstance(data, dict):
                data = [data]
            cards = []
            for d in data:
                cards.append({
                    "parsed": {k: str(d.get(k, "") or "") for k in FIELD_LABELS},
                    "saved": False,
                })
            st.session_state["paste_cards"] = cards
            st.success(f"解析成功，共 {len(cards)} 筆，請逐一確認後儲存。")
        except json.JSONDecodeError as e:
            st.error(f"JSON 格式錯誤：{e}\n請確認從 Claude 複製完整的 JSON。")

    # 顯示解析結果
    if "paste_cards" in st.session_state:
        cards = st.session_state["paste_cards"]
        saved_n = sum(1 for c in cards if c["saved"])
        pending = [c for c in cards if not c["saved"]]

        st.divider()
        st.markdown(f"### 確認名片資料（{saved_n}/{len(cards)} 已儲存）")

        # 一鍵全部儲存
        if pending:
            if st.button(f"💾 全部儲存（{len(pending)} 筆）", type="primary"):
                for c in pending:
                    do_save(uuid.uuid4().hex[:12], c["parsed"])
                    c["saved"] = True
                st.session_state["paste_cards"] = cards
                st.success(f"✅ 已儲存 {len(pending)} 筆！")
                st.rerun()

        # 逐張展開確認
        for idx, card in enumerate(cards):
            p = card["parsed"]
            label = f"{'✅' if card['saved'] else '🔲'} [{idx+1}]  {p.get('name_zh','') or p.get('name_en','')}  ·  {p.get('company','')}"
            with st.expander(label, expanded=not card["saved"]):
                if card["saved"]:
                    st.success("已儲存")
                    for k in ["company", "name_zh", "name_en", "title", "mobile", "email"]:
                        if p.get(k):
                            st.text(f"{FIELD_LABELS[k]}：{p[k]}")
                else:
                    edited = {}
                    c1, c2 = st.columns(2)
                    with c1:
                        for fk in FIELDS_L:
                            edited[fk] = st.text_input(
                                FIELD_LABELS[fk], value=p.get(fk, ""), key=f"p_{idx}_{fk}"
                            )
                    with c2:
                        for fk in FIELDS_R:
                            edited[fk] = st.text_input(
                                FIELD_LABELS[fk], value=p.get(fk, ""), key=f"p_{idx}_{fk}"
                            )

                    # 重複偵測
                    dups = find_duplicates(
                        edited.get("email",""), edited.get("mobile",""),
                        edited.get("name_zh",""), edited.get("company",""),
                    )
                    dup_id = ""
                    if dups:
                        st.warning(f"⚠️ 找到 {len(dups)} 筆疑似重複")
                        st.dataframe(
                            pd.DataFrame(dups)[["company","name_zh","mobile","email","updated_at"]],
                            use_container_width=True,
                        )
                        action = st.radio(
                            "操作", ["新增為全新聯絡人", "更新既有聯絡人"],
                            horizontal=True, key=f"dup_action_{idx}"
                        )
                        if action == "更新既有聯絡人":
                            opts = {r["id"]: f"{r['name_zh']} / {r['company']}" for r in dups}
                            dup_id = st.selectbox(
                                "選擇要更新的聯絡人", list(opts.keys()),
                                format_func=lambda x: opts[x], key=f"dup_sel_{idx}"
                            )

                    if st.button(f"💾 儲存這筆", key=f"save_{idx}"):
                        do_save(dup_id or uuid.uuid4().hex[:12], edited)
                        cards[idx]["saved"] = True
                        cards[idx]["parsed"] = edited
                        st.session_state["paste_cards"] = cards
                        st.rerun()

# ══════════════════════════════════════════════════════════════
# Tab 2：單張新增（含照片上傳）
# ══════════════════════════════════════════════════════════════
with tab_single:
    st.write("手動填寫，或上傳照片後由 Claude 辨識（需在 Claude chat 另行上傳）。")
    st.info("快速方式：在 Claude chat 上傳照片 → 複製 JSON → 回到「貼上辨識結果」頁貼上。")

    front = st.file_uploader("上傳照片（選填，僅供本機存檔）",
                              type=["jpg","jpeg","png","webp"], key="s_front")
    front_path = ""
    if front:
        fb = front.getvalue()
        st.image(Image.open(front), width=320)
        front_path = save_photo(fb, front.name, sha256(fb), "front")

    st.subheader("填寫欄位")
    edited = {}
    c1, c2 = st.columns(2)
    with c1:
        for fk in FIELDS_L:
            edited[fk] = st.text_input(FIELD_LABELS[fk], key=f"m_{fk}")
    with c2:
        for fk in FIELDS_R:
            edited[fk] = st.text_input(FIELD_LABELS[fk], key=f"m_{fk}")

    if st.button("💾 儲存", type="primary"):
        if not edited.get("name_zh") and not edited.get("name_en") and not edited.get("company"):
            st.warning("請至少填寫姓名或公司名稱。")
        else:
            do_save(uuid.uuid4().hex[:12], edited, front_path)
            st.success("已儲存！")
            st.rerun()

# ══════════════════════════════════════════════════════════════
# Tab 3：查詢
# ══════════════════════════════════════════════════════════════
with tab_search:
    q = st.text_input("搜尋姓名、公司、電話、Email、標籤", placeholder="輸入關鍵字...")
    rows = search_contacts(q)
    st.caption(f"共 {len(rows)} 筆")

    if rows:
        df_show = pd.DataFrame(rows)[[
            "company","name_zh","name_en","title","mobile","phone","email","tags","updated_at"
        ]].rename(columns={
            "company":"公司","name_zh":"中文姓名","name_en":"英文姓名",
            "title":"職稱","mobile":"手機","phone":"電話",
            "email":"Email","tags":"標籤","updated_at":"更新時間",
        })
        st.dataframe(df_show, use_container_width=True, height=300)

        selected = st.selectbox(
            "點選查看詳細",
            [r["id"] for r in rows],
            format_func=lambda rid: next(
                (f"{r.get('name_zh') or r.get('name_en','')}  ·  {r.get('company','')}  ·  {r.get('email','')}"
                 for r in rows if r["id"]==rid), rid
            ),
        )
        rec = next((r for r in rows if r["id"]==selected), None)
        if rec:
            c1, c2 = st.columns([1, 2])
            with c1:
                if rec.get("front_image_path") and Path(rec["front_image_path"]).exists():
                    st.image(rec["front_image_path"], use_container_width=True)
            with c2:
                for label, key in [
                    ("公司","company"),("英文公司","company_en"),
                    ("姓名","name_zh"),("英文","name_en"),
                    ("職稱","title"),("部門","department"),
                    ("手機","mobile"),("電話","phone"),("傳真","fax"),
                    ("Email","email"),("地址","address"),("網站","website"),
                    ("標籤","tags"),("備註","notes"),
                ]:
                    if rec.get(key):
                        st.text(f"{label}：{rec[key]}")

# ══════════════════════════════════════════════════════════════
# Tab 4：匯出
# ══════════════════════════════════════════════════════════════
with tab_export:
    df = export_df()
    st.caption(f"共 {len(df)} 筆")
    st.dataframe(df, use_container_width=True, height=280)
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("⬇ 下載 CSV", df.to_csv(index=False).encode("utf-8-sig"),
                           "contacts.csv", "text/csv", use_container_width=True)
    with c2:
        buf = BytesIO()
        df.to_excel(buf, index=False)
        st.download_button("⬇ 下載 Excel", buf.getvalue(), "contacts.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)
