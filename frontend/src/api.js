// Small wrapper around the FastAPI backend.
export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const { headers, ...rest } = options;
  const res = await fetch(`${API_URL}${path}`, {
    ...rest,
    headers: { "Content-Type": "application/json", ...headers },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* response had no JSON body */
    }
    const error = new Error(detail);
    error.status = res.status; // e.g. 401 -> the Admin page asks for the token again
    throw error;
  }
  return res.json();
}

// Admin token: asked once on the Admin page and kept for this browser tab session only.
const ADMIN_TOKEN_KEY = "shopsmart.adminToken";
export const adminToken = {
  get: () => {
    try {
      return sessionStorage.getItem(ADMIN_TOKEN_KEY) || "";
    } catch {
      return "";
    }
  },
  set: (token) => {
    try {
      sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
    } catch {
      /* storage blocked: the token only lives until the page reloads */
    }
  },
  clear: () => {
    try {
      sessionStorage.removeItem(ADMIN_TOKEN_KEY);
    } catch {
      /* nothing stored */
    }
  },
};

const adminRequest = (path, options = {}) =>
  request(path, { ...options, headers: { "X-Admin-Token": adminToken.get() } });

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
  boughtTogether: (id) => request(`/recommend/bought-together/${id}`),
  alsoBought: (id) => request(`/recommend/also-bought/${id}`),
  cart: (userId, productIds) =>
    request(`/recommend/cart${qs({ user_id: userId, product_ids: productIds.join(",") })}`),
  evaluation: (refresh = false) => request(`/evaluation${refresh ? "?refresh=true" : ""}`),
  // Admin: recommendation rules (every call sends the X-Admin-Token header)
  adminSettings: () => adminRequest("/admin/settings"),
  saveAdminSettings: (settings) =>
    adminRequest("/admin/settings", { method: "PUT", body: JSON.stringify(settings) }),
  resetAdminSettings: () => adminRequest("/admin/settings/reset", { method: "POST" }),
  adminEvaluate: () => adminRequest("/admin/evaluate", { method: "POST" }),
  adminStats: () => adminRequest("/admin/stats"),
};

export const imageUrl = (product) => `${API_URL}${product.image_url}`;

export const formatPrice = (value) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
