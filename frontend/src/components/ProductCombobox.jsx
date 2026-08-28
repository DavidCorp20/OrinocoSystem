import { useEffect, useRef, useState } from "react";
import { Package, ScanBarcode } from "lucide-react";
import { fmtMoney, fmtNum } from "../lib/format";

export default function ProductCombobox({
  products,
  onSelect,
  placeholder = "Buscar por nombre, SKU o código de barras…",
  testid = "product-combobox",
  autoFocus = false,
  currency = "USD",
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const close = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const q = query.trim().toLowerCase();
  const results = q
    ? products
        .filter((p) =>
          [p.name, p.sku, p.barcode].filter(Boolean).some((v) => String(v).toLowerCase().includes(q))
        )
        .slice(0, 8)
    : [];

  const pick = (p) => {
    onSelect(p);
    setQuery("");
    setOpen(false);
  };

  const onKeyDown = (e) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    const exact =
      products.find((p) => p.barcode && p.barcode.toLowerCase() === q) ||
      products.find((p) => p.sku && p.sku.toLowerCase() === q);
    if (exact) pick(exact);
    else if (results.length === 1) pick(results[0]);
  };

  return (
    <div className="relative" ref={ref}>
      <ScanBarcode className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
      <input
        data-testid={testid}
        autoFocus={autoFocus}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        className="w-full h-11 pl-10 pr-3 rounded-xl border border-input bg-background text-sm outline-none focus:ring-2 focus:ring-primary/40"
      />
      {open && q && (
        <div className="absolute z-50 mt-1.5 w-full bg-card border border-border rounded-xl shadow-xl max-h-72 overflow-y-auto" data-testid={`${testid}-results`}>
          {results.length === 0 ? (
            <p className="px-4 py-3 text-sm text-muted-foreground">Sin resultados para “{query}”</p>
          ) : (
            results.map((p) => (
              <button
                key={p.id}
                type="button"
                data-testid={`${testid}-result-${p.id}`}
                onClick={() => pick(p)}
                className="w-full text-left px-4 py-2.5 hover:bg-secondary flex items-center gap-3 transition-colors"
              >
                <Package className="w-4 h-4 text-primary shrink-0" />
                <span className="flex-1 min-w-0">
                  <span className="block text-sm font-medium text-slate-800 truncate">{p.name}</span>
                  <span className="block text-xs text-muted-foreground font-num">
                    {p.sku}
                    {p.barcode ? ` · ${p.barcode}` : ""} · stock: {fmtNum(p.stock)}
                  </span>
                </span>
                <span className="text-sm font-num font-semibold">{fmtMoney(p.sale_price, currency)}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
