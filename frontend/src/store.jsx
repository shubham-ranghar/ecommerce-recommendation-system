// App-wide state: current user, cart and event tracking (the COLLECT step of the pipeline).
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api";

const AppContext = createContext(null);

// localStorage can be blocked (private mode etc.), so every access is wrapped.
const storage = {
  get(key, fallback) {
    try {
      const value = localStorage.getItem(key);
      return value === null ? fallback : JSON.parse(value);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* ignore */
    }
  },
};

// One id per browser tab session, used for "frequently bought together".
const SESSION_ID = `web-${Math.random().toString(36).slice(2, 10)}`;

export function AppProvider({ children }) {
  const [demoUsers, setDemoUsers] = useState([]);
  const [user, setUser] = useState(null);
  const [cart, setCart] = useState(() => storage.get("cart", []));
  const [backendError, setBackendError] = useState(null);
  const [eventCount, setEventCount] = useState(0); // bumps after each logged event

  // Load demo users and restore the last selected user (or create a new visitor).
  useEffect(() => {
    (async () => {
      try {
        const users = await api.users();
        setDemoUsers(users);
        const savedId = storage.get("userId", null);
        if (savedId) {
          try {
            setUser(await api.user(savedId));
            return;
          } catch {
            /* saved user no longer exists (database was regenerated) */
          }
        }
        const visitor = await api.createVisitor();
        storage.set("userId", visitor.id);
        setUser(visitor);
      } catch (err) {
        setBackendError(err.message);
      }
    })();
  }, []);

  useEffect(() => storage.set("cart", cart), [cart]);

  const switchUser = useCallback(async (value) => {
    const next = value === "new" ? await api.createVisitor() : await api.user(Number(value));
    storage.set("userId", next.id);
    setUser(next);
    setCart([]);
  }, []);

  const track = useCallback(
    async (eventType, productId, rating) => {
      if (!user) return;
      try {
        await api.logEvent({ user_id: user.id, product_id: productId, event_type: eventType, rating, session_id: SESSION_ID });
        setEventCount((c) => c + 1);
      } catch (err) {
        console.warn("Could not log event", err);
        throw err;
      }
    },
    [user],
  );

  const addToCart = useCallback(
    async (product) => {
      setCart((items) => (items.some((p) => p.id === product.id) ? items : [...items, product]));
      await track("add_to_cart", product.id);
    },
    [track],
  );

  const removeFromCart = useCallback((id) => setCart((items) => items.filter((p) => p.id !== id)), []);

  const checkout = useCallback(async () => {
    const results = await Promise.allSettled(cart.map((p) => track("purchase", p.id)));
    const failed = results.filter((r) => r.status === "rejected").map((r) => r.reason.message);
    setCart([]);
    return failed;
  }, [cart, track]);

  const value = useMemo(
    () => ({ demoUsers, user, switchUser, cart, addToCart, removeFromCart, checkout, track, eventCount, backendError }),
    [demoUsers, user, switchUser, cart, addToCart, removeFromCart, checkout, track, eventCount, backendError],
  );
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export const useApp = () => useContext(AppContext);
