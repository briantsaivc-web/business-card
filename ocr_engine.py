"""
ocr_engine.py
使用 Claude Vision API 辨識名片。
一次 API call 同時完成 OCR + 結構化解析，取代舊版 PaddleOCR + rule-based parser。
"""
import base64
import json
import os
from pathlib import Path
from typing import Optional

import anthropic

_client: Optional[anthropic.Anthropic] = None

PROMPT = """辨識圖片中的名片內容（可能有多張），回傳 JSON。

單張名片回傳物件，多張回傳 array。每個物件包含以下欄位（找不到填空字串）：
{
  "ocr_raw": "名片上所有文字的完整抄寫，用換行分隔",
  "company": "公司中文名稱",
  "company_en": "公司英文名稱",
  "name_zh": "中文姓名（2-4個中文字）",
  "name_en": "英文姓名（First Last 格式）",
  "title": "職稱（中英文都填）",
  "department": "部門",
  "mobile": "行動電話（0912-xxx-xxx 或 +886格式）",
  "phone": "辦公室電話（含分機，如 02-xxxx-xxxx ext 231）",
  "fax": "傳真號碼",
  "email": "電子郵件",
  "address": "完整地址",
  "website": "公司網站（不含個人 email domain）",
  "tags": "",
  "notes": "名片上其他值得保留的資訊，如統一編號、口號、關係企業等"
}

規則：
- mobile 只放手機（09開頭或+886 9開頭）
- phone 放辦公室電話，fax 放傳真（名片上通常有圖示區分）
- 只回傳 JSON，不要其他文字或 markdown code block
"""


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("請在 .env 設定 ANTHROPIC_API_KEY")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _encode_image(image_path: str) -> tuple[str, str]:
    """回傳 (base64_data, mime_type)"""
    suffix = Path(image_path).suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    mime = mime_map.get(suffix, "image/jpeg")
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode(), mime


def ocr_and_parse(front_path: str, back_path: str = "") -> tuple[str, dict]:
    """
    用 Claude Vision 辨識名片。
    回傳 (ocr_raw_text, parsed_fields_dict)
    """
    client = _get_client()

    content = []

    front_b64, front_mime = _encode_image(front_path)
    content.append({"type": "image", "source": {"type": "base64", "media_type": front_mime, "data": front_b64}})

    if back_path and Path(back_path).exists():
        back_b64, back_mime = _encode_image(back_path)
        content.append({"type": "image", "source": {"type": "base64", "media_type": back_mime, "data": back_b64}})
        content.append({"type": "text", "text": "以上是同一張名片的正面與背面，" + PROMPT})
    else:
        content.append({"type": "text", "text": PROMPT})

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1200,
        messages=[{"role": "user", "content": content}],
    )

    raw_text = response.content[0].text.strip()

    try:
        clean = raw_text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean)
        if isinstance(data, list):
            data = data[0]
        ocr_raw = data.pop("ocr_raw", "")
        return ocr_raw, data
    except json.JSONDecodeError:
        return raw_text, {}
