import { useEffect, useState } from "react";
import { api } from "../api";
import ProductCard from "../components/ProductCard";
import { Spinner } from "../components/RecommendationRow";

const PAGE_SIZE = 20;

export default function Shop() {
  const [categories, setCategories] = useState([]);
  const [category, setCategory] = useState("");
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [data, setData] = useState(null);

  useEffect(() => {
    api.categories().then(setCategories).catch(() => {});
  }, []);

  useEffect(() => {
    setData(null);
    api
      .products({ category, q: search, limit: PAGE_SIZE, offset: page * PAGE_SIZE })
      .then(setData)
      .catch(() => setData({ total: 0, items: [] }));
  }, [category, search, page]);

  const chip = (active) =>
    `rounded-full px-3 py-1.5 text-sm font-medium transition ${
      active ? "bg-indigo-600 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-100"
    }`;
  const pages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-extrabold text-slate-900">All products</h1>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setPage(0);
            setSearch(query);
          }}
          className="flex gap-2"
        >
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search name, brand or tag…"
            className="w-64 rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
          />
          <button className="btn-primary">Search</button>
        </form>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button className={chip(!category)} onClick={() => { setCategory(""); setPage(0); }}>All</button>
        {categories.map((c) => (
          <button key={c.name} className={chip(category === c.name)} onClick={() => { setCategory(c.name); setPage(0); }}>
            {c.name}
          </button>
        ))}
      </div>

      {!data ? (
        <Spinner />
      ) : (
        <>
          <p className="mt-4 text-sm text-slate-500">{data.total} products</p>
          <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            {data.items.map((p) => (
              <ProductCard key={p.id} product={p} />
            ))}
          </div>
          {pages > 1 && (
            <div className="mt-8 flex items-center justify-center gap-3 text-sm">
              <button className="btn-secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>← Previous</button>
              <span className="text-slate-500">Page {page + 1} of {pages}</span>
              <button className="btn-secondary" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>Next →</button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
