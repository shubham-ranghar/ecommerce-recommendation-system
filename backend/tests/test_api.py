"""End-to-end API tests on a temporary database (see conftest.py)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

ADMIN = {"X-Admin-Token": "test-admin-token"}  # matches ADMIN_TOKEN set in conftest.py


@pytest.fixture(scope="module")
def client() -> TestClient:
    from app.database import Base, engine
    from app.main import app, recommender

    Base.metadata.drop_all(engine)  # start from an empty temp DB -> startup generates data
    recommender.refit_seconds = 0.0  # retrain immediately after new events
    with TestClient(app) as c:
        yield c


def test_products_and_users(client: TestClient) -> None:
    page = client.get("/products", params={"limit": 5}).json()
    assert page["total"] == 500 and len(page["items"]) == 5
    assert client.get("/products/1").json()["id"] == 1
    assert client.get("/products/99999").status_code == 404
    assert len(client.get("/users").json()) == 8


def test_cold_start_becomes_personalised(client: TestClient) -> None:
    user = client.post("/users").json()
    home = client.get("/recommend/home", params={"user_id": user["id"]}).json()
    assert home["user_type"] == "new"
    assert home["sections"][0]["title"] == "Trending now"

    for event_type in ["view", "click", "add_to_cart"]:
        r = client.post("/events", json={"user_id": user["id"], "product_id": 1, "event_type": event_type})
        assert r.status_code == 201

    home = client.get("/recommend/home", params={"user_id": user["id"]}).json()
    assert home["user_type"] == "returning"
    assert home["sections"][0]["title"] == "Recommended for you"
    assert all(item["reason"] for item in home["sections"][0]["items"])


def test_product_page_and_cart_lists(client: TestClient) -> None:
    similar = client.get("/recommend/similar/1").json()
    also = client.get("/recommend/also-liked/1").json()
    cart = client.get("/recommend/cart", params={"product_ids": "1"}).json()
    for recs in (similar, also, cart):
        assert recs and all(r["reason"] for r in recs)
        assert 1 not in [r["product"]["id"] for r in recs]


def test_invalid_event_is_rejected(client: TestClient) -> None:
    r = client.post("/events", json={"user_id": 1, "product_id": 1, "event_type": "rating"})
    assert r.status_code == 422


def test_recently_viewed_and_purchase_rows(client: TestClient) -> None:
    user = client.post("/users").json()
    log = lambda pid, t: client.post("/events", json={"user_id": user["id"], "product_id": pid, "event_type": t})
    log(2, "view")
    home = client.get("/recommend/home", params={"user_id": user["id"]}).json()
    recent = next(s for s in home["sections"] if s["key"] == "recent")  # new visitors see it too
    assert [i["product"]["id"] for i in recent["items"]] == [2]

    for t in ["view", "add_to_cart", "purchase"]:
        assert log(1, t).status_code == 201
    home = client.get("/recommend/home", params={"user_id": user["id"]}).json()
    sections = {s["key"]: s for s in home["sections"]}
    assert home["user_type"] == "returning"
    # Recently viewed: newest first, never something already bought
    assert [i["product"]["id"] for i in sections["recent"]["items"]] == [2]
    assert sections["recent"]["items"][0]["reason"] == "You viewed this"
    # Based on your purchases: no bought items, no repeats from "Recommended for you"
    based = [i["product"]["id"] for i in sections["purchases"]["items"]]
    for_you = {i["product"]["id"] for i in sections["for_you"]["items"]}
    assert based and 1 not in based and not set(based) & for_you
    assert 2 not in for_you | set(based)  # recently viewed items are not repeated


def test_bought_together_on_product_page(client: TestClient) -> None:
    # Find a product that really has basket partners in the generated data
    for pid in range(1, 60):
        recs = client.get(f"/recommend/bought-together/{pid}").json()
        if recs:
            break
    assert recs, "expected basket co-occurrence data"
    assert pid not in [r["product"]["id"] for r in recs]
    assert all(r["reason"].startswith("Bought together with") for r in recs)
    assert client.get("/recommend/bought-together/99999").status_code == 404


def test_admin_settings_change_recommendations(client: TestClient) -> None:
    data = client.get("/admin/settings", headers=ADMIN).json()
    assert data["current"] == data["defaults"]
    try:
        new = {**data["defaults"], "max_per_category": 1, "show_recently_viewed": False}
        assert client.put("/admin/settings", json=new, headers=ADMIN).json()["current"]["max_per_category"] == 1
        home = client.get("/recommend/home", params={"user_id": 1}).json()
        sections = {s["key"]: s for s in home["sections"]}
        cats = [i["product"]["category"] for i in sections["for_you"]["items"]]
        assert len(cats) == len(set(cats))  # max 1 per category
        assert "recent" not in sections

        zero = {**new, "weights": {"collaborative": 0, "svd": 0, "content": 0, "popularity": 0, "user_cf": 0}}
        assert client.put("/admin/settings", json=zero, headers=ADMIN).status_code == 422
        assert client.put("/admin/settings", json={**new, "max_per_category": 0}, headers=ADMIN).status_code == 422
    finally:
        reset = client.post("/admin/settings/reset", headers=ADMIN).json()
    assert reset["current"] == reset["defaults"]


def test_admin_evaluate_and_stats(client: TestClient) -> None:
    stats = client.get("/admin/stats", headers=ADMIN).json()
    assert stats["n_products"] == 500 and stats["n_events"] == sum(stats["events_by_type"].values())
    result = client.post("/admin/evaluate", headers=ADMIN).json()
    methods = {r["method"]: r for r in result["results"]}
    # With default settings, the admin row must match the default hybrid exactly
    assert methods["hybrid_admin"]["hit_rate_at_10"] == methods["hybrid"]["hit_rate_at_10"]
    assert "user_cf" in methods


def test_every_admin_endpoint_needs_the_token(client: TestClient) -> None:
    from app.main import app

    admin_routes = [(m, r.path) for r in app.routes if getattr(r, "path", "").startswith("/admin") for m in r.methods]
    assert len(admin_routes) >= 5  # settings (GET, PUT), reset, evaluate, stats
    for method, path in admin_routes:
        assert client.request(method, path).status_code == 401, (method, path)
        assert client.request(method, path, headers={"X-Admin-Token": "wrong"}).status_code == 401, (method, path)
    assert client.get("/admin/settings", headers=ADMIN).status_code == 200
    assert client.get("/products", params={"limit": 1}).status_code == 200  # shop pages stay public


def test_admin_is_locked_when_no_token_is_configured(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ADMIN_TOKEN")
    r = client.get("/admin/settings", headers=ADMIN)
    assert r.status_code == 401 and "ADMIN_TOKEN" in r.json()["detail"]


def test_admin_can_set_the_user_cf_weight(client: TestClient) -> None:
    defaults = client.get("/admin/settings", headers=ADMIN).json()["defaults"]
    assert "user_cf" in defaults["weights"]
    try:
        new = {**defaults, "weights": {**defaults["weights"], "user_cf": 0.9}}
        assert client.put("/admin/settings", json=new, headers=ADMIN).json()["current"]["weights"]["user_cf"] == 0.9
        # Older clients that do not send user_cf get the default weight
        old_client = {**defaults, "weights": {k: v for k, v in defaults["weights"].items() if k != "user_cf"}}
        saved = client.put("/admin/settings", json=old_client, headers=ADMIN).json()["current"]
        assert saved["weights"]["user_cf"] == defaults["weights"]["user_cf"]
    finally:
        client.post("/admin/settings/reset", headers=ADMIN)



def test_product_images_match_type_and_are_stable(client: TestClient) -> None:
    import pytest as _pytest

    from app.images import MANIFEST_PATH, photo_candidates, product_photo

    if not MANIFEST_PATH.exists():
        _pytest.skip("run python -m data.fetch_images first")
    phones = photo_candidates("Voltix Neo Smartphone", "Electronics")
    assert phones and all(p["category"] == "smartphones" for p in phones)
    assert product_photo(1, "Voltix Neo Smartphone", "Electronics") == product_photo(1, "Voltix Neo Smartphone", "Electronics")
    assert photo_candidates("Inkstone Ergonomic Wireless Mouse", "Office Supplies") == []  # never a phone photo
    assert all("chair" in p["title"].lower() for p in photo_candidates("Clarion Classic Office Chair", "Office Supplies"))

    products: dict[str, dict] = {}
    for p in client.get("/products", params={"limit": 500}).json()["items"]:
        products.setdefault(p["category"], p)  # first product of each category
    assert products["Electronics"]["name"].endswith("Smartphone")
    photo = client.get(products["Electronics"]["image_url"])
    assert photo.status_code == 200 and photo.headers["content-type"] == "image/webp"
    tile = client.get(products["Books"]["image_url"])  # books have no photos -> line-icon tile
    assert tile.headers["content-type"].startswith("image/svg+xml") and "#EFEFEF" in tile.text
    assert client.get("/images/1.svg").status_code == 200  # old URL still works


def test_recently_viewed_keeps_out_of_stock_with_flag(client: TestClient) -> None:
    items = client.get("/products", params={"limit": 500}).json()["items"]
    sold_out = next(p for p in items if p["stock"] <= 0)
    assert sold_out["in_stock"] is False and all(p["in_stock"] == (p["stock"] > 0) for p in items)
    user = client.post("/users").json()
    client.post("/events", json={"user_id": user["id"], "product_id": sold_out["id"], "event_type": "view"})
    home = client.get("/recommend/home", params={"user_id": user["id"]}).json()
    recent = next(s for s in home["sections"] if s["key"] == "recent")["items"]
    assert recent[0]["product"]["id"] == sold_out["id"] and recent[0]["product"]["in_stock"] is False


def test_also_bought_endpoint(client: TestClient) -> None:
    found = None
    for pid in range(1, 80):
        recs = client.get(f"/recommend/also-bought/{pid}").json()
        if recs:
            found = (pid, recs)
            break
    assert found, "expected co-purchase data"
    pid, recs = found
    assert pid not in [r["product"]["id"] for r in recs]
    assert all(r["method"] == "also_bought" and r["reason"].endswith("bought both") for r in recs)
    assert all(int(r["reason"].split()[0]) >= 2 and r["product"]["in_stock"] for r in recs)
    assert client.get("/recommend/also-bought/99999").status_code == 404

