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
