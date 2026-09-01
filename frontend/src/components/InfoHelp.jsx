import { Info } from "lucide-react";
import { useState } from "react";

export default function InfoHelp({ title, children, formula, example }) {
  const [open, setOpen] = useState(false);
  return <span className="relative inline-flex align-middle ml-1">
    <button type="button" aria-label={`Información sobre ${title}`} onClick={() => setOpen(v => !v)} className="inline-flex items-center justify-center w-5 h-5 rounded-full text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors">
      <Info className="w-3.5 h-3.5" />
    </button>
    {open && <div className="absolute z-50 top-7 left-0 w-72 rounded-xl border bg-card shadow-xl p-3 text-xs text-foreground">
      <p className="font-heading font-bold mb-1">{title}</p>
      <p className="text-muted-foreground leading-relaxed">{children}</p>
      {formula && <p className="mt-2 rounded-lg bg-secondary/70 p-2"><b>Fórmula:</b> {formula}</p>}
      {example && <p className="mt-1.5 text-muted-foreground"><b>Ejemplo:</b> {example}</p>}
    </div>}
  </span>;
}
