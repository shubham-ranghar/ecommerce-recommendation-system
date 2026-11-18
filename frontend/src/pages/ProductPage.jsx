import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, formatPrice, imageUrl } from "../api";
import { Stars } from "../components/ProductCard";
import RecommendationRow, { Spinner } from "../components/RecommendationRow";
import { useApp } from "../store";

export default function ProductPage() {
  const { id } = useParams();
  const productId = Number(id);
  const { user, track, addToCart, cart } = useApp();
  const [product, setProduct] = useState(null);
  const [similar, setSimilar] = useState(null);
  const [alsoLiked, setAlsoLiked] = useState(null);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState("");
  const [myRating, setMyRating] = useState(0);
  const lastViewLogged = useRef("");

  useEffect(() => {
    setProduct(null);
    setSimilar(null);
    setAlsoLiked(null);
    setMessage("");
    setMyRating(0);
    api.product(productId).then(setProduct).catch((e) => setError(e.message));
    api.similar(productId).then(setSimilar).catch(() => setSimilar([]));
    api.alsoLiked(productId).then(setAlsoLiked).catch(() => setAlsoLiked([]));
  }, [productId]);

  // COLLECT: log one "view" event per product page visit
  useEffect(() => {
    const key = `${user?.id}-${productId}`;
    if (user && lastViewLogged.current !== key) {
      lastViewLogged.current = key;
      track("view", productId).catch(() => {});
    }
  }, [user, productId, track]);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!product) return <Spinner />;

  const inCart = cart.some((p) => p.id === product.id);
  const outOfStock = product.stock <= 0;

  const rate = async (stars) => {
    setMyRating(stars);
    await track("rating", product.id, stars);
    setMessage(`Thanks! You rated this ${stars} star${stars > 1 ? "s" : ""}.`);
  };

  return (
    <div>
      <nav className="mb-4 text-sm text-slate-500">
        <Link to="/" className="hover:text-indigo-600">Home</Link> / <span>{product.category}</span> /{" "}
        <span className="text-slate-700">{product.name}</span>
      </nav>

      <div className="card grid gap-8 overflow-hidden p-4 md:grid-cols-2 md:p-6">
        <img src={imageUrl(product)} alt={product.name} className="aspect-[4/3] w-full rounded-xl object-cover" />
        <div className="flex flex-col">
          <span className="text-xs font-semibold uppercase tracking-wide text-indigo-600">
            {product.category} · {product.brand}
          </span>
          <h1 className="mt-1 text-2xl font-extrabold text-slate-900 sm:text-3xl">{product.name}</h1>
          <div className="mt-2"><Stars value={product.rating_avg} count={product.rating_count} /></div>
          <p className="mt-4 text-3xl font-bold text-slate-900">{formatPrice(product.price)}</p>
          <p className={`mt-1 text-sm font-medium ${outOfStock ? "text-red-600" : "text-emerald-600"}`}>
            {outOfStock ? "Out of stock" : `In stock (${product.stock} left)`}
          </p>
          <p className="mt-4 text-sm leading-relaxed text-slate-600">{product.description}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {product.tags.map((t) => (
              <span key={t} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">#{t}</span>
            ))}
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <button
              className="btn-primary"
              disabled={outOfStock || inCart}
              onClick={async () => {
                await addToCart(product);
                setMessage("Added to your cart. Open the cart to see Frequently bought together.");
              }}
            >
              {inCart ? "✓ In your cart" : "🛒 Add to cart"}
            </button>
            {inCart && <Link to="/cart" className="btn-secondary">Go to cart →</Link>}
          </div>

          <div className="mt-6 flex items-center gap-3 border-t border-slate-100 pt-4 text-sm">
            <span className="text-slate-500">Rate this product:</span>
            <div className="flex">
              {[1, 2, 3, 4, 5].map((s) => (
                <button
                  key={s}
                  onClick={() => rate(s)}
                  aria-label={`${s} stars`}
                  className={`text-2xl leading-none transition hover:scale-110 ${s <= myRating ? "text-amber-400" : "text-slate-300"}`}
                >
                  ★
                </button>
              ))}
            </div>
          </div>
          {message && <p className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{message}</p>}
        </div>
      </div>

      <RecommendationRow
        title="Similar products"
        subtitle="Products with similar descriptions and tags (TF-IDF + cosine similarity)"
        method="content"
        items={similar?.slice(0, 5)}
        loading={!similar}
      />
      <RecommendationRow
        title="Customers who liked this also liked"
        subtitle="Learned from what other shoppers did (item-item collaborative filtering)"
        method="collaborative"
        items={alsoLiked?.slice(0, 5)}
        loading={!alsoLiked}
      />
    </div>
  );
}
