import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { Spinner } from "../components/RecommendationRow";

// Validated categorical palette (first three slots), assigned in fixed order.
const SERIES = [
  { key: "precision", name: "Precision@10", color: "#2a78d6" },
  { key: "recall", name: "Recall@10", color: "#eb6834" },
  { key: "hit", name: "Hit rate@10", color: "#1baf7a" },
];
const SHORT = {
  random: "Random",
  popularity: "Popularity",
  content: "Content",
  collaborative: "Item-CF",
  svd: "SVD",
  hybrid: "Hybrid",
  hybrid_no_diversity: "Hybrid (no div.)",
};
const pct = (v, digits = 1) => `${(v * 100).toFixed(digits)}%`;

const PIPELINE = [
  ["📥", "Collect", "Views, clicks, carts, purchases and ratings are logged as events in SQLite."],
  ["🧱", "Represent", "TF-IDF vectors for products, a user × item matrix with weights view=1 … purchase=5."],
  ["🎯", "Generate candidates", "Top 100 items from popularity, content, item-CF and SVD are merged."],
  ["🏆", "Rank", "Normalised scores are blended, then business rules are applied: stock, already bought, price, diversity."],
  ["📏", "Measure", "Time-based split; Precision, Recall, Hit rate @10 and catalogue coverage."],
];

const METRICS_HELP = [
  ["Precision@10", "Out of the 10 recommended products, how many did the user really interact with later?"],
  ["Recall@10", "Out of all products the user interacted with later, how many did we find in our top 10?"],
  ["Hit rate@10", "For how many users was at least one of the 10 recommendations correct?"],
  ["Coverage", "How much of the catalogue gets recommended at all. Low coverage means the same few items are shown to everyone."],
];

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-semibold text-slate-900">{payload[0].payload.label || label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} className="flex items-center gap-2 text-slate-600">
          <span className="h-2.5 w-2.5 rounded-sm" style={{ background: p.color }} />
          {p.name}: <b className="text-slate-900">{pct(p.value)}</b>
        </p>
      ))}
    </div>
  );
}

