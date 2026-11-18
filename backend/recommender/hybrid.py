"""Method 4 - HYBRID: blend all methods, then apply business rules.

Pipeline for one user:
  GENERATE CANDIDATES  take the top 100 products from each method and merge them.
  RANK                 1. normalise each method's scores to 0..1 (min-max)
                       2. weighted sum: 35% item-CF + 20% SVD + 25% content + 20% popularity
                       3. business rules:
                          - remove out-of-stock items
                          - remove items the user already bought
                          - prefer the user's usual price range (soft penalty)
                          - diversity: max 3 items from the same category in the top 10
  EXPLAIN              the method that contributed most decides the reason text.
"""
from __future__ import annotations

from collections import Counter

import numpy as np

from recommender.base import Recommendation, UserHistory, minmax, top_indices
from recommender.collaborative import ItemCFRecommender, SVDRecommender
from recommender.content_based import ContentBasedRecommender
from recommender.popularity import PopularityRecommender

DEFAULT_WEIGHTS: dict[str, float] = {"collaborative": 0.35, "svd": 0.20, "content": 0.25, "popularity": 0.20}


class HybridRecommender:
    name = "hybrid"

    def __init__(
        self,
        popularity: PopularityRecommender,
        content: ContentBasedRecommender,
        item_cf: ItemCFRecommender,
        svd: SVDRecommender,
        weights: dict[str, float] | None = None,
        n_candidates: int = 100,
        max_per_category: int = 3,
        price_penalty: float = 0.3,
    ) -> None:
        self.popularity = popularity
        self.content = content
        self.item_cf = item_cf
        self.svd = svd
        self.weights = weights or DEFAULT_WEIGHTS
        self.n_candidates = n_candidates
        self.max_per_category = max_per_category
        self.price_penalty = price_penalty

    def recommend(
        self,
        history: UserHistory,
        n: int = 10,
        exclude: set[int] | None = None,
        apply_stock_filter: bool = True,
    ) -> list[Recommendation]:
        catalog = self.popularity.catalog

        # 1) Score every product with every method
        content_scores, content_from = self.content.score_user(history)
        cf_scores, cf_from = self.item_cf.score_user(history)
        method_scores = {
            "popularity": self.popularity.score_user(history),
            "content": content_scores,
            "collaborative": cf_scores,
            "svd": self.svd.score_user(history),
        }

        # 2) Business rules that remove items completely
        blocked = set(exclude or set()) | history.purchased
        if apply_stock_filter:
            blocked |= set(np.flatnonzero(~catalog.in_stock).tolist())

        # 3) Candidate generation: union of each method's top list
        candidates: set[int] = set()
        for scores in method_scores.values():
            candidates |= set(top_indices(scores, self.n_candidates, blocked))
        if not candidates:
            return []
        cand = np.array(sorted(candidates))

        # 4) Ranking: weighted blend of normalised scores
        parts = {m: self.weights.get(m, 0.0) * minmax(s[cand]) for m, s in method_scores.items()}
        blended = np.sum(list(parts.values()), axis=0)

        # 5) Soft rule: prefer the user's usual (relative) price range
        if history.weights.sum() > 0:
            target = float(np.average(catalog.price_pct, weights=history.weights))
            gap = np.abs(catalog.price_pct[cand] - target)
            blended = blended * (1.0 - self.price_penalty * np.clip(gap / 0.5, 0.0, 1.0))

        # 6) Diversity: at most `max_per_category` per category
        picked: list[int] = []
        per_category: Counter[str] = Counter()
        for pos in np.argsort(-blended, kind="stable"):
            category = catalog.categories[cand[pos]]
            if per_category[category] >= self.max_per_category:
                continue
            per_category[category] += 1
            picked.append(int(pos))
            if len(picked) == n:
                break

        recs = []
        for pos in picked:
            i = int(cand[pos])
            dominant = max(parts, key=lambda m: parts[m][pos])
            reason = self._reason(i, dominant, content_from, cf_from, history)
            recs.append(Recommendation(int(catalog.ids[i]), float(blended[pos]), reason, f"hybrid:{dominant}"))
        return recs

    def _reason(
        self, i: int, dominant: str, content_from: np.ndarray, cf_from: np.ndarray, history: UserHistory
    ) -> str:
        """Human-readable reason based on the method that contributed most."""
        catalog = self.popularity.catalog
        if dominant == "collaborative" and cf_from[i] >= 0:
            return f"Customers who liked {catalog.names[cf_from[i]]} also liked this"
        if dominant == "content" and content_from[i] >= 0:
            verb = history.actions.get(int(content_from[i]), "viewed")
            return f"Because you {verb} {catalog.names[content_from[i]]}"
        if dominant == "svd":
            return f"Shoppers with your taste love this {catalog.categories[i]} pick"
        return self.popularity.reason(i)
