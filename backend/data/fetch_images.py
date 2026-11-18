"""One-time download of product photos from DummyJSON (free test data, no API key).

Run from the backend folder:
    python -m data.fetch_images

Saves every DummyJSON product thumbnail to data/images/<dummyjson id>.webp and writes
data/images/manifest.json with each image's DummyJSON id, title and category.
After this the app runs fully offline: app/images.py only reads these local files.
Already downloaded images are skipped, so the script can be re-run safely.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

SOURCE_URL = "https://dummyjson.com/products?limit=0&select=title,category,thumbnail"
IMAGES_DIR = Path(__file__).resolve().parent / "images"
MANIFEST_PATH = IMAGES_DIR / "manifest.json"
HEADERS = {"User-Agent": "ShopSmart-demo/1.0"}


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as response:
        return response.read()


def main() -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    products = json.loads(fetch(SOURCE_URL))["products"]
    manifest, failed = [], []
    for n, p in enumerate(products, 1):
        file_name = f"{p['id']}.webp"
        target = IMAGES_DIR / file_name
        if not target.exists():
            try:
                target.write_bytes(fetch(p["thumbnail"]))
            except OSError as error:
                failed.append((p["id"], str(error)))
                continue
        manifest.append({"id": p["id"], "file": file_name, "title": p["title"], "category": p["category"]})
        print(f"\r{n}/{len(products)} images", end="", flush=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {len(manifest)} images and {MANIFEST_PATH.name} to {IMAGES_DIR}")
    if failed:
        print(f"{len(failed)} downloads failed (re-run to retry): {failed[:5]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