export default function Evaluation() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [running, setRunning] = useState(false);

  const load = (refresh = false) => {
    setRunning(refresh);
    api
      .evaluation(refresh)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setRunning(false));
  };
  useEffect(() => load(), []);

  if (error) return <p className="text-red-600">Could not load evaluation: {error}</p>;
  if (!data) return <Spinner label="Loading evaluation results…" />;

  const k = data.k;
  const rows = data.results.map((r) => ({
    method: r.method,
    label: r.label,
    short: SHORT[r.method] || r.label,
    precision: r[`precision_at_${k}`],
    recall: r[`recall_at_${k}`],
    hit: r[`hit_rate_at_${k}`],
    coverage: r.coverage,
  }));
  const best = (key) => Math.max(...rows.map((r) => r[key]));
  const byKey = Object.fromEntries(rows.map((r) => [r.method, r]));
  const hybrid = byKey.hybrid;
  const pop = byKey.popularity;

  const axisProps = { tick: { fontSize: 12, fill: "#52514e" }, axisLine: { stroke: "#cbd5e1" }, tickLine: false };

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900">Evaluation dashboard</h1>
          <p className="text-sm text-slate-500">
            Offline evaluation · {data.split} · {data.n_test_users} test users · {data.n_train_events.toLocaleString()} train /{" "}
            {data.n_test_events.toLocaleString()} test events
          </p>
        </div>
        <button className="btn-secondary" onClick={() => load(true)} disabled={running}>
          {running ? "Re-running… (a few seconds)" : "↻ Re-run evaluation"}
        </button>
      </div>

      {/* Pipeline overview */}
      <div className="mt-6 grid gap-3 sm:grid-cols-5">
        {PIPELINE.map(([icon, title, text], i) => (
          <div key={title} className="card relative p-4">
            <p className="text-2xl">{icon}</p>
            <p className="mt-1 text-sm font-bold text-slate-900">{i + 1}. {title}</p>
            <p className="mt-1 text-xs leading-snug text-slate-500">{text}</p>
          </div>
        ))}
      </div>

      {/* Headline numbers */}
      {hybrid && pop && (
        <div className="mt-6 grid gap-3 sm:grid-cols-3">
          <div className="card p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Hybrid hit rate@{k}</p>
            <p className="mt-1 text-3xl font-extrabold text-slate-900">{pct(hybrid.hit)}</p>
            <p className="text-xs text-slate-500">of users got at least one relevant product</p>
          </div>
          <div className="card p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Hybrid vs popularity</p>
            <p className="mt-1 text-3xl font-extrabold text-slate-900">{(hybrid.precision / pop.precision).toFixed(1)}×</p>
            <p className="text-xs text-slate-500">higher precision than the non-personalised baseline</p>
          </div>
          <div className="card p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Catalogue coverage</p>
            <p className="mt-1 text-3xl font-extrabold text-slate-900">{pct(hybrid.coverage, 0)}</p>
            <p className="text-xs text-slate-500">Hybrid, vs {pct(pop.coverage, 0)} for popularity</p>
          </div>
        </div>
      )}

      {/* Accuracy chart */}
      <section className="card mt-6 p-5">
        <h2 className="text-lg font-bold text-slate-900">Accuracy by method (higher is better)</h2>
        <p className="text-sm text-slate-500">Hover a bar for exact values</p>
        <div className="mt-4 h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} barGap={2} barCategoryGap="22%" margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="#e5e7eb" />
              <XAxis dataKey="short" {...axisProps} interval={0} />
              <YAxis {...axisProps} axisLine={false} tickFormatter={(v) => pct(v, 0)} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "#f1f5f9" }} />
              <Legend verticalAlign="top" align="right" iconType="square" wrapperStyle={{ fontSize: 12, paddingBottom: 8 }} />
              {SERIES.map((s) => (
                <Bar key={s.key} dataKey={s.key} name={s.name} fill={s.color} radius={[4, 4, 0, 0]} maxBarSize={26} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* Coverage chart: separate because it is on a different scale */}
      <section className="card mt-6 p-5">
        <h2 className="text-lg font-bold text-slate-900">Catalogue coverage</h2>
        <p className="text-sm text-slate-500">Share of the 500 products that were recommended to at least one test user</p>
        <div className="mt-4 h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="#e5e7eb" />
              <XAxis dataKey="short" {...axisProps} interval={0} />
              <YAxis {...axisProps} axisLine={false} domain={[0, 1]} tickFormatter={(v) => pct(v, 0)} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "#f1f5f9" }} />
              <Bar dataKey="coverage" name="Coverage" fill="#2a78d6" radius={[4, 4, 0, 0]} maxBarSize={40} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* Table view */}
      <section className="card mt-6 overflow-x-auto p-5">
        <h2 className="text-lg font-bold text-slate-900">Results table</h2>
        <table className="mt-3 w-full min-w-[560px] text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="py-2">Method</th>
              <th className="py-2 text-right">Precision@{k}</th>
              <th className="py-2 text-right">Recall@{k}</th>
              <th className="py-2 text-right">Hit rate@{k}</th>
              <th className="py-2 text-right">Coverage</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.method} className={`border-b border-slate-100 ${r.method === "hybrid" ? "bg-indigo-50/60" : ""}`}>
                <td className="py-2 font-medium text-slate-900">{r.label}</td>
                {["precision", "recall", "hit", "coverage"].map((key) => (
                  <td key={key} className={`py-2 text-right tabular-nums ${r[key] === best(key) ? "font-bold text-slate-900" : "text-slate-600"}`}>
                    {key === "coverage" ? pct(r[key]) : r[key].toFixed(4)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-xs text-slate-400">Bold = best in the column. Generated {new Date(data.generated_at).toLocaleString()}.</p>
      </section>

      {/* Explanations */}
      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <section className="card p-5">
          <h2 className="text-lg font-bold text-slate-900">What the metrics mean</h2>
          <dl className="mt-3 space-y-3 text-sm">
            {METRICS_HELP.map(([term, text]) => (
              <div key={term}>
                <dt className="font-semibold text-slate-900">{term}</dt>
                <dd className="text-slate-600">{text}</dd>
              </div>
            ))}
          </dl>
        </section>
        <section className="card p-5">
          <h2 className="text-lg font-bold text-slate-900">Key takeaways</h2>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-600">
            <li>Every method is far better than <b>random</b>, so the models learned real patterns.</li>
            <li><b>Popularity</b> is a solid cold-start fallback but covers only a tiny part of the catalogue.</li>
            <li><b>Collaborative filtering</b> is the strongest single method: shoppers' behaviour tells more than product text.</li>
            <li><b>Content-based</b> has the highest coverage and works for new products with no history.</li>
            <li>
              <b>Hybrid</b> combines them and gets the best hit rate. The diversity rule (max 3 per category) costs some
              accuracy (compare with "Hybrid (no div.)") but gives users a more varied, less repetitive list.
            </li>
          </ul>
        </section>
      </div>
    </div>
  );
}
