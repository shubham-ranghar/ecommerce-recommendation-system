"""Placeholder product images, drawn as SVG on the fly (works offline, no image files needed)."""
from __future__ import annotations

from html import escape

CATEGORY_COLORS: dict[str, tuple[str, str]] = {
    "Electronics": ("#6366f1", "#a5b4fc"),
    "Fashion": ("#ec4899", "#f9a8d4"),
    "Home & Kitchen": ("#f59e0b", "#fcd34d"),
    "Books": ("#8b5cf6", "#c4b5fd"),
    "Sports & Outdoors": ("#10b981", "#6ee7b7"),
    "Beauty": ("#f43f5e", "#fda4af"),
    "Toys & Games": ("#06b6d4", "#67e8f9"),
    "Grocery": ("#84cc16", "#bef264"),
    "Office Supplies": ("#64748b", "#cbd5e1"),
    "Pet Supplies": ("#f97316", "#fdba74"),
}

TYPE_EMOJI: dict[str, str] = {
    "Smartphone": "📱", "Laptop": "💻", "Tablet": "📲", "Wireless Headphones": "🎧",
    "Bluetooth Speaker": "🔊", "Smartwatch": "⌚", "Power Bank": "🔋", "Phone Case": "📱",
    "USB-C Charger": "🔌", "Webcam": "📷",
    "T-Shirt": "👕", "Jeans": "👖", "Sneakers": "👟", "Hoodie": "🧥", "Dress": "👗",
    "Leather Jacket": "🧥", "Sunglasses": "🕶️", "Socks Pack": "🧦",
    "Coffee Maker": "☕", "Blender": "🥤", "Non-Stick Pan": "🍳", "Knife Set": "🔪", "Air Fryer": "🍟",
    "Bedsheet Set": "🛏️", "Table Lamp": "💡", "Mug Set": "☕",
    "Mystery Novel": "🕵️", "Science Fiction Novel": "🚀", "Fantasy Novel": "🐉", "Cookbook": "📖",
    "Self-Help Book": "🌱", "Biography": "📘", "Programming Guide": "💾", "Children's Picture Book": "🧸",
    "Yoga Mat": "🧘", "Dumbbell Set": "🏋️", "Running Shoes": "👟", "Camping Tent": "⛺",
    "Water Bottle": "💧", "Resistance Bands": "💪", "Cycling Helmet": "🚴", "Hiking Backpack": "🎒",
    "Face Moisturizer": "🧴", "Shampoo": "🧴", "Lipstick": "💄", "Perfume": "🌸", "Sunscreen": "☀️",
    "Hair Dryer": "💨", "Face Serum": "✨", "Makeup Brush Set": "🖌️",
    "Building Blocks Set": "🧱", "Board Game": "🎲", "Jigsaw Puzzle": "🧩", "Remote Control Car": "🏎️",
    "Plush Toy": "🧸", "Art & Craft Kit": "🎨", "Card Game": "🃏", "STEM Robot Kit": "🤖",
    "Coffee Beans": "🫘", "Green Tea": "🍵", "Protein Powder": "🥛", "Granola": "🥣",
    "Dark Chocolate": "🍫", "Olive Oil": "🫒", "Mixed Nuts": "🥜", "Pasta": "🍝",
    "Notebook": "📓", "Gel Pen Set": "🖊️", "Desk Organizer": "🗂️", "Wireless Mouse": "🖱️",
    "Mechanical Keyboard": "⌨️", "Office Chair": "🪑", "Laptop Stand": "💻", "Laptop Sleeve": "💼",
    "Dog Food": "🦴", "Cat Food": "🐟", "Cat Litter": "🐈", "Pet Bed": "🛏️", "Chew Toy": "🦴",
    "Dog Leash": "🐕", "Cat Scratcher": "🐈", "Pet Shampoo": "🛁",
}


def product_type(name: str) -> str:
    """Find the product type at the end of a name like 'Voltix Pro Smartphone'."""
    for t in sorted(TYPE_EMOJI, key=len, reverse=True):
        if name.endswith(t):
            return t
    return name.split()[-1]


def product_svg(name: str, category: str, brand: str) -> str:
    dark, light = CATEGORY_COLORS.get(category, ("#475569", "#cbd5e1"))
    ptype = product_type(name)
    emoji = TYPE_EMOJI.get(ptype, "🛍️")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" viewBox="0 0 400 300">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{light}"/><stop offset="1" stop-color="{dark}"/></linearGradient></defs>
  <rect width="400" height="300" fill="url(#g)"/>
  <circle cx="330" cy="60" r="90" fill="#ffffff" opacity="0.12"/>
  <circle cx="60" cy="260" r="70" fill="#ffffff" opacity="0.10"/>
  <text x="200" y="160" font-size="96" text-anchor="middle" font-family="Segoe UI Emoji, Apple Color Emoji, Noto Color Emoji, sans-serif">{emoji}</text>
  <text x="200" y="230" font-size="22" font-weight="700" fill="#ffffff" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif">{escape(ptype)}</text>
  <text x="200" y="258" font-size="15" fill="#ffffff" opacity="0.85" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif">{escape(brand)}</text>
</svg>"""
