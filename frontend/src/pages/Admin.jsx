import { useEffect, useState } from "react";
import { api } from "../api";
import { METHOD_STYLES } from "../components/ProductCard";
import { Spinner } from "../components/RecommendationRow";

// Admin dashboard: change the hybrid's weights and business rules without touching code.
// Changes apply to the next recommendation request (no retraining needed).

const WEIGHTS = [
  ["collaborative", "Collaborative filtering", "What shoppers with similar behaviour liked"],
  ["svd", "Matrix factorisation", "Hidden taste factors learned from all shoppers"],
  ["content", "Content-based", "Products with similar descriptions and tags"],
  ["popularity", "Popularity", "What is trending right now"],
];

const METRICS = [
  ["precision_at_10", "Precision@10"],
  ["recall_at_10", "Recall@10"],
  ["hit_rate_at_10", "Hit rate@10"],
  ["coverage", "Coverage"],
];

const pct = (v, digits = 0) => `${(v * 100).toFixed(digits)}%`;
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

function Toggle({ label, help, checked, onChange }) {
  return (
    <label className="flex cursor-pointer items-start gap-3 py-2">
      <input
        type="checkbox"
        className="mt-1 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>
        <span className="block text-sm font-medium text-slate-900">{label}</span>
        <span className="block text-xs text-slate-500">{help}</span>
      </span>
    </label>
  );
}

