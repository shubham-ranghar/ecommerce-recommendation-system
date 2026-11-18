"""Unit tests for each recommender, using the tiny shop from conftest.py."""
from __future__ import annotations

import numpy as np
import pandas as pd

from evaluation.evaluate import precision_recall_hit, time_split
from recommender.base import Catalog, build_history, build_interaction_matrix, event_weights
from recommender.collaborative import FrequentlyBoughtTogether, ItemCFRecommender, SVDRecommender
from recommender.content_based import ContentBasedRecommender
from recommender.hybrid import HybridRecommender
from recommender.popularity import PopularityRecommender
from recommender.settings import RecommenderSettings
from tests.conftest import NOW, make_events


def fit_all(events: pd.DataFrame, catalog: Catalog) -> HybridRecommender:
    matrix, _ = build_interaction_matrix(events, catalog)
    return HybridRecommender(
        PopularityRecommender().fit(events, catalog, now=NOW),
        ContentBasedRecommender().fit(catalog),
        ItemCFRecommender(k_neighbours=5).fit(matrix, catalog),
        SVDRecommender(n_components=4).fit(matrix, catalog),
    )


def test_event_weights_follow_the_spec() -> None:
    ev = make_events([(1, 1, "view", 0), (1, 1, "click", 0), (1, 1, "add_to_cart", 0), (1, 1, "purchase", 0)])
    assert event_weights(ev).tolist() == [1.0, 2.0, 3.0, 5.0]


def test_popularity_prefers_recent_events(events: pd.DataFrame, catalog: Catalog) -> None:
    pop = PopularityRecommender(half_life_days=14).fit(events, catalog, now=NOW)
    # Product 9 had 4 purchases (weight 20) 120 days ago, product 10 had 4 views (weight 4) yesterday.
    assert pop.scores[catalog.index[10]] > pop.scores[catalog.index[9]]
    top_ids = [r.product_id for r in pop.top(20)]
    assert 5 not in top_ids  # out of stock is never shown
    assert all(r.reason for r in pop.top(5))


def test_content_based_finds_same_kind_of_product(catalog: Catalog) -> None:
    content = ContentBasedRecommender().fit(catalog)
    similar = content.similar(1, n=3)
    assert similar[0].product_id == 2  # another smartphone with the same tags
    assert "Similar features" in similar[0].reason
    assert 1 not in [r.product_id for r in similar]  # never recommend the product itself


def test_item_cf_learns_co_interactions(events: pd.DataFrame, catalog: Catalog) -> None:
    matrix, users = build_interaction_matrix(events, catalog)
    assert matrix.shape == (len(users), len(catalog))
    cf = ItemCFRecommender(k_neighbours=5).fit(matrix, catalog)
    also = [r.product_id for r in cf.also_liked(6, n=3)]
    assert also[0] == 7  # readers of the mystery novel also liked the fantasy novel
    assert "liked both" in cf.also_liked(6, n=1)[0].reason


def test_frequently_bought_together(events: pd.DataFrame, catalog: Catalog) -> None:
    fbt = FrequentlyBoughtTogether().fit(events, catalog)
    recs = fbt.recommend([1], n=3)
    assert recs[0].product_id == 3  # phone -> phone case
    assert "Bought together" in recs[0].reason


def test_hybrid_applies_business_rules(events: pd.DataFrame, catalog: Catalog) -> None:
    hybrid = fit_all(events, catalog)
    # A phone buyer (user 1)
    history = build_history(events[events["user_id"] == 1], catalog)
    recs = hybrid.recommend(history, n=10)
    ids = [r.product_id for r in recs]
    assert 1 not in ids and 3 not in ids  # already bought
    assert 5 not in ids  # out of stock
    categories = [catalog.categories[catalog.index[p]] for p in ids]
    assert max(categories.count(c) for c in set(categories)) <= 3  # diversity rule
    assert all(r.reason for r in recs)


def test_hybrid_personalises(events: pd.DataFrame, catalog: Catalog) -> None:
    hybrid = fit_all(events, catalog)
    # A new user who only viewed the mystery novel should get the fantasy novel first
    history = build_history(make_events([(99, 6, "view", 0), (99, 6, "click", 0)]), catalog)
    recs = hybrid.recommend(history, n=5)
    assert recs[0].product_id == 7


def test_time_split_puts_latest_events_in_test() -> None:
    ev = make_events([(1, p, "view", 10 - p) for p in range(1, 11)])  # product 10 is the newest
    train, test = time_split(ev, test_fraction=0.2)
    assert len(test) == 2 and len(train) == 8
    assert test["timestamp"].min() > train["timestamp"].max()


def test_metrics() -> None:
    p, r, h = precision_recall_hit([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], {3, 42}, k=10)
    assert np.isclose(p, 0.1) and np.isclose(r, 0.5) and h == 1.0
    assert precision_recall_hit([1, 2], {9}, k=10) == (0.0, 0.0, 0.0)


def test_hybrid_can_keep_purchased_items(events: pd.DataFrame, catalog: Catalog) -> None:
    """Admin switch: with hide_purchased off, a repeat-buy item may come back."""
    hybrid = fit_all(events, catalog)
    hybrid.exclude_purchased = False
    history = build_history(events[events["user_id"] == 1], catalog)
    ids = [r.product_id for r in hybrid.recommend(history, n=10)]
    assert 1 in ids or 3 in ids


def test_settings_round_trip_and_fill_missing_weights() -> None:
    settings = RecommenderSettings(max_per_category=2, hide_purchased=False)
    assert RecommenderSettings.from_dict(settings.to_dict()) == settings
    # An older saved row with a missing weight and an unknown key still loads.
    loaded = RecommenderSettings.from_dict({"weights": {"content": 0.9}, "unknown": 1})
    assert loaded.weights["content"] == 0.9 and set(loaded.weights) == set(RecommenderSettings().weights)
    assert loaded.hybrid_kwargs()["exclude_purchased"] is True

