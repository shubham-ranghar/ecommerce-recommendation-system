"""Unit tests for each recommender, using the tiny shop from conftest.py."""
from __future__ import annotations

import numpy as np
import pandas as pd

from evaluation.evaluate import precision_recall_hit, time_split
from recommender.base import Catalog, build_history, build_interaction_matrix, event_weights
from recommender.collaborative import (
    AlsoBoughtRecommender,
    FrequentlyBoughtTogether,
    ItemCFRecommender,
    SVDRecommender,
    UserCFRecommender,
)
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


def test_bought_together_needs_two_shared_baskets(events: pd.DataFrame, catalog: Catalog) -> None:
    # One extra basket where the cookbook (8) and the yoga mat (9) are bought together once
    once = make_events([(50, 8, "purchase", 1), (50, 9, "purchase", 1)])
    data = pd.concat([events, once], ignore_index=True)
    assert 9 not in [r.product_id for r in FrequentlyBoughtTogether().fit(data, catalog).recommend([8])]
    assert 9 in [r.product_id for r in FrequentlyBoughtTogether(min_count=1).fit(data, catalog).recommend([8])]
    assert [r.product_id for r in FrequentlyBoughtTogether().fit(data, catalog).recommend([1])][0] == 3  # 4 baskets


def test_also_bought_uses_purchases_only(events: pd.DataFrame, catalog: Catalog) -> None:
    purchases = events[events["event_type"] == "purchase"]
    also_bought = AlsoBoughtRecommender().fit(build_interaction_matrix(purchases, catalog)[0], catalog)
    ids = [r.product_id for r in also_bought.also_bought(1)]
    assert ids == [3]  # users 1-4 bought phone + case; headphones (4) were only viewed/clicked
    assert also_bought.also_bought(1)[0].reason == "4 shoppers bought both"
    item_cf = ItemCFRecommender().fit(build_interaction_matrix(events, catalog)[0], catalog)
    assert 4 in [r.product_id for r in item_cf.also_liked(1)]  # "also liked" still uses all interactions


def test_user_cf_scores_what_similar_shoppers_bought(events: pd.DataFrame, catalog: Catalog) -> None:
    user_cf = UserCFRecommender(k_neighbours=30).fit(events, catalog)
    _, user_ids = build_interaction_matrix(events, catalog)
    shopper = build_history(make_events([(99, 1, "purchase", 0)]), catalog)  # new shopper bought a phone
    top, sims = user_cf.neighbours(shopper)
    assert {user_ids[i] for i in top} == {1, 2, 3, 4} and np.all(sims > 0)  # the other phone buyers
    scores = user_cf.score_user(shopper)
    assert scores[catalog.index[3]] > 0  # case: bought by the similar shoppers
    assert scores[catalog.index[4]] == 0  # headphones: only viewed by them, never bought
    assert scores[catalog.index[6]] == 0  # novel: bought by book readers, who are not similar


def test_user_cf_keeps_k_neighbours_and_skips_the_shopper_itself(events: pd.DataFrame, catalog: Catalog) -> None:
    user_cf = UserCFRecommender(k_neighbours=2).fit(events, catalog)
    _, user_ids = build_interaction_matrix(events, catalog)
    own = build_history(events[events["user_id"] == 1], catalog)  # user 1 is also in the training matrix
    top, _ = user_cf.neighbours(own)
    assert len(top) == 2 and 1 not in {user_ids[i] for i in top}
    empty = build_history(pd.DataFrame(), catalog)
    assert not user_cf.score_user(empty).any()


def test_hybrid_uses_user_cf_weight_and_reason(events: pd.DataFrame, catalog: Catalog) -> None:
    base = fit_all(events, catalog)
    user_cf = UserCFRecommender().fit(events, catalog)
    shopper = build_history(make_events([(99, 1, "purchase", 0)]), catalog)
    only_user_cf = {"collaborative": 0, "svd": 0, "content": 0, "popularity": 0, "user_cf": 1.0}
    hybrid = HybridRecommender(base.popularity, base.content, base.item_cf, base.svd,
                               weights=only_user_cf, user_cf=user_cf)
    top = hybrid.recommend(shopper, n=3)[0]
    assert top.product_id == 3 and top.reason == "Shoppers like you bought this" and top.method == "hybrid:user_cf"

    # Weight 0 -> exactly the same list as a hybrid without user-user CF
    weights = {**hybrid.weights, "collaborative": 0.35, "svd": 0.2, "content": 0.25, "popularity": 0.2, "user_cf": 0.0}
    with_zero = HybridRecommender(base.popularity, base.content, base.item_cf, base.svd, weights=weights, user_cf=user_cf)
    without = HybridRecommender(base.popularity, base.content, base.item_cf, base.svd, weights=weights)
    assert [r.product_id for r in with_zero.recommend(shopper)] == [r.product_id for r in without.recommend(shopper)]
