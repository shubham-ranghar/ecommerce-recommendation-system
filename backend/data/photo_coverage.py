"""Photo coverage report: which product types have a real photo.

Run from the backend folder:
    python -m data.photo_coverage

Prints category, type, product count and photo source for every product type in the
database, and rewrites data/images/manual/missing_types.txt with the types that still
show an icon tile and the exact file name to drop into that folder for each.
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path

from app.images import IMAGES_DIR, MANUAL_DIR, manual_photo, product_photo, product_type, type_slug

DB_PATH = Path(__file__).resolve().parent / "shop.db"
MISSING_PATH = MANUAL_DIR / "missing_types.txt"


def main() -> None:
    rows = sqlite3.connect(DB_PATH).execute("SELECT name, category FROM products").fetchall()
    groups: dict[tuple[str, str], int] = defaultdict(int)
    for name, category in rows:
        groups[(category, product_type(name))] += 1

    table, missing, covered = [], [], 0
    for (category, ptype), count in sorted(groups.items()):
        photo = product_photo(f"x {ptype}", category)
        if photo is None:
            source = "no (icon tile)"
            missing.append((category, ptype, count))
        else:
            source = f"yes (manual {photo.name})" if manual_photo(ptype) else f"yes ({photo.relative_to(IMAGES_DIR)})"
            covered += count
        table.append((category, ptype, str(count), source))

    widths = [max(len(r[i]) for r in table + [("Category", "Type", "Products", "Photo")]) for i in range(4)]
    for r in [("Category", "Type", "Products", "Photo")] + table:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)))
    print(f"\n{len(groups)} types, {len(rows)} products; {len(groups) - len(missing)} types / {covered} products "
          f"have a real photo; {len(missing)} types / {len(rows) - covered} products use the icon tile.")

    MANUAL_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "Product types with no real photo (they show an icon tile).",
        "Drop a photo into this folder with the file name below and it is used for every product",
        "of that type on the next page load. .jpg, .jpeg, .png and .webp all work (same name stem).",
        "A photo here also replaces the downloaded photo for types that already have one.",
        "Regenerate this list: python -m data.photo_coverage",
        "",
    ]
    lines += [f"{type_slug(t) + '.jpg':<30} {t} ({c}, {n} products)" for c, t, n in missing]
    MISSING_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(missing)} missing types to {MISSING_PATH}")


if __name__ == "__main__":
    main()
