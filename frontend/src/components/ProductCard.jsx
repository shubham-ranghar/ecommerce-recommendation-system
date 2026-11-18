import { useNavigate } from "react-router-dom";
import { formatPrice, imageUrl } from "../api";
import { useApp } from "../store";

// Colour + icon for each recommendation method, so the audience can see which algorithm produced an item.
export const METHOD_STYLES = {
  popularity: { label: "Popularity", icon: "🔥", chip: "bg-amber-50 text-amber-800 ring-amber-200" },
  content: { label: "Content-based", icon: "🧬", chip: "bg-violet-50 text-violet-800 ring-violet-200" },
  collaborative: { label: "Collaborative", icon: "👥", chip: "bg-sky-50 text-sky-800 ring-sky-200" },
  svd: { label: "Matrix factorisation", icon: "🧮", chip: "bg-teal-50 text-teal-800 ring-teal-200" },
  bought_together: { label: "Bought together", icon: "🛒", chip: "bg-pink-50 text-pink-800 ring-pink-200" },
  hybrid: { label: "Hybrid", icon: "⚡", chip: "bg-emerald-50 text-emerald-800 ring-emerald-200" },
};

export function methodStyle(method = "") {
  // Hybrid items are tagged "hybrid:<dominant method>"
  const base = method.split(":").pop();
  return METHOD_STYLES[base] || METHOD_STYLES.hybrid;
}

export function Stars({ value, count }) {
  if (!value) return <span className="text-xs text-slate-400">No ratings yet</span>;
  return (
    <span className="flex items-center gap-1 text-xs text-slate-500">
      <span className="text-amber-400">{"★".repeat(Math.round(value))}</span>
      <span className="text-slate-300">{"★".repeat(5 - Math.round(value))}</span>
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
  const outOfStock = product.stock <= 0;

  const open = () => {
    if (reason) track("click", product.id).catch(() => {});
    navigate(`/product/${product.id}`);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <div className="card group flex flex-col overflow-hidden transition hover:-translate-y-0.5 hover:shadow-md">
      <button onClick={open} className="relative block aspect-[4/3] overflow-hidden bg-slate-100 text-left">
        <img
          src={imageUrl(product)}
          alt={product.name}
          loading="lazy"
          className="h-full w-full object-cover transition duration-300 group-hover:scale-105"
        />
        {outOfStock && (
          <span className="absolute left-2 top-2 rounded-full bg-slate-900/80 px-2 py-0.5 text-xs font-semibold text-white">
            Out of stock
          </span>
        )}
      </button>
      <div className="flex flex-1 flex-col gap-1.5 p-3">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{product.category}</span>
        <button onClick={open} className="line-clamp-2 text-left text-sm font-semibold leading-snug text-slate-900 hover:text-indigo-700">
          {product.name}
        </button>
        <Stars value={product.rating_avg} count={product.rating_count} />
        <div className="mt-auto flex items-center justify-between pt-1">
          <span className="text-base font-bold text-slate-900">{formatPrice(product.price)}</span>
          {action}
        </div>
        {reason && (
          <p className={`mt-1 rounded-lg px-2 py-1.5 text-xs leading-snug ring-1 ring-inset ${style.chip}`} title={style.label}>
            <span className="mr-1">{style.icon}</span>
            {reason}
          </p>
        )}
      </div>
    </div>
  );
}
