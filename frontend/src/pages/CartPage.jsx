import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatPrice, imageUrl } from "../api";
import RecommendationRow from "../components/RecommendationRow";
import { useApp } from "../store";

export default function CartPage() {
  const { user, cart, addToCart, removeFromCart, checkout } = useApp();
  const [recs, setRecs] = useState(null);
  const [done, setDone] = useState(null);
  const [busy, setBusy] = useState(false);
  const cartKey = cart.map((p) => p.id).join(",");

  useEffect(() => {
    if (!user || !cart.length) return setRecs([]);
    setRecs(null);
    api.cart(user.id, cart.map((p) => p.id)).then(setRecs).catch(() => setRecs([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, cartKey]);

  const total = cart.reduce((sum, p) => sum + p.price, 0);

  const onCheckout = async () => {
    setBusy(true);
    const count = cart.length;
    const failed = await checkout();
    setBusy(false);
    setDone({ count, failed });
  };

  return (
    <div>
      <h1 className="text-2xl font-extrabold text-slate-900">Your cart</h1>

      {done && (
        <div className="mt-4 rounded-xl bg-emerald-50 p-4 text-sm text-emerald-800">
          🎉 Order placed! {done.count - done.failed.length} purchase event(s) were saved. Bought items will no longer be
          recommended to you.
          {done.failed.length > 0 && <span className="block text-red-600">Problems: {done.failed.join("; ")}</span>}
        </div>
      )}

      {cart.length === 0 ? (
        <div className="card mt-6 p-10 text-center">
          <p className="text-4xl">🛒</p>
          <p className="mt-2 text-slate-600">Your cart is empty.</p>
          <Link to="/" className="btn-primary mt-4">Continue shopping</Link>
        </div>
      ) : (
        <div className="mt-6 grid gap-6 lg:grid-cols-3">
          <ul className="card divide-y divide-slate-100 lg:col-span-2">
            {cart.map((p) => (
              <li key={p.id} className="flex items-center gap-4 p-4">
                <img src={imageUrl(p)} alt="" className="h-16 w-20 rounded-lg object-cover" />
                <div className="min-w-0 flex-1">
                  <Link to={`/product/${p.id}`} className="font-semibold text-slate-900 hover:text-indigo-700">{p.name}</Link>
                  <p className="text-xs text-slate-500">{p.category}</p>
                </div>
                <span className="font-semibold">{formatPrice(p.price)}</span>
                <button onClick={() => removeFromCart(p.id)} className="text-sm text-slate-400 hover:text-red-600" aria-label="Remove">
                  ✕
                </button>
              </li>
            ))}
          </ul>
          <div className="card h-fit p-5">
            <div className="flex justify-between text-sm text-slate-500"><span>Items</span><span>{cart.length}</span></div>
            <div className="mt-2 flex justify-between text-lg font-bold"><span>Total</span><span>{formatPrice(total)}</span></div>
            <button className="btn-primary mt-4 w-full" disabled={busy} onClick={onCheckout}>
              {busy ? "Placing order…" : "Checkout"}
            </button>
            <p className="mt-2 text-xs text-slate-400">Demo checkout: logs a purchase event for every item.</p>
          </div>
        </div>
      )}

      {cart.length > 0 && (
        <RecommendationRow
          title="Frequently bought together"
          subtitle="Products that other shoppers put in the same basket as your cart items"
          method="bought_together"
          items={recs?.slice(0, 5)}
          loading={!recs}
          renderAction={(product) =>
            cart.some((p) => p.id === product.id) ? (
              <span className="text-xs font-semibold text-emerald-600">✓ Added</span>
            ) : (
              <button
                onClick={() => addToCart(product)}
                className="rounded-lg bg-indigo-50 px-2 py-1 text-xs font-semibold text-indigo-700 hover:bg-indigo-100"
              >
                + Add
              </button>
            )
          }
        />
      )}
    </div>
  );
}
