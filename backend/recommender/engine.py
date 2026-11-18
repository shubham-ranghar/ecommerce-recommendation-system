"""The recommendation engine used by the API.

It loads data from SQLite, trains every model, and decides WHICH list to show
based on CONTEXT:
  - new visitor (fewer than 3 events)  -> popularity + category-based lists
  - returning user                     -> personalised hybrid list
  - the current page decides the list  -> home / product page / cart

Models are retrained automatically (at most every few seconds) after new events
arrive, while each user's own history is always read fresh from the database.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import Engine, text

from app.database import engine as default_engine
from recommender.base import Catalog, Recommendation, UserHistory, build_history, build_interaction_matrix
from recommender.collaborative import FrequentlyBoughtTogether, ItemCFRecommender, SVDRecommender
from recommender.content_based import ContentBasedRecommender
from recommender.hybrid import HybridRecommender
from recommender.popularity import PopularityRecommender

MIN_EVENTS_FOR_PERSONALISATION = 3


def load_products(db: Engine) -> pd.DataFrame:
    return pd.read_sql(text("SELECT * FROM products"), db)


def load_events(db: Engine, user_id: int | None = None) -> pd.DataFrame:
    query = "SELECT user_id, product_id, event_type, rating, session_id, timestamp FROM events"
    params: dict = {}
    if user_id is not None:
        query += " WHERE user_id = :uid"
        params["uid"] = user_id
    events = pd.read_sql(text(query), db, params=params)
    events["timestamp"] = pd.to_datetime(events["timestamp"], format="mixed")
    return events


class RecommendationEngine:
    def __init__(self, db: Engine | None = None, refit_seconds: float = 3.0) -> None:
        self.db = db or default_engine
        self.refit_seconds = refit_seconds
        self._lock = threading.Lock()
        self._dirty = True
        self._last_fit = 0.0

    # ---------- training ----------
    def fit(self) -> None:
        """Load all data and (re)train every model."""
        with self._lock:
            products = load_products(self.db)
            events = load_events(self.db)
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if not events.empty:
                now = max(now, events["timestamp"].max().to_pydatetime())

            self.catalog = Catalog(products)
            matrix, _ = build_interaction_matrix(events, self.catalog)
            self.popularity = PopularityRecommender().fit(events, self.catalog, now=now)
            self.content = ContentBasedRecommender().fit(self.catalog)
            self.item_cf = ItemCFRecommender().fit(matrix, self.catalog)
            self.svd = SVDRecommender().fit(matrix, self.catalog)
            self.fbt = FrequentlyBoughtTogether().fit(events, self.catalog)
            self.hybrid = HybridRecommender(self.popularity, self.content, self.item_cf, self.svd)
            self.n_events = len(events)
            self._dirty = False
            self._last_fit = time.time()

    def mark_dirty(self) -> None:
        """Call after new events: models will be retrained on the next request."""
        self._dirty = True

    def ensure_fresh(self) -> None:
        never_trained = not hasattr(self, "catalog")
        if never_trained or (self._dirty and time.time() - self._last_fit >= self.refit_seconds):
            self.fit()

    # ---------- helpers ----------
    def history(self, user_id: int | None) -> UserHistory:
        if user_id is None:
            return build_history(pd.DataFrame(), self.catalog)
        return build_history(load_events(self.db, user_id), self.catalog)

    def _idx(self, product_ids: list[int]) -> set[int]:
        return {self.catalog.index[p] for p in product_ids if p in self.catalog.index}

    # ---------- page level recommendations ----------
    def home(self, user_id: int | None, n: int = 10) -> dict:
        """Home page lists, chosen by context (new vs returning user)."""
        self.ensure_fresh()
        history = self.history(user_id)
        sections: list[dict] = []

        if history.n_events < MIN_EVENTS_FOR_PERSONALISATION:
            user_type = "new"
            sections.append(self._section("trending", "Trending now", "Hot products right now", "popularity",
                                          self.popularity.top(n)))
            if history.recent:  # a new visitor already looked at something -> category based
                category = str(self.catalog.categories[history.recent[0]])
                sections.append(self._section(
                    "category", f"Popular in {category}", "Because you are browsing this category", "popularity",
                    self.popularity.top(n, category=category, exclude=history.seen, reason=f"Popular in {category}"),
                ))
            best = sorted(range(len(self.catalog)), key=lambda i: -self.popularity.sales[i])
            best = [i for i in best if self.catalog.in_stock[i]][:n]
            sections.append(self._section(
                "bestsellers", "Best sellers", "Most purchased products", "popularity",
                [Recommendation(int(self.catalog.ids[i]), float(self.popularity.sales[i]),
                                f"{int(self.popularity.sales[i])} purchases", "popularity") for i in best],
            ))
        else:
            user_type = "returning"
            personal = self.hybrid.recommend(history, n=n)
            sections.append(self._section("for_you", "Recommended for you",
                                          "Personalised with the hybrid recommender", "hybrid", personal))
            last = int(self.catalog.ids[history.recent[0]])
            similar = self.content.similar(last, n=6, exclude=history.purchased)
            for r in similar:
                r.reason = f"Because you {history.actions.get(history.recent[0], 'viewed')} {self.catalog.names[history.recent[0]]}"
            sections.append(self._section("because", f"Inspired by {self.catalog.names[history.recent[0]]}",
                                          "Similar to what you looked at last", "content", similar))
            shown = self._idx([r.product_id for r in personal])
            sections.append(self._section("trending", "Trending now", "What everyone is looking at", "popularity",
                                          self.popularity.top(n, exclude=shown | history.purchased)))
        return {"user_id": user_id, "user_type": user_type, "n_events": history.n_events, "sections": sections}

    def similar(self, product_id: int, n: int = 8) -> list[Recommendation]:
        self.ensure_fresh()
        return self.content.similar(product_id, n)

    def also_liked(self, product_id: int, n: int = 8) -> list[Recommendation]:
        self.ensure_fresh()
        recs = self.item_cf.also_liked(product_id, n)
        if len(recs) < n:  # rarely seen product -> fill up with content-based results
            have = self._idx([r.product_id for r in recs]) | {self.catalog.index[product_id]}
            for r in self.content.similar(product_id, n, exclude=have)[: n - len(recs)]:
                r.reason = "Similar product (not enough shopper data yet)"
                recs.append(r)
        return recs

    def cart(self, user_id: int | None, product_ids: list[int], n: int = 6) -> list[Recommendation]:
        """'Frequently bought together' for the products in the cart."""
        self.ensure_fresh()
        history = self.history(user_id)
        exclude = history.purchased
        recs = self.fbt.recommend(product_ids, n, exclude=exclude)
        have = self._idx(product_ids + [r.product_id for r in recs]) | exclude
        # Fallback 1: customers who liked the cart items also liked
        for pid in product_ids:
            if len(recs) >= n:
                break
            for r in self.item_cf.also_liked(pid, n, exclude=have):
                if len(recs) >= n:
                    break
                r.reason = f"Customers who liked {self.catalog.names[self.catalog.index[pid]]} also liked this"
                recs.append(r)
                have.add(self.catalog.index[r.product_id])
        # Fallback 2: popular products
        if len(recs) < n:
            recs += self.popularity.top(n - len(recs), exclude=have)
        return recs[:n]

    @staticmethod
    def _section(key: str, title: str, subtitle: str, method: str, items: list[Recommendation]) -> dict:
        return {"key": key, "title": title, "subtitle": subtitle, "method": method, "items": items}
