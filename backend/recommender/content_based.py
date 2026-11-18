"""Method 2 - CONTENT-BASED: "products that look alike".

1. Each product becomes a text: name + description + tags + category.
2. TF-IDF turns each text into a vector. Words that are common in this product
   but rare in the whole shop (e.g. "noise-cancelling") get a high weight.
3. Cosine similarity between two vectors = how similar two products are (0..1).
For a user, we add up the similarity of every product to the items they interacted with.
Works without any other users, so it also helps with brand-new products.
"""
from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from recommender.base import Catalog, Recommendation, UserHistory, top_indices


class ContentBasedRecommender:
    name = "content"

    def fit(self, catalog: Catalog) -> "ContentBasedRecommender":
        self.catalog = catalog
        p = catalog.products
        tags_text = p["tags"].str.replace(",", " ").str.replace("-", " ")
        # Category is repeated so it counts a bit more than a single word.
        texts = p["name"] + " " + p["description"] + " " + tags_text + " " + p["category"] + " " + p["category"]
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        self.tfidf = self.vectorizer.fit_transform(texts)
        self.sim = cosine_similarity(self.tfidf)
        np.fill_diagonal(self.sim, 0.0)
        self.tag_sets = [set(t.split(",")) for t in p["tags"]]
        return self

    def explain_pair(self, i: int, j: int) -> str:
        """Reason why product j is similar to product i."""
        shared = sorted(self.tag_sets[i] & self.tag_sets[j])
        if shared:
            return "Similar features: " + ", ".join(shared[:3])
        brand_i = self.catalog.products.at[i, "brand"]
        if brand_i == self.catalog.products.at[j, "brand"]:
            return f"Same brand: {brand_i}"
        return f"Also in {self.catalog.categories[j]}"

    def similar(self, product_id: int, n: int = 8, exclude: set[int] | None = None) -> list[Recommendation]:
        """Products most similar to one product (used on the product page)."""
        i = self.catalog.index[product_id]
        exclude = set(exclude or set()) | set(np.flatnonzero(~self.catalog.in_stock).tolist())
        return [
            Recommendation(int(self.catalog.ids[j]), float(self.sim[i, j]), self.explain_pair(i, j), self.name)
            for j in top_indices(self.sim[i], n, exclude)
        ]

    def score_user(self, history: UserHistory) -> tuple[np.ndarray, np.ndarray]:
        """Score every product for a user. Also returns which history item contributed most."""
        n = len(self.catalog)
        hist = np.flatnonzero(history.weights)
        if len(hist) == 0:
            return np.zeros(n), np.full(n, -1)
        contrib = self.sim[:, hist] * history.weights[hist]  # (products x history items)
        scores = contrib.sum(axis=1) / history.weights[hist].sum()
        best = hist[contrib.argmax(axis=1)]
        return scores, best
