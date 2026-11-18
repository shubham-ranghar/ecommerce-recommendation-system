import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import RecommendationRow, { Spinner } from "../components/RecommendationRow";
import { useApp } from "../store";

function ContextBanner({ user, data }) {
  const isNew = data.user_type === "new";
  return (
    <div className="overflow-hidden rounded-3xl bg-gradient-to-br from-indigo-600 via-indigo-500 to-violet-500 p-6 text-white shadow-lg sm:p-8">
      <p className="text-sm font-medium text-indigo-100">
        {isNew ? "👋 Welcome to ShopSmart" : `👋 Welcome back, ${user.name.split(" ")[0]}`}
      </p>
      <h1 className="mt-1 text-2xl font-extrabold sm:text-3xl">
        {isNew ? "Discover what everyone is loving right now" : "Picked just for you"}
      </h1>
      <div className="mt-4 flex flex-wrap gap-2 text-xs">
        <span className="rounded-full bg-white/20 px-3 py-1 font-semibold">
          Context: {isNew ? "new visitor (cold start)" : "returning user"}
        </span>
        <span className="rounded-full bg-white/20 px-3 py-1">{data.n_events} interactions recorded</span>
        <span className="rounded-full bg-white/20 px-3 py-1">
          Strategy: {isNew ? "popularity & category-based" : "personalised hybrid"}
        </span>
      </div>
      {isNew && (
        <p className="mt-4 max-w-2xl text-sm text-indigo-100">
          We don't know you yet, so we show trending products. View or add a few products to your cart. After 3
          interactions, this page switches to <b>Recommended for you</b>.
        </p>
      )}
    </div>
  );
}

export default function Home() {
  const { user } = useApp();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!user) return;
    setData(null);
    api.home(user.id).then(setData).catch((e) => setError(e.message));
  }, [user]);

  if (error) return <p className="text-red-600">Could not load recommendations: {error}</p>;
  if (!user || !data) return <Spinner label="Finding products for you…" />;

  return (
    <div>
      <ContextBanner user={user} data={data} />
      {data.sections.map((section) => (
        <RecommendationRow
          key={section.key}
          title={section.title}
          subtitle={section.subtitle}
          method={section.method}
          items={section.items}
        />
      ))}
      <div className="mt-12 text-center">
        <Link to="/shop" className="btn-secondary">Browse all 500 products →</Link>
      </div>
    </div>
  );
}