function Slider({ label, help, value, min, max, step, display, onChange }) {
  return (
    <label className="block py-2">
      <span className="flex items-baseline justify-between gap-3">
        <span className="text-sm font-medium text-slate-900">{label}</span>
        <span className="text-sm tabular-nums text-slate-700">{display(value)}</span>
      </span>
      {help && <span className="block text-xs text-slate-500">{help}</span>}
      <input
        type="range"
        className="mt-2 w-full accent-indigo-600"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}

function Stat({ label, value }) {
  return (
    <div className="card p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-extrabold tabular-nums text-slate-900">{value.toLocaleString()}</p>
    </div>
  );
}

function ComparisonTable({ result }) {
  const byMethod = Object.fromEntries(result.results.map((r) => [r.method, r]));
  const base = byMethod.hybrid;
  const mine = byMethod.hybrid_admin;
  if (!base || !mine) return null;
  return (
    <div className="mt-4 overflow-x-auto">
      <table className="w-full min-w-[28rem] text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
            <th className="py-2 pr-4 font-semibold">Metric</th>
            <th className="py-2 pr-4 text-right font-semibold">Default hybrid</th>
            <th className="py-2 pr-4 text-right font-semibold">Your settings</th>
            <th className="py-2 text-right font-semibold">Change</th>
          </tr>
        </thead>
        <tbody>
          {METRICS.map(([key, label]) => {
            const delta = mine[key] - base[key];
            const color = Math.abs(delta) < 1e-4 ? "text-slate-500" : delta > 0 ? "text-emerald-700" : "text-red-700";
            return (
              <tr key={key} className="border-b border-slate-100">
                <td className="py-2 pr-4 text-slate-700">{label}</td>
                <td className="py-2 pr-4 text-right tabular-nums">{pct(base[key], 1)}</td>
                <td className="py-2 pr-4 text-right font-semibold tabular-nums">{pct(mine[key], 1)}</td>
                <td className={`py-2 text-right tabular-nums ${color}`}>
                  {delta >= 0 ? "+" : "−"}
                  {pct(Math.abs(delta), 1)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-slate-500">
        Offline test on {result.n_test_users} users (time-based split). Higher is better. Diversity rules usually
        trade a little accuracy for more variety.
      </p>
    </div>
  );
}

export default function Admin() {
  const [saved, setSaved] = useState(null);
  const [defaults, setDefaults] = useState(null);
  const [draft, setDraft] = useState(null);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [evalResult, setEvalResult] = useState(null);
  const [evaluating, setEvaluating] = useState(false);

  const apply = (data) => {
    setSaved(data.current);
    setDefaults(data.defaults);
    setDraft(data.current);
  };

  useEffect(() => {
    api.adminSettings().then(apply).catch((e) => setError(e.message));
    api.adminStats().then(setStats).catch(() => {});
  }, []);

  if (error) return <p className="text-red-600">Could not load admin settings: {error}</p>;
  if (!draft) return <Spinner label="Loading admin settings…" />;

  const dirty = !same(draft, saved);
  const isDefault = same(saved, defaults);
  const set = (key, value) => setDraft((d) => ({ ...d, [key]: value }));
  const setWeight = (key, value) => setDraft((d) => ({ ...d, weights: { ...d.weights, [key]: value } }));
  const total = Object.values(draft.weights).reduce((a, b) => a + b, 0);

  const run = async (action, message) => {
    setBusy(true);
    setStatus("");
    try {
      apply(await action());
      setEvalResult(null);
      setStatus(message);
    } catch (e) {
      setStatus(`Not saved: ${e.message}`);
    } finally {
      setBusy(false);
    }
  };

  const evaluate = async () => {
    setEvaluating(true);
    try {
      setEvalResult(await api.adminEvaluate());
    } catch (e) {
      setStatus(`Evaluation failed: ${e.message}`);
    } finally {
      setEvaluating(false);
    }
  };

  return (
    <div>
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900">Admin: recommendation rules</h1>
        <p className="text-sm text-slate-500">
          Tune how products are picked for shoppers. Changes apply on the next page load, without retraining.
        </p>
        <p className="mt-2 inline-block rounded-lg bg-amber-50 px-3 py-1.5 text-xs text-amber-800 ring-1 ring-inset ring-amber-200">
          Demo only: this page has no login. A live shop must protect it.
        </p>
      </div>

      {stats && (
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Products" value={stats.n_products} />
          <Stat label="Out of stock" value={stats.n_out_of_stock} />
          <Stat label="Shoppers" value={stats.n_users} />
          <Stat label="Events logged" value={stats.n_events} />
        </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <section className="card p-5">
          <h2 className="text-lg font-bold text-slate-900">"Recommended for you" blend</h2>
          <p className="text-sm text-slate-500">
            How much each method counts. Only the ratio matters; the share column shows the effective mix.
          </p>
          <div className="mt-3 divide-y divide-slate-100">
            {WEIGHTS.map(([key, label, help]) => (
              <Slider
                key={key}
                label={`${METHOD_STYLES[key]?.icon ?? ""} ${label}`}
                help={help}
                value={draft.weights[key]}
                min={0}
                max={1}
                step={0.05}
                display={(v) => `${v.toFixed(2)} · ${total > 0 ? pct(v / total) : "–"} share`}
                onChange={(v) => setWeight(key, v)}
              />
            ))}
          </div>
          {total <= 0 && <p className="mt-2 text-sm text-red-600">Give at least one method a weight above 0.</p>}
        </section>

        <section className="card p-5">
          <h2 className="text-lg font-bold text-slate-900">Business rules</h2>
          <p className="text-sm text-slate-500">Applied after the blend, to the personalised list.</p>
          <div className="mt-3 divide-y divide-slate-100">
            <Slider
              label="Max products per category"
              help="Diversity: stops one category filling the whole list"
              value={draft.max_per_category}
              min={1}
              max={10}
              step={1}
              display={(v) => (v >= 10 ? "No limit" : `${v} of 10`)}
              onChange={(v) => set("max_per_category", v)}
            />
            <Slider
              label="Price-range preference"
              help="How much score a product loses when it is far from the shopper's usual price range"
              value={draft.price_penalty}
              min={0}
              max={1}
              step={0.05}
              display={(v) => (v === 0 ? "Off" : `up to −${pct(v)}`)}
              onChange={(v) => set("price_penalty", v)}
            />
            <Toggle
              label="Hide out-of-stock products"
              help="Recommended for you and Based on your purchases"
              checked={draft.hide_out_of_stock}
              onChange={(v) => set("hide_out_of_stock", v)}
            />
            <Toggle
              label="Hide products the shopper already bought"
              help="Turn off for repeat-purchase shops (groceries, pet food)"
              checked={draft.hide_purchased}
              onChange={(v) => set("hide_purchased", v)}
            />
          </div>

          <h3 className="mt-5 text-sm font-bold text-slate-900">Home page</h3>
          <div className="divide-y divide-slate-100">
            <Slider
              label="Interactions before personalising"
              help="Below this, a visitor sees trending products and best sellers"
              value={draft.min_events_for_personalisation}
              min={1}
              max={20}
              step={1}
              display={(v) => `${v}`}
              onChange={(v) => set("min_events_for_personalisation", v)}
            />
            <Toggle
              label='Show "Recently viewed"'
              help="Products the shopper looked at but did not buy"
              checked={draft.show_recently_viewed}
              onChange={(v) => set("show_recently_viewed", v)}
            />
            <Toggle
              label='Show "Based on your purchases"'
              help="Recommendations that use only the shopper's past orders"
              checked={draft.show_purchase_based}
              onChange={(v) => set("show_purchase_based", v)}
            />
          </div>
        </section>
      </div>

      <div className="sticky bottom-0 mt-6 flex flex-wrap items-center gap-3 border-t border-slate-200 bg-white/95 py-4 backdrop-blur">
        <button
          className="btn-primary"
          disabled={!dirty || busy || total <= 0}
          onClick={() => run(() => api.saveAdminSettings(draft), "Saved. New recommendations use these rules.")}
        >
          {busy ? "Saving…" : "Save changes"}
        </button>
        <button className="btn-secondary" disabled={!dirty || busy} onClick={() => setDraft(saved)}>
          Discard
        </button>
        <button
          className="btn-secondary"
          disabled={isDefault || busy}
          onClick={() => run(api.resetAdminSettings, "Reset to the default rules.")}
        >
          Reset to defaults
        </button>
        <span className="text-sm text-slate-500">
          {status || (dirty ? "You have unsaved changes." : isDefault ? "Using the default rules." : "Custom rules are live.")}
        </span>
      </div>

      <section className="card mt-6 p-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Test the saved rules</h2>
            <p className="text-sm text-slate-500">
              Replays past shopping data and compares your saved rules with the defaults.
            </p>
          </div>
          <button className="btn-secondary" disabled={evaluating || dirty} onClick={evaluate}>
            {evaluating ? "Testing… (a few seconds)" : dirty ? "Save first to test" : "Run test"}
          </button>
        </div>
        {evalResult && <ComparisonTable result={evalResult} />}
      </section>
    </div>
  );
}
