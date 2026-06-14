"""
drive_sync.py  ——  v3  Google Drive 照片上傳
與 v2.5 API 完全相同：upload_photo(local_path, company, name, folder_id) -> str

認證方式優先順序：
  1. config/service_account.json  （本機開發）
  2. .env  GOOGLE_SERVICE_ACCOUNT_JSON=<JSON 字串>  （環境變數）
  3. Streamlit secrets  [gdrive]  區塊  （Streamlit Cloud）

設定步驟（一次性）：
  1. Google Cloud Console → APIs → 啟用 Google Drive API
  2. IAM → 服務帳戶 → 建立 → 下載 JSON 金鑰
  3. 把金鑰放到  config/service_account.json
     或把 JSON 內容整個貼到 .env GOOGLE_SERVICE_ACCOUNT_JSON='{"type":...}'
  4. 在 Google Drive「名片通」資料夾 → 共用 → 加入服務帳戶 email（Editor）
  5. 複製資料夾 ID（URL /folders/XXXX）→ .env GOOGLE_DRIVE_FOLDER_ID=XXXX
"""

import io
import json
import mimetypes
import os
import re
from pathlib import Path
from typing import Optional

_drive_service = None   # lazy init


def _get_drive_service():
    global _drive_service
    if _drive_service is not None:
        return _drive_service

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        raise ImportError("請執行：pip install google-api-python-client google-auth")

    creds_info = None

    # ── 優先 1：config/service_account.json ──────────────────────────────────
    sa_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "config/service_account.json")
    if Path(sa_path).exists():
        creds = service_account.Credentials.from_service_account_file(
            sa_path, scopes=["https://www.googleapis.com/auth/drive"]
        )
        _drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return _drive_service

    # ── 優先 2：環境變數（JSON 字串）────────────────────────────────────────
    env_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if env_json.strip().startswith("{"):
        creds_info = json.loads(env_json)

    # ── 優先 3：Streamlit secrets [gdrive] ──────────────────────────────────
    if not creds_info:
        try:
            import streamlit as st
            gdrive_secret = st.secrets.get("gdrive", {})
            if gdrive_secret:
                creds_info = dict(gdrive_secret)
        except Exception:
            pass

    if not creds_info:
        raise FileNotFoundError(
            "找不到 Google 服務帳戶憑證。\n"
            "請參考 drive_sync.py 頂部說明完成設定，\n"
            "或略過（照片只存本機，不影響其他功能）。"
        )

    creds = service_account.Credentials.from_service_account_info(
        creds_info, scopes=["https://www.googleapis.com/auth/drive"]
    )
    _drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)
    return _drive_service


def _get_folder_id() -> str:
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
    if not folder_id:
        try:
            import streamlit as st
            folder_id = st.secrets.get("GOOGLE_DRIVE_FOLDER_ID", "")
        except Exception:
            pass
    return folder_id


def _safe_filename(company: str, name: str, ext: str = ".jpg") -> str:
    parts = [p for p in [company, name] if p]
    stem = "-".join(parts) if parts else "unnamed"
    stem = re.sub(r'[\\/:*?"<>|]', "_", stem)[:80]
    return stem + ext


def upload_photo(
    local_path: str,
    company: str = "",
    name: str = "",
    folder_id: Optional[str] = None,
) -> str:
    """
    上傳圖片到 Google Drive「名片通」資料夾。
    回傳 Drive 檔案 ID；失敗時回傳空字串（不阻斷主流程）。

    v3 新增：同時設定公開讀取權限，讓 app 可直接用
             https://drive.google.com/thumbnail?id=FILE_ID 顯示縮圖。
    """
    folder_id = folder_id or _get_folder_id()
    if not folder_id:
        return ""

    local_path = Path(local_path)
    if not local_path.exists():
        return ""

    try:
        from googleapiclient.http import MediaFileUpload

        service = _get_drive_service()
        filename = _safe_filename(company, name, local_path.suffix or ".jpg")
        mime_type = mimetypes.guess_type(str(local_path))[0] or "image/jpeg"

        file_metadata = {"name": filename, "parents": [folder_id]}
        media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=False)
        result = service.files().create(
            body=file_metadata, media_body=media, fields="id"
        ).execute()

        file_id = result.get("id", "")

        # v3 新增：設公開讀取，讓 Streamlit 可直接顯示縮圖
        if file_id:
            service.permissions().create(
                fileId=file_id,
                body={"role": "reader", "type": "anyone"},
            ).execute()

        return file_id

    except Exception as e:
        print(f"[drive_sync] 上傳失敗（不影響本機儲存）：{e}")
        return ""


def upload_bytes(
    image_bytes: bytes,
    filename: str,
    folder_id: Optional[str] = None,
) -> str:
    """
    v3 新增：直接上傳 bytes（Streamlit file_uploader 用）。
    回傳 Drive 檔案 ID。
    """
    folder_id = folder_id or _get_folder_id()
    if not folder_id:
        return ""

    try:
        from googleapiclient.http import MediaIoBaseUpload

        service = _get_drive_service()
        mime_type = (
            "image/png" if filename.lower().endswith(".png") else "image/jpeg"
        )
        file_metadata = {"name": filename, "parents": [folder_id]}
        media = MediaIoBaseUpload(
            io.BytesIO(image_bytes), mimetype=mime_type, resumable=False
        )
        result = service.files().create(
            body=file_metadata, media_body=media, fields="id"
        ).execute()
        file_id = result.get("id", "")
        if file_id:
            service.permissions().create(
                fileId=file_id,
                body={"role": "reader", "type": "anyone"},
            ).execute()
        return file_id
    except Exception as e:
        print(f"[drive_sync] bytes 上傳失敗：{e}")
        return ""


def thumbnail_url(file_id: str, size: int = 400) -> str:
    """回傳 Drive 縮圖 URL（需先呼叫 upload_photo/upload_bytes 設公開權限）。"""
    if not file_id:
        return ""
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w{size}"
