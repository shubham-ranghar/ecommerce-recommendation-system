import { Link, NavLink } from "react-router-dom";
import { useApp } from "../store";

const linkClass = ({ isActive }) =>
  `rounded-lg px-3 py-2 text-sm transition ${
    isActive ? "bg-chip font-medium text-ink" : "text-muted hover:bg-chip hover:text-ink"
  }`;

function CartIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M6 7h12l-1 13H7L6 7Z" />
      <path d="M9 7V6a3 3 0 0 1 6 0v1" />
    </svg>
  );
}

export default function Navbar() {
  const { demoUsers, user, switchUser, cart } = useApp();
  const isGuest = user && !user.is_demo;

  return (
    <header className="sticky top-0 z-20 border-b border-line bg-canvas">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-4 py-4 md:flex-nowrap">
        <Link to="/" className="font-serif text-xl font-semibold tracking-tight text-ink">
          ShopSmart
        </Link>

        <nav className="order-last flex w-full items-center justify-center gap-1 md:order-none md:w-auto md:flex-1">
          <NavLink to="/" end className={linkClass}>Home</NavLink>
          <NavLink to="/shop" className={linkClass}>Shop</NavLink>
          <NavLink to="/evaluation" className={linkClass}>Evaluation</NavLink>
          <NavLink to="/admin" className={linkClass}>Admin</NavLink>
        </nav>

        <div className="ml-auto flex items-center gap-3 md:ml-0">
          <label className="flex items-center gap-2 text-sm">
            <span className="hidden text-muted lg:inline">Shopping as</span>
            <select
              className="max-w-[12rem] rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink focus:border-ink focus:outline-none sm:max-w-[16rem]"
              value={user ? (isGuest ? "guest" : String(user.id)) : ""}
              onChange={(e) => switchUser(e.target.value)}
            >
              {isGuest && <option value="guest">{user.name}</option>}
              <option value="new">Start as a new visitor</option>
              <optgroup label="Demo shoppers (returning users)">
                {demoUsers.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name} · {u.persona.replace("Likes ", "")}
                  </option>
                ))}
              </optgroup>
            </select>
          </label>

          <NavLink
            to="/cart"
            aria-label={`Cart, ${cart.length} items`}
            className={({ isActive }) =>
              `relative inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition ${
                isActive ? "bg-chip text-ink" : "text-ink hover:bg-chip"
              }`
            }
          >
            <CartIcon />
            <span className="hidden sm:inline">Cart</span>
            {cart.length > 0 && (
              <span className="min-w-[1.25rem] rounded-full bg-accent px-1.5 text-center text-[11px] font-semibold leading-5 text-surface">
                {cart.length}
              </span>
            )}
          </NavLink>
        </div>
      </div>
    </header>
  );
}
