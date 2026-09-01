import { Info } from "lucide-react";
import { useEffect, useRef, useState } from "react";

const AUTO_CLOSE_MS = 15000;

export default function InfoHelp({ title, children, formula, example }) {
  const [open, setOpen] = useState(false);
  const [hovered, setHovered] = useState(false);
  const closeTimer = useRef(null);

  useEffect(() => {
    if (!open || hovered) return undefined;

    closeTimer.current = setTimeout(() => {
      setOpen(false);
    }, AUTO_CLOSE_MS);

    return () => {
      if (closeTimer.current) {
        clearTimeout(closeTimer.current);
        closeTimer.current = null;
      }
    };
  }, [open, hovered]);

  const handleMouseEnter = () => {
    setHovered(true);
    setOpen(true);
  };

  const handleMouseLeave = () => {
    setHovered(false);
    setOpen(false);
  };

  const handleClick = () => {
    setOpen((value) => !value);
  };

  return (
    <span
      className="relative inline-flex align-middle ml-1"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <button
        type="button"
        aria-label={`Información sobre ${title}`}
        aria-expanded={open}
        onClick={handleClick}
        className="inline-flex items-center justify-center w-5 h-5 rounded-full text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors"
      >
        <Info className="w-3.5 h-3.5" />
      </button>
      {open && (
        <div className="absolute z-50 top-7 left-0 w-72 rounded-xl border bg-card shadow-xl p-3 text-xs text-foreground">
          <p className="font-heading font-bold mb-1">{title}</p>
          <p className="text-muted-foreground leading-relaxed">{children}</p>
          {formula && (
            <p className="mt-2 rounded-lg bg-secondary/70 p-2">
              <b>Fórmula:</b> {formula}
            </p>
          )}
          {example && (
            <p className="mt-1.5 text-muted-foreground">
              <b>Ejemplo:</b> {example}
            </p>
          )}
        </div>
      )}
    </span>
  );
}
