# 📇 名片通 v3

> **v2.5 升級版**：SQLite → Supabase PostgreSQL + Google Drive 照片

---

## 什麼改了（什麼沒改）

| 檔案 | 狀態 | 說明 |
|------|------|------|
| `app.py` | ✅ 不動 | 介面、OCR 流程、重複偵測完全保留 |
| `ocr_engine.py` | ✅ 不動 | Claude Vision OCR |
| `sheets_sync.py` | ✅ 不動 | Google Sheets 同步 |
| `import_old_csv.py` | ✅ 不動 | CSV 匯入工具 |
| `cleanup_duplicate_images.py` | ✅ 不動 | 重複圖片清理 |
| **`db.py`** | 🔄 **替換** | SQLite → Supabase（API 介面完全相同） |
| **`drive_sync.py`** | 🔄 **升級** | 新增 Streamlit secrets 支援 + `upload_bytes()` + 公開縮圖 URL |
| **`migrate.py`** | ✨ 新增 | 一次性 SQLite → Supabase 遷移工具 |
| **`init_supabase.sql`** | ✨ 新增 | 手動建表 SQL |
| **`requirements.txt`** | 🔄 更新 | 新增 `supabase>=2.4.0` |

---

## 快速部署

### Step 1 — Supabase 建表（一次性）

1. 前往 https://supabase.com → 建立免費專案
2. **Settings → API** 複製 `Project URL` 和 `anon public key`
3. **SQL Editor** → 貼上 `init_supabase.sql` → Run

### Step 2 — 填憑證

複製 `.env.example` → `.env`，填入：

```
ANTHROPIC_API_KEY=sk-ant-...
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=eyJ...
```

Google Drive（可選，照片用）：
```
GOOGLE_DRIVE_FOLDER_ID=1AbC...
GOOGLE_SERVICE_ACCOUNT_JSON=config/service_account.json
```

### Step 3 — 遷移現有資料（4,607 筆）

```bash
pip install -r requirements.txt

# 先預覽
python migrate.py

# 確認無誤後執行（約 1-2 分鐘）
python migrate.py --run
```

### Step 4 — 本機測試

```bash
streamlit run app.py
```

### Step 5 — 部署 Streamlit Cloud

```bash
git add . && git commit -m "v3: SQLite -> Supabase"
git push
```

Streamlit Cloud → App Settings → **Secrets** → 貼入 `.streamlit/secrets.toml.template` 內容（填真實值）

---

## Google Drive 服務帳戶設定（照片上傳）

> 若不設定，照片只存本機；搜尋、OCR、Supabase 同步完全正常。

1. [Google Cloud Console](https://console.cloud.google.com) → 建立或選擇專案
2. **APIs & Services** → 啟用 **Google Drive API**
3. **IAM → 服務帳戶** → 建立 → 下載 JSON 金鑰
4. 金鑰放到 `config/service_account.json`（加入 `.gitignore`）
5. Google Drive → 建立「**名片通**」資料夾 → 複製資料夾 ID（URL 中 `/folders/XXXX`）
6. 資料夾「共用」→ 加入服務帳戶 email（Editor 權限）
7. `.env` 填入 `GOOGLE_DRIVE_FOLDER_ID=XXXX`

---

## 架構

```
Browser（手機 / 電腦）
      │
      ▼
Streamlit Cloud（免費）
      │
      ├──► Supabase PostgreSQL  ←  所有聯絡人文字資料
      │         搜尋快、手機可查、4,607 筆完整遷入
      │
      ├──► Google Drive「名片通」資料夾
      │         名片照片，15GB 免費
      │         手機用 Drive App 直接瀏覽
      │
      └──► Anthropic Claude API  （OCR 辨識）
```

---

## migrate.py 選項

```
python migrate.py                      # 預覽，不寫入
python migrate.py --run                # 執行遷移
python migrate.py --run --batch 50     # 較慢網路用小批次
python migrate.py --run --skip-existing  # 只補新資料（已有的跳過）
```
