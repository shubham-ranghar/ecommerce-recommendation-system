"""Request and response shapes for the API (Pydantic models)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EventType = Literal["view", "click", "add_to_cart", "purchase", "rating"]


class ProductOut(BaseModel):
    id: int
    name: str
    category: str
    brand: str
    price: float
    description: str
    tags: list[str]
    stock: int
    image_url: str
    rating_avg: float | None = None
    rating_count: int = 0


class ProductPage(BaseModel):
    total: int
    items: list[ProductOut]


class UserOut(BaseModel):
    id: int
    name: str
    is_demo: bool
    persona: str
    price_band: str
    n_events: int = 0


class EventIn(BaseModel):
    user_id: int
    product_id: int
    event_type: EventType
    rating: int | None = Field(default=None, ge=1, le=5)
    session_id: str | None = None


class EventOut(BaseModel):
    id: int
    status: str = "saved"


class RecommendationOut(BaseModel):
    product: ProductOut
    score: float
    reason: str
    method: str


class SectionOut(BaseModel):
    key: str
    title: str
    subtitle: str
    method: str
    items: list[RecommendationOut]


class HomeOut(BaseModel):
    user_id: int | None
    user_type: Literal["new", "returning"]
    n_events: int
    sections: list[SectionOut]
