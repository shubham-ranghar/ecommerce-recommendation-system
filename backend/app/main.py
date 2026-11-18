"""FastAPI app: product catalogue, event logging and recommendation endpoints.

Run from the backend folder:
    uvicorn app.main:app --reload
Interactive API docs: http://localhost:8000/docs
"""
from __future__ import annotations

import hmac
import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import func, inspect, or_, select
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.images import media_type, product_photo, product_svg
from app.models import Event, Product, User
from app.schemas import (
    AdminSettingsOut,
    AdminStatsOut,
    EventIn,
    EventOut,
    HomeOut,
    ProductOut,
    ProductPage,
    RecommendationOut,
    RecommenderSettingsModel,
    UserOut,
)
from evaluation.evaluate import RESULTS_PATH, evaluate
from recommender.base import Recommendation
from recommender.engine import RecommendationEngine
from recommender.settings import RecommenderSettings

recommender = RecommendationEngine(engine)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """On startup: create the database if it is missing, then train the models."""
    if not inspect(engine).has_table("products"):
        from data.generate_data import main as generate

        print("No database found - generating synthetic data ...")
        generate()
    Base.metadata.create_all(engine)
    recommender.fit()
    print(f"Recommender ready: {len(recommender.catalog)} products, {recommender.n_events} events")
    yield


app = FastAPI(title="ShopSmart Recommendation API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],  # includes PUT for the admin settings
    allow_headers=["*"],
)


# ---------- helpers ----------
def rating_stats(db: Session, product_ids: list[int]) -> dict[int, tuple[float, int]]:
    """Average rating and number of ratings for a list of products."""
    rows = db.execute(
        select(Event.product_id, func.avg(Event.rating), func.count(Event.id))
        .where(Event.event_type == "rating", Event.product_id.in_(product_ids))
        .group_by(Event.product_id)
    ).all()
    return {pid: (round(float(avg), 1), int(n)) for pid, avg, n in rows}


def to_product_out(p: Product, stats: dict[int, tuple[float, int]]) -> ProductOut:
    avg, count = stats.get(p.id, (None, 0))
    return ProductOut(
        id=p.id, name=p.name, category=p.category, brand=p.brand, price=p.price,
        description=p.description, tags=[t for t in p.tags.split(",") if t], stock=p.stock,
        in_stock=p.stock > 0, image_url=p.image_url, rating_avg=avg, rating_count=count,
    )


def to_recommendations(db: Session, recs: list[Recommendation]) -> list[RecommendationOut]:
    """Attach full (fresh) product data to recommendation results."""
    ids = [r.product_id for r in recs]
    products = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(ids)))}
    stats = rating_stats(db, ids)
    return [
        RecommendationOut(product=to_product_out(products[r.product_id], stats), score=round(r.score, 4),
                          reason=r.reason, method=r.method)
        for r in recs
        if r.product_id in products
    ]


def get_product_or_404(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return product


def check_user(db: Session, user_id: int | None) -> None:
    if user_id is not None and db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")


# ---------- catalogue ----------
@app.get("/")
def root() -> dict:
    return {"message": "ShopSmart Recommendation API", "docs": "/docs"}


@app.get("/products", response_model=ProductPage)
def list_products(
    category: str | None = None,
    q: str | None = Query(default=None, description="Search in name, brand and tags"),
    limit: int = Query(default=24, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ProductPage:
    query = select(Product)
    if category:
        query = query.where(Product.category == category)
    if q:
        like = f"%{q}%"
        query = query.where(or_(Product.name.ilike(like), Product.brand.ilike(like), Product.tags.ilike(like)))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    products = db.scalars(query.order_by(Product.id).offset(offset).limit(limit)).all()
    stats = rating_stats(db, [p.id for p in products])
    return ProductPage(total=total, items=[to_product_out(p, stats) for p in products])


@app.get("/categories")
def list_categories(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(select(Product.category, func.count()).group_by(Product.category)).all()
    return [{"name": c, "count": n} for c, n in rows]


@app.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)) -> ProductOut:
    product = get_product_or_404(db, product_id)
    return to_product_out(product, rating_stats(db, [product_id]))


# The ".svg" path is what databases generated before the photo change store; it serves the same image.
# Decorators register bottom-up, so the ".svg" route must be the lower one to be matched first.
@app.get("/images/{product_id}")
@app.get("/images/{product_id}.svg", include_in_schema=False)
def product_image(product_id: int, db: Session = Depends(get_db)) -> Response:
    """The type's photo (manual drop-in first, then DummyJSON), or a line-icon tile when there is none."""
    product = get_product_or_404(db, product_id)
    # no-cache: browsers revalidate, so a photo dropped into data/images/manual/ shows up on reload.
    cache = {"Cache-Control": "no-cache"}
    photo = product_photo(product.name, product.category)
    if photo is not None:
        return FileResponse(photo, media_type=media_type(photo), headers=cache)
    svg = product_svg(product.name, product.category, product.brand)
    return Response(content=svg, media_type="image/svg+xml", headers=cache)


# ---------- users ----------
@app.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)) -> list[UserOut]:
    """Demo users for the user selector."""
    counts = dict(db.execute(select(Event.user_id, func.count()).group_by(Event.user_id)).all())
    users = db.scalars(select(User).where(User.is_demo.is_(True)).order_by(User.id)).all()
    return [
        UserOut(id=u.id, name=u.name, is_demo=u.is_demo, persona=u.persona, price_band=u.price_band,
                n_events=counts.get(u.id, 0))
        for u in users
    ]


