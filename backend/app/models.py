"""Database tables (SQLAlchemy ORM models)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(60), index=True)
    brand: Mapped[str] = mapped_column(String(60))
    price: Mapped[float] = mapped_column(Float)
    description: Mapped[str] = mapped_column(Text)
    tags: Mapped[str] = mapped_column(String(300))  # comma separated, e.g. "bluetooth,audio"
    stock: Mapped[int] = mapped_column(Integer)
    image_url: Mapped[str] = mapped_column(String(300))


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    # The next two fields only describe the synthetic "persona" for the demo.
    # The recommenders never read them: they learn only from events.
    persona: Mapped[str] = mapped_column(String(200), default="")
    price_band: Mapped[str] = mapped_column(String(20), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    # view | click | add_to_cart | purchase | rating
    event_type: Mapped[str] = mapped_column(String(20), index=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_id: Mapped[str] = mapped_column(String(40), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)


class AppSetting(Base):
    """Key/value settings, e.g. the admin's recommendation rules (JSON in `value`).
    Read and written by recommender/settings.py."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
