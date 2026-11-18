"""Request and response shapes for the API (Pydantic models)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

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


# ---------- admin ----------
class HybridWeights(BaseModel):
    """Blend weights of the hybrid. Only their ratio matters; they do not need to sum to 1."""

    collaborative: float = Field(ge=0, le=1)
    svd: float = Field(ge=0, le=1)
    content: float = Field(ge=0, le=1)
    popularity: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def at_least_one(self) -> "HybridWeights":
        if self.collaborative + self.svd + self.content + self.popularity <= 0:
            raise ValueError("At least one method needs a weight above 0")
        return self


class RecommenderSettingsModel(BaseModel):
    weights: HybridWeights
    max_per_category: int = Field(ge=1, le=10, description="Diversity: max items per category in the top 10")
    price_penalty: float = Field(ge=0, le=1, description="Max score lost for being far from the user's price range")
    hide_out_of_stock: bool
    hide_purchased: bool
    min_events_for_personalisation: int = Field(ge=1, le=20)
    show_recently_viewed: bool
    show_purchase_based: bool


class AdminSettingsOut(BaseModel):
    current: RecommenderSettingsModel
    defaults: RecommenderSettingsModel


class AdminStatsOut(BaseModel):
    n_products: int
    n_out_of_stock: int
    n_users: int
    n_events: int
    events_by_type: dict[str, int]
