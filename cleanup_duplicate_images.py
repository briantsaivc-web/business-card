"""
清理 BusinessCards 資料夾內「內容完全相同」的重複圖片。
預設只列出，不刪除；確認後加 --delete 才會刪。
"""
import argparse
import hashlib
import os
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DEFAULT_DIR = Path("data/BusinessCards")
DRIVE_DIR = Path(os.getenv("GOOGLE_DRIVE_DIR") or DEFAULT_DIR)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delete", action="store_true", help="真的刪除重複檔；不加時只預覽")
    args = parser.parse_args()

    files = []
    for ext in ["*.jpg", "*.jpeg", "*.png", "*.webp"]:
        files.extend(DRIVE_DIR.rglob(ext))

    groups = defaultdict(list)
    for p in files:
        groups[sha256_file(p)].append(p)

    duplicate_count = 0
    for digest, paths in groups.items():
        if len(paths) <= 1:
            continue
        paths = sorted(paths, key=lambda p: p.stat().st_mtime)
        keep = paths[0]
        remove = paths[1:]
        duplicate_count += len(remove)
        print(f"\n保留：{keep}")
        for p in remove:
            print(f"  重複：{p}")
            if args.delete:
                p.unlink()

    if duplicate_count == 0:
        print("沒有找到內容完全相同的重複圖片。")
    elif args.delete:
        print(f"已刪除 {duplicate_count} 個重複圖片。")
    else:
        print(f"找到 {duplicate_count} 個重複圖片。確認無誤後執行：py cleanup_duplicate_images.py --delete")


if __name__ == "__main__":
    main()
