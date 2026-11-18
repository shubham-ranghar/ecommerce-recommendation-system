"""End-to-end API tests on a temporary database (see conftest.py)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


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
    data = client.get("/admin/settings").json()
    assert data["current"] == data["defaults"]
    try:
        new = {**data["defaults"], "max_per_category": 1, "show_recently_viewed": False}
        assert client.put("/admin/settings", json=new).json()["current"]["max_per_category"] == 1
        home = client.get("/recommend/home", params={"user_id": 1}).json()
        sections = {s["key"]: s for s in home["sections"]}
        cats = [i["product"]["category"] for i in sections["for_you"]["items"]]
        assert len(cats) == len(set(cats))  # max 1 per category
        assert "recent" not in sections

        zero = {**new, "weights": {"collaborative": 0, "svd": 0, "content": 0, "popularity": 0}}
        assert client.put("/admin/settings", json=zero).status_code == 422
        assert client.put("/admin/settings", json={**new, "max_per_category": 0}).status_code == 422
    finally:
        reset = client.post("/admin/settings/reset").json()
    assert reset["current"] == reset["defaults"]


def test_admin_evaluate_and_stats(client: TestClient) -> None:
    stats = client.get("/admin/stats").json()
    assert stats["n_products"] == 500 and stats["n_events"] == sum(stats["events_by_type"].values())
    result = client.post("/admin/evaluate").json()
    methods = {r["method"]: r for r in result["results"]}
    # With default settings, the admin row must match the default hybrid exactly
    assert methods["hybrid_admin"]["hit_rate_at_10"] == methods["hybrid"]["hit_rate_at_10"]

