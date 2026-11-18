import ProductCard, { methodStyle } from "./ProductCard";

export function Spinner({ label = "Loading…" }) {
  return (
    <div className="flex items-center gap-3 py-10 text-sm text-muted">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-line border-t-ink" />
      {label}
    </div>
  );
}

/** A titled list of recommended products, e.g. "Trending now" or "Similar products". */
export default function RecommendationRow({ title, subtitle, method, items, loading, empty, renderAction }) {
  const style = methodStyle(method);
  return (
    <section className="mt-14">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="font-serif text-2xl font-medium tracking-tight text-ink">{title}</h2>
          {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
        </div>
        {method && (
          <span className="rounded-full border border-line bg-surface px-3 py-1 text-xs text-muted">
            {style.label}
          </span>
        )}
      </div>
      {loading ? (
        <Spinner />
      ) : items?.length ? (
        <div className="-mx-4 flex snap-x snap-mandatory gap-4 overflow-x-auto px-4 pb-2 sm:mx-0 sm:grid sm:grid-cols-3 sm:overflow-visible sm:px-0 sm:pb-0 lg:grid-cols-5">
          {items.map((rec) => (
            <div key={rec.product.id} className="w-44 shrink-0 snap-start sm:w-auto">
              <ProductCard
                product={rec.product}
                reason={rec.reason}
                method={rec.method}
                action={renderAction?.(rec.product)}
              />
            </div>
          ))}
        </div>
      ) : (
        <p className="rounded-xl border border-dashed border-line bg-surface p-6 text-center text-sm text-muted">
          {empty || "No recommendations yet."}
        </p>
      )}
    </section>
  );
}
