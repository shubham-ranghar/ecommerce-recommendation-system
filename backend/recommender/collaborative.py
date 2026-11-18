"""Method 3 - COLLABORATIVE FILTERING: learn from what other shoppers did.

Item-item CF:
    Each product is a column of the users x items matrix (who interacted, how strongly).
    Two products are similar when the same users like both (cosine similarity of columns).
    We keep only the top-k neighbours of each product to remove noise, and "shrink"
    similarities that are based on very few shared users.

Matrix factorisation (TruncatedSVD):
    Compresses the users x items matrix into a few hidden "taste" factors
    (e.g. "budget tech fan"). A user's score for a product = how well their
    factors match the product's factors.

Frequently bought together:
    Counts how often two products end up in the same cart/purchase session.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, diags
from sklearn.decomposition import TruncatedSVD

from recommender.base import Catalog, Recommendation, UserHistory, top_indices


class ItemCFRecommender:
    name = "collaborative"

    def __init__(self, k_neighbours: int = 50, shrinkage: float = 5.0, min_support: int = 2) -> None:
        self.k_neighbours = k_neighbours
        self.shrinkage = shrinkage
        self.min_support = min_support  # "also liked" needs at least this many shared shoppers

    def fit(self, matrix: csr_matrix, catalog: Catalog) -> "ItemCFRecommender":
        self.catalog = catalog
        norms = np.sqrt(np.asarray(matrix.multiply(matrix).sum(axis=0))).ravel()
        norms[norms == 0] = 1.0
        normalised = matrix @ diags(1.0 / norms)
        sim = (normalised.T @ normalised).toarray()

        binary = (matrix > 0).astype(float)
        self.co_users = (binary.T @ binary).toarray()  # number of users who liked both
        sim *= self.co_users / (self.co_users + self.shrinkage)
        np.fill_diagonal(sim, 0.0)

        # Keep only the k strongest neighbours of each product
        if self.k_neighbours < sim.shape[1]:
            cutoff = -np.partition(-sim, self.k_neighbours - 1, axis=1)[:, self.k_neighbours - 1]
            sim[sim < cutoff[:, None]] = 0.0
        self.sim = sim
        return self

    def also_liked(self, product_id: int, n: int = 8, exclude: set[int] | None = None) -> list[Recommendation]:
        """'Customers who liked this also liked' for the product page."""
        i = self.catalog.index[product_id]
        exclude = set(exclude or set()) | set(np.flatnonzero(~self.catalog.in_stock).tolist())
        exclude |= set(np.flatnonzero(self.co_users[i] < self.min_support).tolist())
        recs = []
        for j in top_indices(self.sim[i], n, exclude):
            shared = int(self.co_users[i, j])
            recs.append(
                Recommendation(
                    int(self.catalog.ids[j]),
                    float(self.sim[i, j]),
                    f"{shared} shopper{'s' if shared != 1 else ''} liked both",
                    self.name,
                )
            )
        return recs

    def score_user(self, history: UserHistory) -> tuple[np.ndarray, np.ndarray]:
        """Score = sum of similarities to the user's items. Also returns the top contributor."""
        n = len(self.catalog)
        hist = np.flatnonzero(history.weights)
        if len(hist) == 0:
            return np.zeros(n), np.full(n, -1)
        contrib = self.sim[hist, :].T * history.weights[hist]  # (products x history items)
        return contrib.sum(axis=1), hist[contrib.argmax(axis=1)]


class SVDRecommender:
    name = "svd"

    def __init__(self, n_components: int = 32) -> None:
        self.n_components = n_components

    def fit(self, matrix: csr_matrix, catalog: Catalog) -> "SVDRecommender":
        self.catalog = catalog
        k = max(1, min(self.n_components, min(matrix.shape) - 1))
        self.model = TruncatedSVD(n_components=k, random_state=42).fit(matrix)
        self.item_factors = self.model.components_  # (factors x products)
        return self

    def score_user(self, history: UserHistory) -> np.ndarray:
        """'Fold in' the user: project their history onto the factors, then back to products.
        This also works for users who were not in the training matrix."""
        user_factors = history.weights @ self.item_factors.T
        return user_factors @ self.item_factors


class FrequentlyBoughtTogether:
    name = "bought_together"

    def fit(self, events: pd.DataFrame, catalog: Catalog) -> "FrequentlyBoughtTogether":
        self.catalog = catalog
        n = len(catalog)
        baskets = events[
            events["event_type"].isin(["add_to_cart", "purchase"]) & events["product_id"].isin(catalog.index.keys())
        ][["session_id", "product_id"]].drop_duplicates()
        if baskets.empty:
            self.co = np.zeros((n, n))
            return self
        session_ids = {s: i for i, s in enumerate(baskets["session_id"].unique())}
        rows = baskets["session_id"].map(session_ids).to_numpy()
        cols = baskets["product_id"].map(catalog.index).to_numpy()
        basket_matrix = csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(session_ids), n))
        self.co = (basket_matrix.T @ basket_matrix).toarray()  # times bought together
        np.fill_diagonal(self.co, 0.0)
        return self

    def recommend(self, cart_product_ids: list[int], n: int = 6, exclude: set[int] | None = None) -> list[Recommendation]:
        cart = [self.catalog.index[p] for p in cart_product_ids if p in self.catalog.index]
        if not cart:
            return []
        exclude = set(exclude or set()) | set(cart) | set(np.flatnonzero(~self.catalog.in_stock).tolist())
        contrib = self.co[cart, :]  # (cart items x products)
        scores = contrib.sum(axis=0)
        best = np.array(cart)[contrib.argmax(axis=0)]
        recs = []
        for j in top_indices(scores, n, exclude):
            times = int(self.co[best[j], j])
            recs.append(
                Recommendation(
                    int(self.catalog.ids[j]),
                    float(scores[j]),
                    f"Bought together with {self.catalog.names[best[j]]} ({times}x)",
                    self.name,
                )
            )
        return recs
