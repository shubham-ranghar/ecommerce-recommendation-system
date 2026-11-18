"""Recommendation rules that a shop admin can change at runtime (Admin page).

The settings are stored as one JSON row in the `app_settings` table, so they
survive restarts. Regenerating the data (python -m data.generate_data) resets them.
Changing them does not need a retrain: only the hybrid ranker is rebuilt.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields

from sqlalchemy import Engine, text

from recommender.hybrid import DEFAULT_WEIGHTS

SETTINGS_KEY = "recommender"


@dataclass
class RecommenderSettings:
    # Hybrid blend: how much each method counts in "Recommended for you".
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    # Business rules of the hybrid.
    max_per_category: int = 3
    price_penalty: float = 0.3
    hide_out_of_stock: bool = True
    hide_purchased: bool = True
    # Context: how many interactions before a visitor counts as "returning".
    min_events_for_personalisation: int = 3
    # Which extra rows the home page shows.
    show_recently_viewed: bool = True
    show_purchase_based: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RecommenderSettings":
        known = {f.name for f in fields(cls)}
        values = {k: v for k, v in data.items() if k in known}
        settings = cls(**values)
        # Keep every method present, even if an older saved row lacks one.
        settings.weights = {**DEFAULT_WEIGHTS, **{k: float(v) for k, v in settings.weights.items() if k in DEFAULT_WEIGHTS}}
        return settings

    def hybrid_kwargs(self) -> dict:
        """Keyword arguments for HybridRecommender."""
        return {
            "weights": dict(self.weights),
            "max_per_category": self.max_per_category,
            "price_penalty": self.price_penalty,
            "exclude_purchased": self.hide_purchased,
        }


def _ensure_table(db: Engine) -> None:
    with db.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"))


def load_settings(db: Engine) -> RecommenderSettings:
    _ensure_table(db)
    with db.connect() as conn:
        row = conn.execute(text("SELECT value FROM app_settings WHERE key = :k"), {"k": SETTINGS_KEY}).first()
    if row is None:
        return RecommenderSettings()
    try:
        return RecommenderSettings.from_dict(json.loads(row[0]))
    except (ValueError, TypeError):  # corrupt row -> fall back to defaults
        return RecommenderSettings()


def save_settings(db: Engine, settings: RecommenderSettings) -> None:
    _ensure_table(db)
    with db.begin() as conn:
        conn.execute(
            text("INSERT INTO app_settings (key, value) VALUES (:k, :v) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value"),
            {"k": SETTINGS_KEY, "v": json.dumps(settings.to_dict())},
        )
