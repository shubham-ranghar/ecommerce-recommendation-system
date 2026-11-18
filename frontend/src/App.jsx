import { Route, Routes } from "react-router-dom";
import Navbar from "./components/Navbar";
import { useApp } from "./store";
import { API_URL } from "./api";
import Home from "./pages/Home";
import Shop from "./pages/Shop";
import ProductPage from "./pages/ProductPage";
import CartPage from "./pages/CartPage";
import Evaluation from "./pages/Evaluation";

export default function App() {
  const { backendError } = useApp();
  return (
    <div className="min-h-screen text-slate-800">
      <Navbar />
      {backendError && (
        <div className="mx-auto mt-6 max-w-6xl px-4">
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            <b>Cannot reach the backend at {API_URL}.</b> Start it with{" "}
            <code className="rounded bg-red-100 px-1">uvicorn app.main:app --reload</code> in the backend folder,
            then refresh this page. ({backendError})
          </div>
        </div>
      )}
      <main className="mx-auto max-w-6xl px-4 pb-16 pt-6">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/shop" element={<Shop />} />
          <Route path="/product/:id" element={<ProductPage />} />
          <Route path="/cart" element={<CartPage />} />
          <Route path="/evaluation" element={<Evaluation />} />
        </Routes>
      </main>
      <footer className="border-t border-slate-200 py-6 text-center text-xs text-slate-400">
        ShopSmart · E-commerce Recommendation System demo · Collect → Represent → Generate candidates → Rank → Measure
      </footer>
    </div>
  );
}
