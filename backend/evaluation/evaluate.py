"""STEP 5 - MEASURE: offline evaluation of every recommender.

Run from the backend folder:
    python -m evaluation.evaluate

Method:
1. Time-based split: for every user (with >= 5 events) the LATEST 20% of their
   events go to the test set, the rest to the training set. This copies real
   life: we learn from the past and try to predict the future.
2. Every model is trained ONLY on the training events.
3. For each test user we recommend 10 products they have NOT interacted with
   in training. "Relevant" products = new products they interacted with in the test period.
4. Metrics (averaged over users):
   - Precision@10: share of the 10 recommendations that were relevant
   - Recall@10:    share of the relevant products that we found in the top 10
   - Hit rate@10:  share of users with at least one relevant product in the top 10
   - Coverage:     share of the whole catalogue that was recommended to anyone
"""
from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine as default_engine  # noqa: E402
from recommender.base import Catalog, UserHistory, build_history, build_interaction_matrix, event_weights, minmax, top_indices  # noqa: E402
from recommender.collaborative import ItemCFRecommender, SVDRecommender  # noqa: E402
from recommender.content_based import ContentBasedRecommender  # noqa: E402
from recommender.engine import load_events, load_products  # noqa: E402
from recommender.hybrid import HybridRecommender  # noqa: E402
from recommender.popularity import PopularityRecommender  # noqa: E402

RESULTS_PATH = Path(__file__).resolve().parent / "results.json"
K = 10
TEST_FRACTION = 0.2
MIN_USER_EVENTS = 5

METHOD_LABELS = {
    "random": "Random (baseline)",
    "popularity": "Popularity",
    "content": "Content-based",
    "collaborative": "Collaborative (item-item)",
    "svd": "Matrix factorisation (SVD)",
    "hybrid": "Hybrid",
    "hybrid_no_diversity": "Hybrid without diversity rule",
}


def time_split(events: pd.DataFrame, test_fraction: float = TEST_FRACTION) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Each user's latest events go to the test set."""
    events = events.sort_values(["user_id", "timestamp"]).reset_index(drop=True)
    position = events.groupby("user_id").cumcount()
    size = events.groupby("user_id")["user_id"].transform("size")
    n_test = np.ceil(size * test_fraction).astype(int)
    is_test = (size >= MIN_USER_EVENTS) & (position >= size - n_test)
    return events[~is_test].copy(), events[is_test].copy()


def precision_recall_hit(recommended: list[int], relevant: set[int], k: int = K) -> tuple[float, float, float]:
    hits = len(set(recommended[:k]) & relevant)
    precision = hits / k
    recall = hits / len(relevant) if relevant else 0.0
    return precision, recall, float(hits > 0)


def evaluate(db=None, k: int = K, save: bool = True) -> dict:
    db = db or default_engine
    started = time.time()
    catalog = Catalog(load_products(db))
    events = load_events(db)
    train, test = time_split(events)

    # Train every model on the training data only
    matrix, _ = build_interaction_matrix(train, catalog)
    popularity = PopularityRecommender().fit(train, catalog, now=train["timestamp"].max())
    content = ContentBasedRecommender().fit(catalog)
    item_cf = ItemCFRecommender().fit(matrix, catalog)
    svd = SVDRecommender().fit(matrix, catalog)
    hybrid = HybridRecommender(popularity, content, item_cf, svd)
    # Ablation: same hybrid without the "max 3 per category" rule, to show its cost/benefit
    hybrid_no_div = HybridRecommender(popularity, content, item_cf, svd, max_per_category=k)
    rng = np.random.default_rng(0)

    def rank(scores: np.ndarray, seen: set[int]) -> list[int]:
        return top_indices(scores, k, seen)

    # Each method: (history, seen items) -> list of catalog indices
    methods: dict[str, Callable[[UserHistory, set[int]], list[int]]] = {
        "random": lambda h, seen: [int(i) for i in rng.permutation(len(catalog)) if i not in seen][:k],
        "popularity": lambda h, seen: rank(popularity.score_user(h), seen),
        "content": lambda h, seen: rank(content.score_user(h)[0], seen),
        "collaborative": lambda h, seen: rank(item_cf.score_user(h)[0], seen),
        # SVD scores can be negative, so shift them above zero before ranking
        "svd": lambda h, seen: rank(minmax(svd.score_user(h)) + 1e-9, seen),
        # Stock is a "today" rule, so it is switched off when replaying the past.
        "hybrid": lambda h, seen: [
            catalog.index[r.product_id] for r in hybrid.recommend(h, n=k, exclude=seen, apply_stock_filter=False)
        ],
        "hybrid_no_diversity": lambda h, seen: [
            catalog.index[r.product_id]
            for r in hybrid_no_div.recommend(h, n=k, exclude=seen, apply_stock_filter=False)
        ],
    }

    # Relevant items per user = new products with positive feedback in the test period
    test = test.assign(w=event_weights(test))
    train_by_user = dict(tuple(train.groupby("user_id")))
    per_method = {m: {"precision": [], "recall": [], "hit": [], "items": set()} for m in methods}
    n_users = 0
    for user_id, user_test in test.groupby("user_id"):
        user_train = train_by_user.get(user_id, pd.DataFrame(columns=train.columns))
        history = build_history(user_train, catalog)
        seen = history.seen
        positive = user_test.groupby("product_id")["w"].sum()
        relevant = {catalog.index[p] for p in positive[positive > 0].index if p in catalog.index} - seen
        if not relevant:
            continue
        n_users += 1
        for name, recommend in methods.items():
            recs = recommend(history, seen)
            p, r, h = precision_recall_hit(recs, relevant, k)
            per_method[name]["precision"].append(p)
            per_method[name]["recall"].append(r)
            per_method[name]["hit"].append(h)
            per_method[name]["items"].update(recs)

    results = []
    for name, values in per_method.items():
        results.append(
            {
                "method": name,
                "label": METHOD_LABELS[name],
                f"precision_at_{k}": round(float(np.mean(values["precision"])), 4),
                f"recall_at_{k}": round(float(np.mean(values["recall"])), 4),
                f"hit_rate_at_{k}": round(float(np.mean(values["hit"])), 4),
                "coverage": round(len(values["items"]) / len(catalog), 4),
            }
        )

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "k": k,
        "split": f"time-based, latest {int(TEST_FRACTION * 100)}% of each user's events (users with >= {MIN_USER_EVENTS} events)",
        "n_train_events": int(len(train)),
        "n_test_events": int(len(test)),
        "n_test_users": n_users,
        "n_products": len(catalog),
        "runtime_seconds": round(time.time() - started, 2),
        "results": results,
    }
    if save:
        RESULTS_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
    return output


def print_table(output: dict) -> None:
    k = output["k"]
    print(f"\nTest users: {output['n_test_users']}  |  train events: {output['n_train_events']}  "
          f"|  test events: {output['n_test_events']}")
    print(f"{'Method':30} {'P@' + str(k):>8} {'R@' + str(k):>8} {'HR@' + str(k):>8} {'Coverage':>9}")
    for r in output["results"]:
        print(f"{r['label']:30} {r[f'precision_at_{k}']:8.4f} {r[f'recall_at_{k}']:8.4f} "
              f"{r[f'hit_rate_at_{k}']:8.4f} {r['coverage']:9.2%}")


if __name__ == "__main__":
    result = evaluate()
    print_table(result)
    print(f"\nSaved to {RESULTS_PATH} ({result['runtime_seconds']}s)")
