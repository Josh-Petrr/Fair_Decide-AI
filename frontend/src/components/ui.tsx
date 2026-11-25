import { Loader2, X } from "lucide-react";
import { useEffect, type ButtonHTMLAttributes, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";

export const cn = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

/** Overlays (dialogs, drawers, action bars) render directly into <body>, so no ancestor style can displace them. */
export const Portal = ({ children }: { children: ReactNode }) => createPortal(children, document.body);

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("rounded-2xl border border-slate-200/80 bg-white shadow-sm", className)}>{children}</div>;
}

const TONES = {
  gray: "bg-slate-100 text-slate-700", green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  amber: "bg-amber-50 text-amber-800 ring-amber-200", red: "bg-rose-50 text-rose-700 ring-rose-200",
  brand: "bg-brand-50 text-brand-700 ring-brand-200", blue: "bg-sky-50 text-sky-700 ring-sky-200",
};
export type Tone = keyof typeof TONES;

export function Badge({ tone = "gray", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ring-transparent", TONES[tone], className)}>{children}</span>;
}

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger"; loading?: boolean; size?: "sm" | "md" };
export function Button({ variant = "primary", loading, size = "md", className, children, disabled, ...p }: BtnProps) {
  const v = {
    primary: "bg-brand-600 text-white hover:bg-brand-700 shadow-sm shadow-brand-600/30",
    secondary: "bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50",
    ghost: "text-slate-600 hover:bg-slate-100",
    danger: "bg-white text-rose-600 ring-1 ring-rose-200 hover:bg-rose-50",
  }[variant];
  return (
    <button {...p} disabled={disabled || loading}
      className={cn("inline-flex items-center justify-center gap-2 rounded-xl font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "px-3 py-1.5 text-sm" : "px-4 py-2.5 text-sm", v, className)}>
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

const AV = ["bg-violet-100 text-violet-700", "bg-sky-100 text-sky-700", "bg-emerald-100 text-emerald-700",
  "bg-amber-100 text-amber-800", "bg-rose-100 text-rose-700", "bg-indigo-100 text-indigo-700", "bg-teal-100 text-teal-700"];
export function Avatar({ name, size = 40 }: { name: string; size?: number }) {
  const initials = name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  const tone = AV[[...name].reduce((a, ch) => a + ch.charCodeAt(0), 0) % AV.length];
  return <div className={cn("grid shrink-0 place-items-center rounded-full font-semibold", tone)}
    style={{ width: size, height: size, fontSize: size * 0.36 }}>{initials}</div>;
}

/** Circular gauge for a 0..1 value. */
export function Ring({ value, size = 64, label }: { value: number; size?: number; label?: string }) {
  const r = (size - 8) / 2, c = 2 * Math.PI * r;
  const color = value >= 0.7 ? "#10b981" : value >= 0.5 ? "#6c5cf0" : value >= 0.35 ? "#f59e0b" : "#f43f5e";
  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#eef0f6" strokeWidth="7" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="7" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - value)} style={{ transition: "stroke-dashoffset .8s ease" }} />
      </svg>
      <div className="absolute text-center leading-none">
        <div className="font-display font-bold text-slate-800" style={{ fontSize: Math.max(11, size * 0.22) }}>{Math.round(value * 100)}%</div>
        {label && size >= 64 && <div className="mt-0.5 text-[9px] uppercase tracking-wide text-slate-400">{label}</div>}
      </div>
    </div>
  );
}

/** Workload now -> after, on a 0..150% scale with the 100% limit marked. */
export function LoadBar({ now, after, compact }: { now: number; after?: number; compact?: boolean }) {
  const pct = (v: number) => `${Math.min(v, 150) / 1.5}%`;
  const tone = (v: number) => (v > 100 ? "bg-rose-500" : v > 80 ? "bg-amber-400" : "bg-emerald-500");
  return (
    <div>
      {!compact && <div className="mb-1 flex justify-between text-xs text-slate-500">
        <span>Workload</span>
        <span className="font-medium text-slate-700">{now}%{after !== undefined && <> → <b className={after > 100 ? "text-rose-600" : ""}>{after}%</b></>}</span>
      </div>}
      <div className="relative h-2 overflow-hidden rounded-full bg-slate-100">
        {after !== undefined && <div className={cn("absolute inset-y-0 left-0 rounded-full opacity-35", tone(after))} style={{ width: pct(after) }} />}
        <div className={cn("absolute inset-y-0 left-0 rounded-full", tone(now))} style={{ width: pct(now) }} />
        <div className="absolute inset-y-0 w-px bg-slate-400" style={{ left: "66.67%" }} title="100%" />
      </div>
    </div>
  );
}

/** Horizontal diverging bars for SHAP factor impacts (percentage points). */
export function FactorBars({ factors, max = 8 }: { factors: { factor: string; impact: number }[]; max?: number }) {
  const m = Math.max(max, ...factors.map((f) => Math.abs(f.impact)));
  return (
    <div className="space-y-1.5">
      {factors.map((f) => (
        <div key={f.factor} className="grid grid-cols-[110px_1fr_42px] items-center gap-2 text-xs">
          <span className="truncate text-slate-600">{f.factor}</span>
          <div className="relative h-2.5 rounded bg-slate-50">
            <div className="absolute inset-y-0 left-1/2 w-px bg-slate-300" />
            <div className={cn("absolute inset-y-0 rounded", f.impact >= 0 ? "left-1/2 bg-emerald-400" : "right-1/2 bg-rose-400")}
              style={{ width: `${(Math.abs(f.impact) / m) * 50}%` }} />
          </div>
          <span className={cn("text-right font-medium tabular-nums", f.impact >= 0 ? "text-emerald-600" : "text-rose-600")}>
            {f.impact > 0 ? "+" : ""}{f.impact.toFixed(1)}
          </span>
        </div>
      ))}
    </div>
  );
}

export function LevelDots({ level, required }: { level: number | null; required?: number }) {
  return (
    <span className="inline-flex gap-0.5" title={level ? `Level ${level}/5${required ? `, needs ${required}` : ""}` : "Level not recorded"}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className={cn("h-1.5 w-1.5 rounded-full",
          level && i <= level ? (required && level < required ? "bg-rose-400" : "bg-brand-500")
            : required && i <= required ? "bg-slate-300" : "bg-slate-200")} />
      ))}
    </span>
  );
}

export function Spinner({ label }: { label?: string }) {
  return <div className="flex items-center justify-center gap-2 py-16 text-slate-400"><Loader2 className="h-5 w-5 animate-spin" />{label}</div>;
}

export function Empty({ icon, title, text }: { icon?: ReactNode; title: string; text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-14 text-center">
      {icon && <div className="mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-brand-50 text-brand-600">{icon}</div>}
      <div className="font-medium text-slate-700">{title}</div>
      {text && <div className="mt-1 max-w-sm text-sm text-slate-500">{text}</div>}
    </div>
  );
}

export function Modal({ open, onClose, title, children, footer, wide }: { open: boolean; onClose: () => void; title: ReactNode;
  children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);
  if (!open) return null;
  return (
    <Portal>
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink-900/40 p-4 backdrop-blur-sm" onMouseDown={onClose}>
      <div onMouseDown={(e) => e.stopPropagation()}
        className={cn("flex max-h-[90vh] w-full animate-rise flex-col rounded-2xl bg-white shadow-2xl", wide ? "max-w-4xl" : "max-w-xl")}>
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <h3 className="text-lg font-bold text-slate-800">{title}</h3>
          <button onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-slate-100"><X className="h-5 w-5" /></button>
        </div>
        <div className="scrollbar-thin overflow-y-auto px-6 py-5">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-slate-100 px-6 py-4">{footer}</div>}
      </div>
    </div>
    </Portal>
  );
}

export function PageHeader({ title, subtitle, actions, eyebrow }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow && <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-brand-600">{eyebrow}</div>}
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

/** KPI tile: the number is the hero, the hint stays quiet. With `to`, the whole tile is a link. */
export function Stat({ to, label, value, hint, icon, tone = "brand" }: { to?: string; label: string; value: ReactNode; hint?: ReactNode; icon: ReactNode;
  tone?: "brand" | "green" | "amber" | "red" | "blue" }) {
  const t = { brand: "bg-brand-50 text-brand-600", green: "bg-emerald-50 text-emerald-600", amber: "bg-amber-50 text-amber-600",
    red: "bg-rose-50 text-rose-600", blue: "bg-sky-50 text-sky-600" }[tone];
  const body = <>
    <div className={cn("grid h-9 w-9 place-items-center rounded-xl", t)}>{icon}</div>
    <div className="mt-3 font-display text-4xl font-extrabold tabular-nums tracking-tight text-slate-900">{value}</div>
    <div className="mt-1 text-base font-semibold text-slate-700">{label}</div>
    {hint && <div className="mt-0.5 text-sm text-slate-500">{hint}</div>}
  </>;
  const box = "rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm";
  return to ? <Link to={to} className={cn(box, "transition hover:-translate-y-0.5 hover:border-brand-200 hover:shadow-md")}>{body}</Link> : <div className={box}>{body}</div>;
}

export const fmtDate = (d?: string | null) => d ? new Date(d + (d.length === 10 ? "T00:00:00" : "")).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "-";

export const inputCls = "w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-brand-400 focus:ring-4 focus:ring-brand-100";
