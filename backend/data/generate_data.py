"""STEP 1 - COLLECT: create a realistic synthetic shop dataset and save it to SQLite.

Run from the backend folder:
    python -m data.generate_data

What makes the data "realistic":
- 10 categories, 50 products each (500 total), with brands, prices, tags and stock.
- Product popularity follows a long tail: a few "hit" products, many rarely seen ones.
- Some products launched recently and are trending in the last 30 days.
- Every user has 1-3 favourite categories, a price band (budget / mid / premium)
  and a favourite style (e.g. eco-friendly). Their browsing follows these preferences.
- Shopping sessions follow a funnel: view -> click -> add_to_cart -> purchase -> rating.
- Complementary items (phone + phone case, coffee maker + coffee beans) are often
  bought together in the same session.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

# Allow "python data/generate_data.py" as well as "python -m data.generate_data".
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import insert  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Event, Product, User  # noqa: E402

SEED = 42
PRODUCTS_PER_CATEGORY = 50
N_USERS = 300
N_DEMO_USERS = 8
HISTORY_DAYS = 180
AVG_SESSIONS_PER_USER = 11.5

STYLES = ["minimalist", "eco-friendly", "luxury", "budget-friendly", "trendy"]

# category -> brands, adjectives and product types: (type name, min price, max price, feature tags)
CATALOG: dict[str, dict] = {
    "Electronics": {
        "brands": ["Voltix", "Nexon", "Auralis", "PixelCore", "Zentro", "Lumio"],
        "adjectives": ["Pro", "Ultra", "Lite", "Max", "Smart", "Neo", "Air"],
        "types": [
            ("Smartphone", 199, 1199, ["5g", "camera", "android", "oled-display"]),
            ("Laptop", 399, 1899, ["portable", "ssd", "work", "display"]),
            ("Tablet", 149, 899, ["touchscreen", "portable", "streaming"]),
            ("Wireless Headphones", 29, 349, ["bluetooth", "noise-cancelling", "audio", "music"]),
            ("Bluetooth Speaker", 19, 249, ["bluetooth", "audio", "waterproof", "music"]),
            ("Smartwatch", 49, 499, ["fitness-tracking", "bluetooth", "wearable"]),
            ("Power Bank", 15, 79, ["battery", "usb-c", "portable", "charging"]),
            ("Phone Case", 9, 49, ["protective", "slim", "accessory"]),
            ("USB-C Charger", 12, 59, ["fast-charging", "usb-c", "accessory"]),
            ("Webcam", 25, 199, ["hd-video", "streaming", "work-from-home"]),
        ],
    },
    "Fashion": {
        "brands": ["Urbanthread", "Northloom", "Velora", "Kestrel & Co", "Modeva"],
        "adjectives": ["Classic", "Slim-Fit", "Vintage", "Everyday", "Relaxed", "Premium"],
        "types": [
            ("T-Shirt", 9, 45, ["cotton", "casual", "summer"]),
            ("Jeans", 25, 120, ["denim", "casual", "stretch"]),
            ("Sneakers", 39, 220, ["footwear", "casual", "comfort"]),
            ("Hoodie", 25, 95, ["cotton", "winter", "casual"]),
            ("Dress", 29, 250, ["party", "summer", "elegant"]),
            ("Leather Jacket", 79, 450, ["leather", "winter", "outerwear"]),
            ("Sunglasses", 12, 180, ["uv-protection", "summer", "accessory"]),
            ("Socks Pack", 5, 25, ["cotton", "comfort", "basics"]),
        ],
    },
    "Home & Kitchen": {
        "brands": ["Hearthly", "CasaNova", "Kitchora", "Dwellwise", "Ovenly"],
        "adjectives": ["Deluxe", "Compact", "Classic", "Modern", "Essential", "Family"],
        "types": [
            ("Coffee Maker", 29, 399, ["coffee", "appliance", "brewing"]),
            ("Blender", 25, 299, ["smoothie", "appliance", "kitchen"]),
            ("Non-Stick Pan", 15, 120, ["cookware", "kitchen", "cooking"]),
            ("Knife Set", 20, 250, ["cutlery", "kitchen", "cooking", "steel"]),
            ("Air Fryer", 49, 249, ["appliance", "healthy-cooking", "kitchen"]),
            ("Bedsheet Set", 19, 150, ["bedroom", "cotton", "comfort"]),
            ("Table Lamp", 15, 140, ["lighting", "decor", "bedroom"]),
            ("Mug Set", 9, 49, ["coffee", "ceramic", "kitchen"]),
        ],
    },
    "Books": {
        "brands": ["Bluequill Press", "Harbor House", "Inkwell Books", "Lantern Publishing"],
        "adjectives": ["Bestselling", "Illustrated", "Complete", "Pocket", "Award-Winning"],
        "types": [
            ("Mystery Novel", 7, 25, ["fiction", "thriller", "crime"]),
            ("Science Fiction Novel", 7, 25, ["fiction", "space", "future"]),
            ("Fantasy Novel", 7, 28, ["fiction", "magic", "adventure"]),
            ("Cookbook", 12, 45, ["recipes", "cooking", "food"]),
            ("Self-Help Book", 9, 30, ["productivity", "habits", "mindset"]),
            ("Biography", 10, 35, ["non-fiction", "history", "inspiring"]),
            ("Programming Guide", 25, 70, ["coding", "python", "technology"]),
            ("Children's Picture Book", 6, 22, ["kids", "illustrated", "bedtime"]),
        ],
    },
    "Sports & Outdoors": {
        "brands": ["Peakform", "Trailborn", "Stridex", "Fitnova", "Summitra"],
        "adjectives": ["Pro", "Lightweight", "All-Terrain", "Training", "Performance"],
        "types": [
            ("Yoga Mat", 15, 90, ["yoga", "fitness", "home-workout"]),
            ("Dumbbell Set", 29, 299, ["strength", "fitness", "home-workout"]),
            ("Running Shoes", 49, 220, ["running", "footwear", "cardio"]),
            ("Camping Tent", 59, 499, ["camping", "outdoor", "waterproof"]),
            ("Water Bottle", 8, 45, ["hydration", "outdoor", "steel"]),
            ("Resistance Bands", 9, 49, ["strength", "fitness", "home-workout"]),
            ("Cycling Helmet", 29, 199, ["cycling", "safety", "outdoor"]),
            ("Hiking Backpack", 39, 249, ["hiking", "outdoor", "travel"]),
        ],
    },
    "Beauty": {
        "brands": ["Glowella", "Purélis", "Bloomé", "Vanté", "Skinfolk"],
        "adjectives": ["Hydrating", "Natural", "Radiant", "Gentle", "Advanced", "Daily"],
        "types": [
            ("Face Moisturizer", 9, 89, ["skincare", "hydration", "face"]),
            ("Shampoo", 6, 39, ["haircare", "hair", "daily-use"]),
            ("Lipstick", 8, 49, ["makeup", "lips", "color"]),
            ("Perfume", 25, 220, ["fragrance", "gift", "luxury-scent"]),
            ("Sunscreen", 8, 45, ["skincare", "spf", "summer"]),
            ("Hair Dryer", 25, 299, ["haircare", "appliance", "styling"]),
            ("Face Serum", 12, 120, ["skincare", "vitamin-c", "face"]),
            ("Makeup Brush Set", 10, 79, ["makeup", "tools", "brushes"]),
        ],
    },
    "Toys & Games": {
        "brands": ["Playforge", "Tinkerly", "Joyblock", "Wonderwhirl"],
        "adjectives": ["Classic", "Deluxe", "Junior", "Family", "Creative", "Mega"],
        "types": [
            ("Building Blocks Set", 15, 149, ["construction", "kids", "creative"]),
            ("Board Game", 15, 69, ["family", "strategy", "party"]),
            ("Jigsaw Puzzle", 9, 39, ["puzzle", "family", "relaxing"]),
            ("Remote Control Car", 25, 159, ["rc", "kids", "outdoor-play"]),
            ("Plush Toy", 8, 45, ["soft-toy", "kids", "gift"]),
            ("Art & Craft Kit", 12, 59, ["creative", "kids", "drawing"]),
            ("Card Game", 6, 29, ["party", "family", "travel"]),
            ("STEM Robot Kit", 39, 199, ["stem", "coding", "educational"]),
        ],
    },
    "Grocery": {
        "brands": ["Harvest Hill", "Greenroot", "Mornbrew", "Nutriva", "Olivo"],
        "adjectives": ["Organic", "Premium", "Classic", "Family-Size", "Single-Origin"],
        "types": [
            ("Coffee Beans", 8, 35, ["coffee", "arabica", "roasted"]),
            ("Green Tea", 4, 20, ["tea", "antioxidant", "healthy"]),
            ("Protein Powder", 19, 79, ["protein", "fitness", "nutrition"]),
            ("Granola", 4, 15, ["breakfast", "healthy", "oats"]),
            ("Dark Chocolate", 3, 15, ["chocolate", "snack", "cocoa"]),
            ("Olive Oil", 7, 35, ["cooking", "olive", "healthy"]),
            ("Mixed Nuts", 6, 25, ["snack", "protein", "healthy"]),
            ("Pasta", 2, 9, ["italian", "cooking", "dinner"]),
        ],
    },
    "Office Supplies": {
        "brands": ["Deskcraft", "Notara", "Inkstone", "Worksmith", "Clarion"],
        "adjectives": ["Ergonomic", "Compact", "Professional", "Classic", "Wireless"],
        "types": [
            ("Notebook", 3, 25, ["paper", "writing", "journal"]),
            ("Gel Pen Set", 4, 22, ["writing", "pens", "color"]),
            ("Desk Organizer", 9, 59, ["storage", "desk", "tidy"]),
            ("Wireless Mouse", 9, 99, ["computer", "bluetooth", "work"]),
            ("Mechanical Keyboard", 39, 249, ["computer", "typing", "gaming"]),
            ("Office Chair", 79, 599, ["furniture", "ergonomic", "work-from-home"]),
            ("Laptop Stand", 19, 89, ["desk", "ergonomic", "work-from-home"]),
            ("Laptop Sleeve", 12, 59, ["laptop", "protective", "travel"]),
        ],
    },
    "Pet Supplies": {
        "brands": ["Pawsome", "Furlane", "Tailwise", "Whiskerly"],
        "adjectives": ["Premium", "Natural", "Durable", "Cozy", "Everyday"],
        "types": [
            ("Dog Food", 12, 79, ["dog", "nutrition", "grain-free"]),
            ("Cat Food", 9, 59, ["cat", "nutrition", "salmon"]),
            ("Cat Litter", 8, 35, ["cat", "odor-control", "hygiene"]),
            ("Pet Bed", 19, 129, ["dog", "cat", "comfort"]),
            ("Chew Toy", 4, 25, ["dog", "play", "durable-rubber"]),
            ("Dog Leash", 8, 45, ["dog", "walking", "outdoor"]),
            ("Cat Scratcher", 12, 89, ["cat", "play", "furniture"]),
            ("Pet Shampoo", 6, 25, ["grooming", "hygiene", "dog"]),
        ],
    },
}

# "If you buy X you often also buy Y" - used to create frequently-bought-together patterns.
COMPLEMENTS: dict[str, list[str]] = {
    "Smartphone": ["Phone Case", "USB-C Charger", "Power Bank", "Wireless Headphones"],
    "Laptop": ["Wireless Mouse", "Laptop Sleeve", "Laptop Stand", "Webcam"],
    "Tablet": ["USB-C Charger", "Power Bank"],
    "Coffee Maker": ["Coffee Beans", "Mug Set"],
    "Yoga Mat": ["Resistance Bands", "Water Bottle"],
    "Dumbbell Set": ["Protein Powder", "Resistance Bands"],
    "Running Shoes": ["Socks Pack", "Water Bottle", "Smartwatch"],
    "Camping Tent": ["Hiking Backpack", "Water Bottle"],
    "Shampoo": ["Hair Dryer"],
    "Face Moisturizer": ["Sunscreen", "Face Serum"],
    "Dog Food": ["Chew Toy", "Dog Leash"],
    "Cat Litter": ["Cat Scratcher", "Cat Food"],
    "Board Game": ["Card Game", "Jigsaw Puzzle"],
    "Cookbook": ["Non-Stick Pan", "Knife Set", "Olive Oil"],
    "Programming Guide": ["Mechanical Keyboard", "Notebook"],
    "Children's Picture Book": ["Plush Toy", "Art & Craft Kit"],
    "Jeans": ["T-Shirt", "Sneakers"],
    "Dress": ["Sunglasses", "Perfume"],
    "Air Fryer": ["Olive Oil"],
    "Blender": ["Protein Powder"],
    "Notebook": ["Gel Pen Set"],
    "Mechanical Keyboard": ["Wireless Mouse"],
}

FIRST_NAMES = [
    "Aarav", "Priya", "Rohan", "Ananya", "Vikram", "Sneha", "Arjun", "Kavya", "Rahul", "Isha",
    "Liam", "Emma", "Noah", "Olivia", "Mia", "Lucas", "Sofia", "Ethan", "Zara", "Omar",
    "Aisha", "Daniel", "Meera", "Kabir", "Nina", "Leo", "Riya", "Sam", "Tara", "Yusuf",
]
LAST_NAMES = [
    "Sharma", "Patel", "Iyer", "Gupta", "Singh", "Khan", "Reddy", "Mehta", "Das", "Nair",
    "Smith", "Brown", "Garcia", "Lee", "Martin", "Silva", "Kim", "Lopez", "Ali", "Rossi",
]
PRICE_BANDS = {"budget": 0.2, "mid": 0.5, "premium": 0.8}  # preferred price percentile


@dataclass
class SimUser:
    """A synthetic shopper with hidden preferences (only used to generate behaviour)."""

    id: int
    name: str
    fav_categories: list[str]
    fav_weights: np.ndarray
    price_band: str
    fav_style: str
    activity: float
    start_day: float
    viewed: list[int] = field(default_factory=list)


def make_products(rng: np.random.Generator) -> list[dict]:
    """Create the product catalogue."""
    products: list[dict] = []
    pid = 1
    for category, spec in CATALOG.items():
        used_names: set[str] = set()
        types = spec["types"]
        for i in range(PRODUCTS_PER_CATEGORY):
            type_name, lo, hi, features = types[i % len(types)]
            # Find a unique name like "Voltix Pro Smartphone"
            for _ in range(50):
                brand = str(rng.choice(spec["brands"]))
                adjective = str(rng.choice(spec["adjectives"]))
                name = f"{brand} {adjective} {type_name}"
                if name not in used_names:
                    break
            else:
                name = f"{brand} {adjective} {type_name} {i}"
            used_names.add(name)

            # Log-uniform price, ending in .99 like real shops
            price = float(np.exp(rng.uniform(np.log(lo), np.log(hi))))
            price = max(1.99, round(price) - 0.01)
            style = str(rng.choice(STYLES))
            tags = list(features[:])
            if rng.random() < 0.6:  # style is visible in the tags only 60% of the time
                tags.append(style)
            description = (
                f"The {name} is a {adjective.lower()} {type_name.lower()} by {brand}. "
                f"Features: {', '.join(features)}. "
                f"A great choice in {category.lower()} for everyday use."
            )
            stock = 0 if rng.random() < 0.05 else int(rng.integers(3, 250))
            products.append(
                {
                    "id": pid,
                    "name": name,
                    "category": category,
                    "brand": brand,
                    "price": price,
                    "description": description,
                    "tags": ",".join(dict.fromkeys(tags)),
                    "stock": stock,
                    "image_url": f"/images/{pid}.svg",
                    # hidden fields used only for simulation
                    "_type": type_name,
                    "_style": style,
                }
            )
            pid += 1
    return products


def make_users(rng: np.random.Generator, now: datetime) -> list[SimUser]:
    """Create synthetic users with favourite categories, price band and style."""
    categories = list(CATALOG.keys())
    users: list[SimUser] = []
    for uid in range(1, N_USERS + 1):
        n_fav = int(rng.choice([1, 2, 3], p=[0.3, 0.45, 0.25]))
        favs = list(rng.choice(categories, size=n_fav, replace=False))
        weights = rng.dirichlet(np.ones(n_fav) * 2)
        band = str(rng.choice(list(PRICE_BANDS), p=[0.35, 0.45, 0.2]))
        activity = float(rng.lognormal(0, 0.7))
        start_day = float(rng.uniform(0, HISTORY_DAYS * 0.7))  # day the user joined
        name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
        users.append(SimUser(uid, name, favs, weights, band, str(rng.choice(STYLES)), activity, start_day))

    # Demo users: active users with clear, different profiles (easy to show in a presentation)
    demo_profiles = [
        (["Electronics", "Office Supplies"], "premium"),
        (["Sports & Outdoors", "Grocery"], "mid"),
        (["Beauty", "Fashion"], "mid"),
        (["Books", "Toys & Games"], "budget"),
        (["Home & Kitchen", "Grocery"], "budget"),
        (["Pet Supplies"], "mid"),
        (["Fashion", "Sports & Outdoors"], "premium"),
        (["Electronics", "Books"], "budget"),
    ]
    for user, (favs, band) in zip(users[:N_DEMO_USERS], demo_profiles):
        user.fav_categories = favs
        user.fav_weights = np.array([0.65, 0.35])[: len(favs)] / np.array([0.65, 0.35])[: len(favs)].sum()
        user.price_band = band
        user.activity = 2.5
        user.start_day = 5.0
    return users


def generate_events(
    rng: np.random.Generator, products: list[dict], users: list[SimUser], now: datetime
) -> list[dict]:
    """Simulate shopping sessions and return a list of event rows."""
    start = now - timedelta(days=HISTORY_DAYS)
    categories = list(CATALOG.keys())
    n = len(products)
    cat_of = np.array([p["category"] for p in products])
    type_of = [p["_type"] for p in products]
    style_of = np.array([p["_style"] for p in products])
    prices = np.array([p["price"] for p in products])

    # Long-tail popularity: a few hits, many rarely seen products
    popularity = rng.lognormal(0, 1.0, size=n)
    order = np.argsort(-popularity)
    popularity[order[: int(n * 0.05)]] *= 4.0  # hits
    popularity[order[-int(n * 0.2) :]] *= 0.1  # rarely seen
    # Hidden product quality affects ratings
    quality = rng.normal(0, 0.6, size=n)
    # Some products launched recently -> trending
    launch_day = np.zeros(n)
    trending = rng.choice(n, size=25, replace=False)
    launch_day[trending] = rng.uniform(HISTORY_DAYS - 30, HISTORY_DAYS - 3, size=25)
    popularity[trending] *= 3.0

    # Price percentile of each product inside its own category
    price_pct = np.zeros(n)
    for c in categories:
        idx = np.where(cat_of == c)[0]
        ranks = prices[idx].argsort().argsort()
        price_pct[idx] = ranks / (len(idx) - 1)

    cat_index = {c: np.where(cat_of == c)[0] for c in categories}
    type_index: dict[str, np.ndarray] = {}
    for i, t in enumerate(type_of):
        type_index.setdefault(t, [])  # type: ignore[arg-type]
        type_index[t].append(i)  # type: ignore[union-attr]
    type_index = {t: np.array(v) for t, v in type_index.items()}

    # Category-level complements (e.g. Electronics <-> Office Supplies)
    comp_cats: dict[str, list[str]] = {c: [] for c in categories}
    cat_of_type = {t: p["category"] for p in products for t in [p["_type"]]}
    for t, comps in COMPLEMENTS.items():
        for ct in comps:
            a, b = cat_of_type[t], cat_of_type[ct]
            if a != b:
                comp_cats[a].append(b)
                comp_cats[b].append(a)

    rows: list[dict] = []

    def add(uid: int, pid_idx: int, etype: str, ts: datetime, sid: str, rating: int | None = None) -> None:
        rows.append(
            {
                "user_id": uid,
                "product_id": int(pid_idx) + 1,
                "event_type": etype,
                "rating": rating,
                "session_id": sid,
                "timestamp": min(ts, now),
            }
        )

    for user in users:
        target = PRICE_BANDS[user.price_band]
        price_fit = np.exp(-(((price_pct - target) / 0.25) ** 2))
        style_boost = np.where(style_of == user.fav_style, 2.5, 1.0)
        base_weight = popularity * (0.15 + price_fit) * style_boost

        n_sessions = max(1, int(round(rng.poisson(AVG_SESSIONS_PER_USER * user.activity / 1.28))))
        session_days = np.sort(rng.uniform(user.start_day, HISTORY_DAYS, size=n_sessions))
        for day in session_days:
            sid = f"{int(rng.integers(0, 2**63)):016x}"
            ts = start + timedelta(days=float(day), seconds=float(rng.uniform(0, 3600)))

            # Choose the category for this session
            r = rng.random()
            if r < 0.75:
                category = str(rng.choice(user.fav_categories, p=user.fav_weights))
            elif r < 0.88 and any(comp_cats[c] for c in user.fav_categories):
                options = [cc for c in user.fav_categories for cc in comp_cats[c]]
                category = str(rng.choice(options))
            else:
                category = str(rng.choice(categories))

            idx = cat_index[category]
            weights = base_weight[idx] * (launch_day[idx] <= day)  # not launched yet -> 0
            # recently launched products get an extra boost
            weights = weights * np.where(launch_day[idx] > 0, 1.0 + 2.0 * (day - launch_day[idx] < 30), 1.0)
            if weights.sum() <= 0:
                continue
            weights = weights / weights.sum()

            n_views = 1 + int(rng.poisson(1.8))
            chosen = list(rng.choice(idx, size=min(n_views, len(idx)), replace=False, p=weights))
            # Sometimes a user comes back to something they already looked at
            if user.viewed and rng.random() < 0.25:
                chosen.append(int(rng.choice(user.viewed[-10:])))

            for p in chosen:
                ts += timedelta(seconds=float(rng.uniform(20, 240)))
                add(user.id, p, "view", ts, sid)
                user.viewed.append(int(p))
                fit = price_fit[p] * (1.3 if style_of[p] == user.fav_style else 1.0)
                if rng.random() > 0.45 + 0.15 * fit:
                    continue
                ts += timedelta(seconds=float(rng.uniform(5, 60)))
                add(user.id, p, "click", ts, sid)
                if rng.random() > 0.15 + 0.3 * fit:
                    continue
                ts += timedelta(seconds=float(rng.uniform(10, 120)))
                add(user.id, p, "add_to_cart", ts, sid)
                if rng.random() > 0.55:
                    continue
                ts += timedelta(seconds=float(rng.uniform(30, 300)))
                add(user.id, p, "purchase", ts, sid)

                # Frequently bought together: add a complementary product
                comps = [c for c in COMPLEMENTS.get(type_of[p], []) if c in type_index]
                if comps and rng.random() < 0.45:
                    cidx = type_index[str(rng.choice(comps))]
                    cw = popularity[cidx] * (0.15 + price_fit[cidx])
                    q = int(rng.choice(cidx, p=cw / cw.sum()))
                    add(user.id, q, "view", ts + timedelta(seconds=30), sid)
                    add(user.id, q, "add_to_cart", ts + timedelta(seconds=60), sid)
                    if rng.random() < 0.7:
                        add(user.id, q, "purchase", ts + timedelta(seconds=90), sid)

                # Rating a few days later
                if rng.random() < 0.5:
                    score = 3.4 + quality[p] + 0.8 * fit + rng.normal(0, 0.7)
                    rating = int(np.clip(round(score), 1, 5))
                    add(user.id, p, "rating", ts + timedelta(days=float(rng.uniform(1, 7))), sid, rating)
    rows.sort(key=lambda r: r["timestamp"])
    return rows


def main() -> None:
    rng = np.random.default_rng(SEED)
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)

    print("Creating database tables ...")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    products = make_products(rng)
    users = make_users(rng, now)
    events = generate_events(rng, products, users, now)

    product_rows = [{k: v for k, v in p.items() if not k.startswith("_")} for p in products]
    user_rows = []
    for u in users:
        user_rows.append(
            {
                "id": u.id,
                "name": u.name,
                "is_demo": u.id <= N_DEMO_USERS,
                "persona": f"Likes {' & '.join(u.fav_categories)}",
                "price_band": u.price_band,
                "created_at": now - timedelta(days=HISTORY_DAYS - u.start_day),
            }
        )

    with SessionLocal() as db:
        db.execute(insert(Product), product_rows)
        db.execute(insert(User), user_rows)
        db.execute(insert(Event), events)
        db.commit()

    counts: dict[str, int] = {}
    for e in events:
        counts[e["event_type"]] = counts.get(e["event_type"], 0) + 1
    print(f"Saved {len(product_rows)} products, {len(user_rows)} users, {len(events)} events")
    print("Events by type:", counts)
    print("Out of stock products:", sum(1 for p in product_rows if p["stock"] == 0))


if __name__ == "__main__":
    main()
