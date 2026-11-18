import { Link, NavLink } from "react-router-dom";
import { useApp } from "../store";

const linkClass = ({ isActive }) =>
  `rounded-lg px-3 py-2 text-sm font-medium transition ${
    isActive ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
  }`;

export default function Navbar() {
  const { demoUsers, user, switchUser, cart } = useApp();
  const isGuest = user && !user.is_demo;

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-4 py-3">
        <Link to="/" className="flex items-center gap-2 text-lg font-extrabold tracking-tight text-slate-900">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-indigo-600 text-white">🛍️</span>
          Shop<span className="-ml-2 text-indigo-600">Smart</span>
        </Link>

        <nav className="flex items-center gap-1">
          <NavLink to="/" end className={linkClass}>Home</NavLink>
          <NavLink to="/shop" className={linkClass}>Shop</NavLink>
          <NavLink to="/evaluation" className={linkClass}>Evaluation</NavLink>
          <NavLink to="/admin" className={linkClass}>Admin</NavLink>
        </nav>

        <div className="ml-auto flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <span className="hidden text-slate-500 sm:inline">Shopping as</span>
            <select
              className="max-w-[16rem] rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-medium focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
              value={user ? (isGuest ? "guest" : String(user.id)) : ""}
              onChange={(e) => switchUser(e.target.value)}
            >
              {isGuest && <option value="guest">👤 {user.name}</option>}
              <option value="new">✨ Start as a new visitor</option>
              <optgroup label="Demo shoppers (returning users)">
                {demoUsers.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name} · {u.persona.replace("Likes ", "")}
                  </option>
                ))}
              </optgroup>
            </select>
          </label>

          <NavLink to="/cart" className={linkClass}>
            <span className="relative inline-flex items-center gap-1">
              🛒 Cart
              {cart.length > 0 && (
                <span className="ml-1 rounded-full bg-indigo-600 px-2 py-0.5 text-xs font-bold text-white">
                  {cart.length}
                </span>
              )}
            </span>
          </NavLink>
        </div>
      </div>
    </header>
  );
}
