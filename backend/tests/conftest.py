"""Shared test data: a tiny hand-made shop where we know the right answers."""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

# API tests must never touch the real database: point to a temp file BEFORE app imports.
_TMP_DB = Path(tempfile.gettempdir()) / "shop_test.db"
os.environ["SHOP_DATABASE_URL"] = f"sqlite:///{_TMP_DB.as_posix()}"
# Admin endpoints need this token in the X-Admin-Token header (see test_api.py: ADMIN).
os.environ["ADMIN_TOKEN"] = "test-admin-token"

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from recommender.base import Catalog  # noqa: E402

NOW = datetime(2026, 1, 31, 12, 0, 0)


@pytest.fixture
def products() -> pd.DataFrame:
    rows = [
        # id, name, category, price, tags, stock
        (1, "Voltix Pro Smartphone", "Electronics", 799.0, "5g,camera,android", 10),
        (2, "Nexon Ultra Smartphone", "Electronics", 699.0, "5g,camera,android", 10),
        (3, "Voltix Phone Case", "Electronics", 19.0, "protective,accessory", 10),
        (4, "Auralis Wireless Headphones", "Electronics", 199.0, "bluetooth,audio,music", 10),
        (5, "Lumio Bluetooth Speaker", "Electronics", 89.0, "bluetooth,audio,music", 0),  # out of stock
        (6, "Bluequill Mystery Novel", "Books", 12.0, "fiction,thriller,crime", 10),
        (7, "Inkwell Fantasy Novel", "Books", 14.0, "fiction,magic,adventure", 10),
        (8, "Harbor House Cookbook", "Books", 25.0, "recipes,cooking,food", 10),
        (9, "Peakform Yoga Mat", "Sports & Outdoors", 30.0, "yoga,fitness", 10),
        (10, "Stridex Running Shoes", "Sports & Outdoors", 120.0, "running,footwear", 10),
        (11, "Zentro Smartwatch", "Electronics", 299.0, "fitness-tracking,bluetooth,wearable", 10),
        (12, "Nexon Tablet", "Electronics", 499.0, "touchscreen,portable,streaming", 10),
    ]
    df = pd.DataFrame(rows, columns=["id", "name", "category", "price", "tags", "stock"])
    df["brand"] = df["name"].str.split().str[0]
    df["description"] = "The " + df["name"] + " with " + df["tags"].str.replace(",", ", ")
    df["image_url"] = "/images/" + df["id"].astype(str) + ".svg"
    return df


@pytest.fixture
def catalog(products: pd.DataFrame) -> Catalog:
    return Catalog(products)


def make_events(rows: list[tuple[int, int, str, int]]) -> pd.DataFrame:
    """rows = (user_id, product_id, event_type, days_ago)"""
    return pd.DataFrame(
        [
            {
                "user_id": u,
                "product_id": p,
                "event_type": t,
                "rating": None,
                "session_id": f"s{u}-{d}",
                "timestamp": NOW - timedelta(days=d, minutes=i),
            }
            for i, (u, p, t, d) in enumerate(rows)
        ]
    )


@pytest.fixture
def events() -> pd.DataFrame:
    rows: list[tuple[int, int, str, int]] = []
    # Users 1-4: phone buyers who also buy a case and headphones (strong 1-3-4 pattern)
    for u in range(1, 5):
        rows += [(u, 1, "view", 3), (u, 1, "purchase", 3), (u, 3, "add_to_cart", 3), (u, 3, "purchase", 3),
                 (u, 4, "view", 2), (u, 4, "click", 2)]
    # Users 5-7: book readers (6 and 7 together)
    for u in range(5, 8):
        rows += [(u, 6, "view", 40), (u, 6, "purchase", 40), (u, 7, "view", 39), (u, 7, "add_to_cart", 39)]
    # Product 9 was popular a long time ago, product 10 is popular now
    for u in range(8, 12):
        rows += [(u, 9, "purchase", 120), (u, 10, "view", 1)]
    return make_events(rows)
