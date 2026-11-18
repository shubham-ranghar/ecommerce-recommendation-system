"""Method 1 - POPULARITY: trending and best-selling products.

Score of a product = sum over its events of (event weight x recency decay).
Recency decay halves the value of an event every `half_life_days` days, so
something that is hot this week beats something that was popular months ago.
Used for new visitors (cold start), when we know nothing about the user.
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from recommender.base import Catalog, Recommendation, UserHistory, event_weights, top_indices


class PopularityRecommender:
    name = "popularity"

    def __init__(self, half_life_days: float = 14.0) -> None:
        self.half_life_days = half_life_days

    def fit(self, events: pd.DataFrame, catalog: Catalog, now: datetime | None = None) -> "PopularityRecommender":
        self.catalog = catalog
        n = len(catalog)
        self.scores = np.zeros(n)
        self.sales = np.zeros(n)
        self.weekly_shoppers = np.zeros(n)
        ev = events[events["product_id"].isin(catalog.index.keys())]
        if ev.empty:
            return self

        now = now or ev["timestamp"].max()
        age_days = ((now - ev["timestamp"]).dt.total_seconds() / 86400).clip(lower=0)
        decay = 0.5 ** (age_days / self.half_life_days)
        weights = event_weights(ev).clip(lower=0) * decay
        idx = ev["product_id"].map(catalog.index).to_numpy()

        self.scores = np.bincount(idx, weights=weights.to_numpy(), minlength=n)
        is_purchase = (ev["event_type"] == "purchase").to_numpy()
        self.sales = np.bincount(idx[is_purchase], minlength=n).astype(float)
        last_week = (age_days <= 7).to_numpy()
        shoppers = ev[last_week].groupby("product_id")["user_id"].nunique()
        for pid, count in shoppers.items():
            self.weekly_shoppers[catalog.index[int(pid)]] = count
        return self

    def score_user(self, history: UserHistory | None = None) -> np.ndarray:
        """Popularity is the same for everyone (not personalised)."""
        return self.scores.copy()

    def reason(self, i: int) -> str:
        category = self.catalog.categories[i]
        if self.weekly_shoppers[i] >= 3:
            return f"Trending: {int(self.weekly_shoppers[i])} shoppers this week"
        if self.sales[i] >= 3:
            return f"Best seller in {category}"
        return f"Popular in {category}"

    def top(
        self,
        n: int = 10,
        category: str | None = None,
        exclude: set[int] | None = None,
        in_stock_only: bool = True,
        reason: str | None = None,
    ) -> list[Recommendation]:
        """Top-n popular products, optionally inside one category."""
        exclude = set(exclude or set())
        if in_stock_only:
            exclude |= set(np.flatnonzero(~self.catalog.in_stock).tolist())
        if category:
            exclude |= set(np.flatnonzero(self.catalog.categories != category).tolist())
        return [
            Recommendation(int(self.catalog.ids[i]), float(self.scores[i]), reason or self.reason(i), self.name)
            for i in top_indices(self.scores, n, exclude)
        ]
