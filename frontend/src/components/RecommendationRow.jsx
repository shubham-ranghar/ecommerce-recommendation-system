import ProductCard, { methodStyle } from "./ProductCard";

export function Spinner({ label = "Loading…" }) {
  return (
    <div className="flex items-center gap-3 py-10 text-sm text-slate-500">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-200 border-t-indigo-600" />
      {label}
    </div>
  );
}

/** A titled list of recommended products, e.g. "Trending now" or "Similar products". */
export default function RecommendationRow({ title, subtitle, method, items, loading, empty, renderAction }) {
  const style = methodStyle(method);
  return (
    <section className="mt-10">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-xl font-bold text-slate-900">{title}</h2>
          {subtitle && <p className="text-sm text-slate-500">{subtitle}</p>}
        </div>
        {method && (
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset ${style.chip}`}>
            {style.icon} {style.label}
          </span>
        )}
      </div>
      {loading ? (
        <Spinner />
      ) : items?.length ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          {items.map((rec) => (
            <ProductCard
              key={rec.product.id}
              product={rec.product}
              reason={rec.reason}
              method={rec.method}
              action={renderAction?.(rec.product)}
            />
          ))}
        </div>
      ) : (
        <p className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
          {empty || "No recommendations yet."}
        </p>
      )}
    </section>
  );
}
