// Small wrapper around the FastAPI backend.
export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* response had no JSON body */
    }
    throw new Error(detail);
  }
  return res.json();
}

const qs = (params) => {
  const clean = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "");
  return clean.length ? `?${new URLSearchParams(clean)}` : "";
};

export const api = {
  products: (params = {}) => request(`/products${qs(params)}`),
  product: (id) => request(`/products/${id}`),
  categories: () => request("/categories"),
  users: () => request("/users"),
  user: (id) => request(`/users/${id}`),
  createVisitor: () => request("/users", { method: "POST" }),
  logEvent: (event) => request("/events", { method: "POST", body: JSON.stringify(event) }),
  home: (userId) => request(`/recommend/home${qs({ user_id: userId })}`),
  similar: (id) => request(`/recommend/similar/${id}`),
  alsoLiked: (id) => request(`/recommend/also-liked/${id}`),
  cart: (userId, productIds) =>
    request(`/recommend/cart${qs({ user_id: userId, product_ids: productIds.join(",") })}`),
  evaluation: (refresh = false) => request(`/evaluation${refresh ? "?refresh=true" : ""}`),
};

export const imageUrl = (product) => `${API_URL}${product.image_url}`;

export const formatPrice = (value) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
