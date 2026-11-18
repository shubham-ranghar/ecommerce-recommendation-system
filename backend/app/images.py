"""Product images: real photos from DummyJSON test data, with line-icon tiles as fallback.

Photos are downloaded once by `python -m data.fetch_images` into data/images/ and served
from disk, so the app works offline. Each product gets the photo whose DummyJSON title
matches its product type (a mouse never shows a phone). When several photos match, the
product id picks one, so the choice is the same on every run. Product types without a
good photo, and every product when the photos are missing, get a clean line-icon tile.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from html import escape
from pathlib import Path

IMAGES_DIR = Path(__file__).resolve().parent.parent / "data" / "images"
MANIFEST_PATH = IMAGES_DIR / "manifest.json"

TILE_BG = "#EFEFEF"
ICON_INK = "#191919"

# ShopSmart category -> closest DummyJSON categories (empty: no good photos -> icon tiles).
CATEGORY_SOURCES: dict[str, tuple[str, ...]] = {
    "Electronics": ("smartphones", "laptops", "tablets", "mobile-accessories"),
    "Fashion": ("mens-shirts", "mens-shoes", "tops", "womens-dresses", "sunglasses"),
    "Home & Kitchen": ("kitchen-accessories", "home-decoration"),
    "Books": (),
    "Sports & Outdoors": ("mens-shoes", "groceries"),
    "Beauty": ("beauty", "fragrances", "skin-care"),
    "Toys & Games": (),
    "Grocery": ("groceries",),
    "Office Supplies": ("furniture",),
    "Pet Supplies": ("groceries",),
}

# Product type -> (DummyJSON category, title pattern) pairs that really show that type.
# A pattern of None means "every photo in that DummyJSON category". No entry -> icon tile.
TYPE_PHOTOS: dict[str, list[tuple[str, str | None]]] = {
    # Electronics
    "Smartphone": [("smartphones", None)],
    "Laptop": [("laptops", None)],
    "Tablet": [("tablets", None)],
    "Wireless Headphones": [("mobile-accessories", r"airpods|earphones")],
    "Bluetooth Speaker": [("mobile-accessories", r"echo|homepod")],
    "Smartwatch": [("mobile-accessories", r"apple watch")],
    "Power Bank": [("mobile-accessories", r"battery pack")],
    "Phone Case": [("mobile-accessories", r"\bcase\b")],
    "USB-C Charger": [("mobile-accessories", r"charger")],
    # Fashion
    "T-Shirt": [("mens-shirts", r"tshirt|short sleeve")],
    "Sneakers": [("mens-shoes", r"sneakers|trainers|jordan")],
    "Dress": [("tops", r"dress|frock"), ("womens-dresses", r"dress|gown")],
    "Sunglasses": [("sunglasses", r"sun ?glasses")],
    # Home & Kitchen
    "Blender": [("kitchen-accessories", r"blender")],
    "Non-Stick Pan": [("kitchen-accessories", r"^pan$|\bwok\b")],
    "Knife Set": [("kitchen-accessories", r"^knife$")],
    "Table Lamp": [("home-decoration", r"table lamp")],
    "Mug Set": [("kitchen-accessories", r"\bcup\b")],
    # Sports & Outdoors
    "Running Shoes": [("mens-shoes", r"trainers|sports sneakers")],
    "Water Bottle": [("groceries", r"^water$")],
    # Beauty
    "Face Moisturizer": [("skin-care", r"lotion")],
    "Lipstick": [("beauty", r"lipstick")],
    "Perfume": [("fragrances", None)],
    # Grocery
    "Coffee Beans": [("groceries", r"coffee")],
    "Protein Powder": [("groceries", r"protein powder")],
    "Olive Oil": [("groceries", r"cooking oil")],
    # Office Supplies
    "Office Chair": [("furniture", r"chair")],
    # Pet Supplies
    "Dog Food": [("groceries", r"dog food")],
    "Cat Food": [("groceries", r"cat food")],
}

# Every product type in the shop (used to read the type from the end of a product name).
PRODUCT_TYPES: tuple[str, ...] = (
    "Smartphone", "Laptop", "Tablet", "Wireless Headphones", "Bluetooth Speaker", "Smartwatch", "Power Bank",
    "Phone Case", "USB-C Charger", "Webcam",
    "T-Shirt", "Jeans", "Sneakers", "Hoodie", "Dress", "Leather Jacket", "Sunglasses", "Socks Pack",
    "Coffee Maker", "Blender", "Non-Stick Pan", "Knife Set", "Air Fryer", "Bedsheet Set", "Table Lamp", "Mug Set",
    "Mystery Novel", "Science Fiction Novel", "Fantasy Novel", "Cookbook", "Self-Help Book", "Biography",
    "Programming Guide", "Children's Picture Book",
    "Yoga Mat", "Dumbbell Set", "Running Shoes", "Camping Tent", "Water Bottle", "Resistance Bands",
    "Cycling Helmet", "Hiking Backpack",
    "Face Moisturizer", "Shampoo", "Lipstick", "Perfume", "Sunscreen", "Hair Dryer", "Face Serum", "Makeup Brush Set",
    "Building Blocks Set", "Board Game", "Jigsaw Puzzle", "Remote Control Car", "Plush Toy", "Art & Craft Kit",
    "Card Game", "STEM Robot Kit",
    "Coffee Beans", "Green Tea", "Protein Powder", "Granola", "Dark Chocolate", "Olive Oil", "Mixed Nuts", "Pasta",
    "Notebook", "Gel Pen Set", "Desk Organizer", "Wireless Mouse", "Mechanical Keyboard", "Office Chair",
    "Laptop Stand", "Laptop Sleeve",
    "Dog Food", "Cat Food", "Cat Litter", "Pet Bed", "Chew Toy", "Dog Leash", "Cat Scratcher", "Pet Shampoo",
)

# One line icon per category (24x24 grid, stroked, no fill), drawn in ICON_INK.
CATEGORY_ICONS: dict[str, str] = {
    "Electronics": '<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M11 18h2"/>',
    "Fashion": '<path d="M20.4 3.5 16 2a4 4 0 0 1-8 0L3.6 3.5a2 2 0 0 0-1.3 2.2l.6 3.5a1 1 0 0 0 1 .8H6v10a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V10h2.1a1 1 0 0 0 1-.8l.6-3.5a2 2 0 0 0-1.3-2.2z"/>',
    "Home & Kitchen": '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/><path d="M9.5 21v-6.5h5V21"/>',
    "Books": '<path d="M2 4h6a4 4 0 0 1 4 4v13a3 3 0 0 0-3-3H2z"/><path d="M22 4h-6a4 4 0 0 0-4 4v13a3 3 0 0 1 3-3h7z"/>',
    "Sports & Outdoors": '<path d="M6.5 6.5v11M17.5 6.5v11M3 9.5v5M21 9.5v5M6.5 12h11M3 12h3.5M17.5 12H21"/>',
    "Beauty": '<path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5S12.5 5.5 12 3c-.5 2.5-2 4.9-4 6.5S5 13 5 15a7 7 0 0 0 7 7z"/>',
    "Toys & Games": '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M8.5 8.5h.01M15.5 8.5h.01M12 12h.01M8.5 15.5h.01M15.5 15.5h.01" stroke-width="2.6"/>',
    "Grocery": '<path d="M2 11h20M3.5 11l1.6 7.4a2 2 0 0 0 2 1.6h9.8a2 2 0 0 0 2-1.6l1.6-7.4M5 11l4-7M19 11l-4-7M9 11l1 9M15 11l-1 9"/>',
    "Office Supplies": '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    "Pet Supplies": '<circle cx="11" cy="4" r="2"/><circle cx="18" cy="8" r="2"/><circle cx="20" cy="16" r="2"/><circle cx="4" cy="8" r="2"/><path d="M9 10a5 5 0 0 1 5 5v3.5a3.5 3.5 0 0 1-6.8 1.1c-.6-1.8-1.6-2.7-3.5-3.3A3.5 3.5 0 0 1 5.5 10z"/>',
}
DEFAULT_ICON = '<path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4zM3 6h18M16 10a4 4 0 0 1-8 0"/>'


def product_type(name: str) -> str:
    """Find the product type at the end of a name like 'Voltix Pro Smartphone'."""
    for t in sorted(PRODUCT_TYPES, key=len, reverse=True):
        if name.endswith(t):
            return t
    return name.split()[-1]


@lru_cache(maxsize=1)
def _manifest() -> tuple[dict, ...]:
    """Downloaded photos (empty when data.fetch_images has not been run)."""
    try:
        entries = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    return tuple(sorted((e for e in entries if (IMAGES_DIR / e["file"]).exists()), key=lambda e: e["id"]))


def photo_candidates(name: str, category: str) -> list[dict]:
    """All local photos that show this product's type, in a stable order."""
    allowed = set(CATEGORY_SOURCES.get(category, ()))
    rules = [(c, re.compile(p, re.IGNORECASE) if p else None)
             for c, p in TYPE_PHOTOS.get(product_type(name), []) if c in allowed]
    return [e for e in _manifest()
            if any(e["category"] == c and (rx is None or rx.search(e["title"])) for c, rx in rules)]


def product_photo(product_id: int, name: str, category: str) -> Path | None:
    """The photo for one product, or None when the type has no good match."""
    candidates = photo_candidates(name, category)
    if not candidates:
        return None
    return IMAGES_DIR / candidates[product_id % len(candidates)]["file"]


def product_svg(name: str, category: str, brand: str) -> str:
    """Line-icon tile: category icon and product type on a light grey square."""
    icon = CATEGORY_ICONS.get(category, DEFAULT_ICON)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400">
  <rect width="400" height="400" fill="{TILE_BG}"/>
  <g transform="translate(152 120) scale(4)" fill="none" stroke="{ICON_INK}" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round">{icon}</g>
  <text x="200" y="272" font-size="20" fill="{ICON_INK}" text-anchor="middle" font-family="Segoe UI, Helvetica, Arial, sans-serif">{escape(product_type(name))}</text>
  <text x="200" y="300" font-size="15" fill="{ICON_INK}" opacity="0.6" text-anchor="middle" font-family="Segoe UI, Helvetica, Arial, sans-serif">{escape(brand)}</text>
</svg>"""
