"""STEP 2 - REPRESENT: shared building blocks used by every recommender.

- Catalog: the product table with fast "product id <-> row index" lookups.
- event_weights: turns raw events into implicit-feedback scores.
- UserHistory: one user's interactions as a vector over all products.
- build_interaction_matrix: the users x items matrix used by collaborative filtering.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix

# Implicit feedback: stronger actions say more about what the user likes.
EVENT_WEIGHTS: dict[str, float] = {"view": 1.0, "click": 2.0, "add_to_cart": 3.0, "purchase": 5.0}
ACTION_VERBS: dict[str, str] = {
    "view": "viewed",
    "click": "viewed",
    "add_to_cart": "added",
    "purchase": "bought",
    "rating": "rated",
}


def event_weights(events: pd.DataFrame) -> pd.Series:
    """Weight of every event. Ratings: 5 stars -> +3, 3 stars -> 0, 1 star -> -3."""
    weights = events["event_type"].map(EVENT_WEIGHTS).fillna(0.0).astype(float)
    is_rating = events["event_type"] == "rating"
    if is_rating.any():
        weights[is_rating] = (events.loc[is_rating, "rating"].fillna(3).astype(float) - 3.0) * 1.5
    return weights


@dataclass
class Recommendation:
    """One recommended product, with the reason shown to the user."""

    product_id: int
    score: float
    reason: str
    method: str


class Catalog:
    """Products sorted by id. Row i of every score array refers to catalog.ids[i]."""

    def __init__(self, products: pd.DataFrame) -> None:
        self.products = products.sort_values("id").reset_index(drop=True)
        self.ids: np.ndarray = self.products["id"].to_numpy()
        self.index: dict[int, int] = {int(pid): i for i, pid in enumerate(self.ids)}
        self.names: list[str] = self.products["name"].tolist()
        self.categories: np.ndarray = self.products["category"].to_numpy()
        self.prices: np.ndarray = self.products["price"].to_numpy(dtype=float)
        self.stock: np.ndarray = self.products["stock"].to_numpy(dtype=int)
        # Relative price inside the category: 0 = cheapest, 1 = most expensive.
        # Comparing a laptop to pasta makes no sense, so price preference uses this.
        self.price_pct: np.ndarray = (
            self.products.groupby("category")["price"].rank(pct=True).to_numpy(dtype=float)
        )

    def __len__(self) -> int:
        return len(self.ids)

    @property
    def in_stock(self) -> np.ndarray:
        return self.stock > 0


@dataclass
class UserHistory:
    """What one user did, as vectors aligned with the catalog."""

    weights: np.ndarray  # strength of interest per product (>= 0)
    purchased: set[int] = field(default_factory=set)  # catalog indices
    recent: list[int] = field(default_factory=list)  # catalog indices, most recent first
    actions: dict[int, str] = field(default_factory=dict)  # strongest action per product
    n_events: int = 0

    @property
    def seen(self) -> set[int]:
        return set(np.flatnonzero(self.weights).tolist()) | set(self.actions)

    @property
    def is_empty(self) -> bool:
        return self.n_events == 0


def build_history(user_events: pd.DataFrame, catalog: Catalog) -> UserHistory:
    """Turn one user's events into a UserHistory."""
    weights = np.zeros(len(catalog))
    if user_events.empty:
        return UserHistory(weights=weights)
    ev = user_events[user_events["product_id"].isin(catalog.index.keys())].copy()
    ev["w"] = event_weights(ev)
    ev["idx"] = ev["product_id"].map(catalog.index)

    summed = ev.groupby("idx")["w"].sum().clip(lower=0)
    weights[summed.index.to_numpy()] = np.log1p(summed.to_numpy())  # log: dampen heavy repeat views

    purchased = set(ev.loc[ev["event_type"] == "purchase", "idx"].tolist())
    recent = ev.sort_values("timestamp", ascending=False)["idx"].drop_duplicates().tolist()

    rank = {"rating": 0, "view": 1, "click": 2, "add_to_cart": 3, "purchase": 4}
    ev["rank"] = ev["event_type"].map(rank).fillna(0)
    strongest = ev.sort_values("rank").groupby("idx")["event_type"].last()
    actions = {int(i): ACTION_VERBS.get(t, "viewed") for i, t in strongest.items()}
    return UserHistory(weights, purchased, recent, actions, n_events=len(ev))


def build_interaction_matrix(events: pd.DataFrame, catalog: Catalog) -> tuple[csr_matrix, list[int]]:
    """Users x items matrix of log(1 + summed event weights). Returns (matrix, user ids)."""
    ev = events[events["product_id"].isin(catalog.index.keys())].copy()
    ev["w"] = event_weights(ev)
    grouped = ev.groupby(["user_id", "product_id"])["w"].sum().clip(lower=0).reset_index()
    grouped = grouped[grouped["w"] > 0]
    user_ids = sorted(grouped["user_id"].unique().tolist())
    user_index = {u: i for i, u in enumerate(user_ids)}
    rows = grouped["user_id"].map(user_index).to_numpy()
    cols = grouped["product_id"].map(catalog.index).to_numpy()
    values = np.log1p(grouped["w"].to_numpy())
    matrix = csr_matrix((values, (rows, cols)), shape=(len(user_ids), len(catalog)))
    return matrix, user_ids


def minmax(x: np.ndarray) -> np.ndarray:
    """Scale values to 0..1 so scores from different methods can be blended."""
    lo, hi = float(np.min(x)), float(np.max(x))
    if hi - lo < 1e-12:
        return np.zeros_like(x, dtype=float)
    return (x - lo) / (hi - lo)


def top_indices(scores: np.ndarray, k: int, exclude: set[int] | None = None) -> list[int]:
    """Indices of the k highest scores, skipping excluded indices and zero scores."""
    s = scores.astype(float).copy()
    if exclude:
        s[list(exclude)] = -np.inf
    order = np.argsort(-s, kind="stable")
    return [int(i) for i in order[:k] if np.isfinite(s[i]) and s[i] > 0]
