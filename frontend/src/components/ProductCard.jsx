import { useNavigate } from "react-router-dom";
import { formatPrice, imageUrl } from "../api";
import { useApp } from "../store";

// Colour + icon for each recommendation method, so the audience can see which algorithm produced an item.
export const METHOD_STYLES = {
  popularity: { label: "Popularity", icon: "🔥", chip: "bg-amber-50 text-amber-800 ring-amber-200" },
  content: { label: "Content-based", icon: "🧬", chip: "bg-violet-50 text-violet-800 ring-violet-200" },
  collaborative: { label: "Collaborative", icon: "👥", chip: "bg-sky-50 text-sky-800 ring-sky-200" },
  svd: { label: "Matrix factorisation", icon: "🧮", chip: "bg-teal-50 text-teal-800 ring-teal-200" },
  user_cf: { label: "Shoppers like you", icon: "🤝", chip: "bg-sky-50 text-sky-800 ring-sky-200" },
  bought_together: { label: "Bought together", icon: "🛒", chip: "bg-pink-50 text-pink-800 ring-pink-200" },
  also_bought: { label: "Also bought", icon: "🧾", chip: "bg-sky-50 text-sky-800 ring-sky-200" },
  hybrid: { label: "Hybrid", icon: "⚡", chip: "bg-emerald-50 text-emerald-800 ring-emerald-200" },
  history: { label: "Your history", icon: "🕘", chip: "bg-slate-100 text-slate-700 ring-slate-300" },
};

export function methodStyle(method = "") {
  // Hybrid items are tagged "hybrid:<dominant method>"
  const base = method.split(":").pop();
  return METHOD_STYLES[base] || METHOD_STYLES.hybrid;
}

export function Stars({ value, count }) {
  if (!value) return <span className="text-xs text-muted">No ratings yet</span>;
  return (
    <span className="flex items-center gap-1 text-xs text-muted">
      <span className="text-ink">{"★".repeat(Math.round(value))}</span>
      <span className="text-line">{"★".repeat(5 - Math.round(value))}</span>
      {value.toFixed(1)} ({count})
    </span>
  );
}

/**
 * Product tile. When `reason` is given it is shown under the product (every recommendation has one).
 * Clicking a recommended product logs a "click" event before opening it.
 */
export default function ProductCard({ product, reason, method, action }) {
  const navigate = useNavigate();
  const { track } = useApp();
  const style = methodStyle(method);
  // The API sends in_stock (e.g. sold-out items in "Recently viewed"); fall back to stock for older data.
  const outOfStock = product.in_stock === undefined ? product.stock <= 0 : !product.in_stock;

  const open = () => {
    if (reason) track("click", product.id).catch(() => {});
    navigate(`/product/${product.id}`);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <div className="group flex h-full flex-col overflow-hidden rounded-xl border border-line bg-surface transition-colors hover:border-muted/40">
      {/* Square #EFEFEF tile: multiply blends white photo backgrounds into the tile */}
      <button onClick={open} className="relative block aspect-square overflow-hidden bg-[#EFEFEF] p-5 text-left">
        {outOfStock && (
          <span className="absolute left-2 top-2 z-10 rounded-full bg-ink px-2 py-0.5 text-[11px] font-medium text-white">
            Out of stock
          </span>
        )}
        <img
          src={imageUrl(product)}
          alt={product.name}
          loading="lazy"
          className={`h-full w-full object-contain mix-blend-multiply transition duration-300 group-hover:scale-[1.03] ${outOfStock ? "opacity-50" : ""}`}
        />
      </button>
      <div className="flex flex-1 flex-col gap-1.5 p-4">
        <span className="text-xs text-muted">{product.category}</span>
        <button onClick={open} className="line-clamp-2 text-left text-sm leading-snug text-ink hover:underline">
          {product.name}
        </button>
        <Stars value={product.rating_avg} count={product.rating_count} />
        <div className="mt-auto flex items-center justify-between gap-2 pt-2">
          <span className="text-sm font-medium text-ink">{formatPrice(product.price)}</span>
          {!outOfStock && action /* sold out: the image badge says so, and there is no add-to-cart button */}
        </div>
        {reason && (
          <p className="mt-2 self-start rounded-lg bg-chip px-2 py-1 text-xs leading-snug text-chip-ink" title={style.label}>
            {reason}
          </p>
        )}
      </div>
    </div>
  );
}