@app.post("/users", response_model=UserOut, status_code=201)
def create_visitor(db: Session = Depends(get_db)) -> UserOut:
    """Create a fresh 'new visitor' so the cold-start behaviour can be shown live."""
    # The database assigns the id (safe when several visitors arrive at the same time).
    user = User(name="New visitor", is_demo=False, persona="No history yet",
                price_band="", created_at=datetime.now(timezone.utc).replace(tzinfo=None))
    db.add(user)
    db.flush()
    user.name = f"New visitor #{user.id}"
    db.commit()
    return UserOut(id=user.id, name=user.name, is_demo=False, persona=user.persona, price_band="")


@app.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    n = db.scalar(select(func.count()).where(Event.user_id == user_id)) or 0
    return UserOut(id=user.id, name=user.name, is_demo=user.is_demo, persona=user.persona,
                   price_band=user.price_band, n_events=n)


# ---------- events (COLLECT) ----------
@app.post("/events", response_model=EventOut, status_code=201)
def log_event(event: EventIn, db: Session = Depends(get_db)) -> EventOut:
    check_user(db, event.user_id)
    product = get_product_or_404(db, event.product_id)
    if event.event_type == "rating" and event.rating is None:
        raise HTTPException(status_code=422, detail="A rating event needs a rating between 1 and 5")
    if event.event_type == "purchase":
        if product.stock <= 0:
            raise HTTPException(status_code=409, detail=f"{product.name} is out of stock")
        product.stock -= 1
    row = Event(
        user_id=event.user_id, product_id=event.product_id, event_type=event.event_type,
        rating=event.rating if event.event_type == "rating" else None,
        session_id=event.session_id or f"web-{event.user_id}",
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(row)
    db.commit()
    recommender.mark_dirty()  # models will be retrained with the new event
    return EventOut(id=row.id)


# ---------- recommendations ----------
@app.get("/recommend/home", response_model=HomeOut)
def recommend_home(user_id: int | None = None, n: int = Query(default=10, ge=1, le=30),
                   db: Session = Depends(get_db)) -> HomeOut:
    check_user(db, user_id)
    result = recommender.home(user_id, n=n)
    for section in result["sections"]:
        section["items"] = to_recommendations(db, section["items"])
    return HomeOut(**result)


@app.get("/recommend/similar/{product_id}", response_model=list[RecommendationOut])
def recommend_similar(product_id: int, n: int = Query(default=8, ge=1, le=30),
                      db: Session = Depends(get_db)) -> list[RecommendationOut]:
    get_product_or_404(db, product_id)
    return to_recommendations(db, recommender.similar(product_id, n))


@app.get("/recommend/also-liked/{product_id}", response_model=list[RecommendationOut])
def recommend_also_liked(product_id: int, n: int = Query(default=8, ge=1, le=30),
                         db: Session = Depends(get_db)) -> list[RecommendationOut]:
    get_product_or_404(db, product_id)
    return to_recommendations(db, recommender.also_liked(product_id, n))


@app.get("/recommend/also-bought/{product_id}", response_model=list[RecommendationOut])
def recommend_also_bought(product_id: int, n: int = Query(default=8, ge=1, le=30),
                          db: Session = Depends(get_db)) -> list[RecommendationOut]:
    """Customers who bought this also bought: item-item CF on purchases only. Empty without data."""
    get_product_or_404(db, product_id)
    return to_recommendations(db, recommender.also_bought(product_id, n))


@app.get("/recommend/bought-together/{product_id}", response_model=list[RecommendationOut])
def recommend_bought_together(product_id: int, n: int = Query(default=6, ge=1, le=30),
                              db: Session = Depends(get_db)) -> list[RecommendationOut]:
    """Frequently bought together for one product (product page). Empty when there is no basket data."""
    get_product_or_404(db, product_id)
    return to_recommendations(db, recommender.bought_together(product_id, n))


@app.get("/recommend/cart", response_model=list[RecommendationOut])
def recommend_cart(
    user_id: int | None = None,
    product_ids: str | None = Query(default=None, description="Comma separated cart product ids"),
    n: int = Query(default=6, ge=1, le=30),
    db: Session = Depends(get_db),
) -> list[RecommendationOut]:
    """Frequently bought together. If product_ids is missing, the cart is rebuilt from
    the user's add_to_cart events that were not purchased afterwards."""
    check_user(db, user_id)
    if product_ids:
        try:
            cart = [int(x) for x in product_ids.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(status_code=422, detail="product_ids must be numbers, e.g. 1,2,3")
    elif user_id is not None:
        rows = db.execute(
            select(Event.product_id, Event.event_type).where(
                Event.user_id == user_id, Event.event_type.in_(["add_to_cart", "purchase"])
            ).order_by(Event.timestamp)
        ).all()
        in_cart: dict[int, bool] = {}
        for pid, etype in rows:
            in_cart[pid] = etype == "add_to_cart"
        cart = [pid for pid, open_ in in_cart.items() if open_]
    else:
        cart = []
    return to_recommendations(db, recommender.cart(user_id, cart, n))


# ---------- evaluation (MEASURE) ----------
@app.get("/evaluation")
def get_evaluation(refresh: bool = False) -> dict:
    """Saved evaluation results. Use ?refresh=true to re-run the evaluation (a few seconds)."""
    if refresh or not RESULTS_PATH.exists():
        return evaluate()
    return json.loads(RESULTS_PATH.read_text(encoding="utf-8"))


# ---------- admin: recommendation rules ----------
# Every /admin endpoint needs the header "X-Admin-Token: <ADMIN_TOKEN>".
# The token is read from the ADMIN_TOKEN environment variable on every request.
# If ADMIN_TOKEN is not set, admin is locked for everyone (fail closed).
ADMIN_TOKEN_HEADER = "X-Admin-Token"


def require_admin(x_admin_token: str | None = Header(default=None, alias=ADMIN_TOKEN_HEADER)) -> None:
    expected = os.environ.get("ADMIN_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=401, detail="Admin is locked: set ADMIN_TOKEN on the server")
    if not x_admin_token or not hmac.compare_digest(x_admin_token.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Missing or wrong admin token",
                            headers={"WWW-Authenticate": ADMIN_TOKEN_HEADER})


admin_router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def settings_out(settings: RecommenderSettings) -> RecommenderSettingsModel:
    return RecommenderSettingsModel(**settings.to_dict())


@admin_router.get("/settings", response_model=AdminSettingsOut)
def get_admin_settings() -> AdminSettingsOut:
    recommender.ensure_fresh()
    return AdminSettingsOut(current=settings_out(recommender.settings), defaults=settings_out(RecommenderSettings()))


@admin_router.put("/settings", response_model=AdminSettingsOut)
def put_admin_settings(body: RecommenderSettingsModel) -> AdminSettingsOut:
    """Save new weights and rules. They apply to the next recommendation request."""
    recommender.update_settings(RecommenderSettings.from_dict(body.model_dump()))
    return get_admin_settings()


@admin_router.post("/settings/reset", response_model=AdminSettingsOut)
def reset_admin_settings() -> AdminSettingsOut:
    recommender.update_settings(RecommenderSettings())
    return get_admin_settings()


@admin_router.post("/evaluate")
def evaluate_admin_settings() -> dict:
    """Score the saved admin settings against the defaults (a few seconds; not saved to results.json)."""
    recommender.ensure_fresh()
    return evaluate(save=False, settings=recommender.settings)


@admin_router.get("/stats", response_model=AdminStatsOut)
def admin_stats(db: Session = Depends(get_db)) -> AdminStatsOut:
    by_type = dict(db.execute(select(Event.event_type, func.count()).group_by(Event.event_type)).all())
    return AdminStatsOut(
        n_products=db.scalar(select(func.count()).select_from(Product)) or 0,
        n_out_of_stock=db.scalar(select(func.count()).where(Product.stock <= 0)) or 0,
        n_users=db.scalar(select(func.count()).select_from(User)) or 0,
        n_events=sum(by_type.values()),
        events_by_type=by_type,
    )


# Registered last, after every admin route above has been added to the router.
app.include_router(admin_router)
