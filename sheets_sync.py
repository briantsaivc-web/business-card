"""
sheets_sync.py
將聯絡人資料寫入 Google Sheets。
每次儲存名片後，自動 append 一列到 Sheet1。
"""
import os
from pathlib import Path
from typing import Optional

_sheets_service = None


def _get_sheets_service():
    global _sheets_service
    if _sheets_service is not None:
        return _sheets_service
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        sa_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "config/service_account.json")
        if not Path(sa_path).exists():
            raise FileNotFoundError(f"找不到 Service Account JSON：{sa_path}")

        creds = service_account.Credentials.from_service_account_file(
            sa_path, scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        _sheets_service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        return _sheets_service
    except ImportError:
        raise ImportError("請執行：pip install google-api-python-client google-auth")


COLUMNS = [
    "id", "company", "company_en", "name_zh", "name_en", "title", "department",
    "mobile", "phone", "fax", "email", "address", "website", "tags", "notes",
    "front_image_path", "back_image_path", "drive_file_id", "created_at", "updated_at",
]


def ensure_header(sheet_id: str):
    """確保 Sheet1 第一列是欄位名稱（只在空白時寫入）。"""
    try:
        service = _get_sheets_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id, range="Sheet1!A1:T1"
        ).execute()
        if not result.get("values"):
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range="Sheet1!A1",
                valueInputOption="RAW",
                body={"values": [COLUMNS]},
            ).execute()
    except Exception as e:
        print(f"[sheets_sync] 確認標題列失敗：{e}")


def append_contact(contact: dict, sheet_id: Optional[str] = None) -> bool:
    """
    將一筆聯絡人資料 append 到 Google Sheet。
    回傳 True 代表成功；False 代表失敗（不阻斷主流程）。
    """
    sheet_id = sheet_id or os.getenv("GOOGLE_SHEET_ID", "")
    if not sheet_id:
        return False

    try:
        service = _get_sheets_service()
        ensure_header(sheet_id)
        row = [str(contact.get(c, "") or "") for c in COLUMNS]
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="Sheet1!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()
        return True
    except Exception as e:
        print(f"[sheets_sync] 寫入 Sheets 失敗（不影響本機儲存）：{e}")
        return False


def update_contact_row(contact: dict, sheet_id: Optional[str] = None) -> bool:
    """
    依 id 找到對應列並更新。找不到時改為 append。
    """
    sheet_id = sheet_id or os.getenv("GOOGLE_SHEET_ID", "")
    if not sheet_id:
        return False

    try:
        service = _get_sheets_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id, range="Sheet1!A:A"
        ).execute()
        ids = [r[0] if r else "" for r in result.get("values", [])]
        target_id = str(contact.get("id", ""))
        if target_id in ids:
            row_num = ids.index(target_id) + 1
            row = [str(contact.get(c, "") or "") for c in COLUMNS]
            range_notation = f"Sheet1!A{row_num}:T{row_num}"
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=range_notation,
                valueInputOption="RAW",
                body={"values": [row]},
            ).execute()
            return True
        else:
            return append_contact(contact, sheet_id)
    except Exception as e:
        print(f"[sheets_sync] 更新 Sheets 失敗：{e}")
        return False
