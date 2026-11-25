import { ArrowRight, Briefcase, Eye, EyeOff, Scale, ShieldCheck, Sparkles } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { Avatar, Button, Spinner, cn, inputCls } from "../components/ui";
import { useApi } from "../lib/api";
import { useAuth } from "../lib/auth";

interface DemoUser { user_id: string; full_name: string; app_role: string; designation: string | null; location: string | null }

export default function Login() {
  const { user, login } = useAuth();
  const nav = useNavigate();
  const { data: users, loading } = useApi<DemoUser[]>("/auth/users");
  const [open, setOpen] = useState<string | null>(null);
  if (user) return <Navigate to="/" replace />;

  const go = async (id: string, password: string) => {
    await login(id, password);
    nav("/");
  };
  const row = (u: DemoUser) => <UserRow key={u.user_id} u={u} open={open === u.user_id}
    onToggle={() => setOpen(open === u.user_id ? null : u.user_id)} onLogin={(p) => go(u.user_id, p)} />;
  const managers = users?.filter((u) => u.app_role === "manager") ?? [];
  const others = users?.filter((u) => u.app_role !== "manager") ?? [];

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <div className="relative hidden overflow-hidden bg-ink-900 p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="absolute -right-32 -top-32 h-96 w-96 rounded-full bg-brand-600/30 blur-3xl" />
        <div className="absolute -bottom-40 left-10 h-96 w-96 rounded-full bg-sky-500/10 blur-3xl" />
        <div className="relative flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-700"><Briefcase className="h-5 w-5" /></div>
          <span className="font-display text-xl font-extrabold">FairDecide <span className="text-brand-400">AI</span></span>
        </div>
        <div className="relative max-w-lg">
          <h1 className="text-4xl font-extrabold leading-tight">Put the right people on the right projects, <span className="text-brand-400">fairly.</span></h1>
          <p className="mt-4 text-lg text-slate-300">Recommendations you can understand, question and override. The AI explains; you decide.</p>
          <div className="mt-10 grid grid-cols-2 gap-4">
            {[
              [Sparkles, "Skill & semantic matching", "Skills, experience and similar past projects"],
              [Eye, "Explainable", "Every score broken into clear factors"],
              [Scale, "Fairness-audited", "Bias measured, corrected and monitored"],
              [ShieldCheck, "Human in the loop", "Nothing happens without your approval"],
            ].map(([Icon, t, d]: any) => (
              <div key={t} className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
                <Icon className="h-5 w-5 text-brand-400" />
                <div className="mt-2 font-semibold">{t}</div>
                <div className="text-sm text-slate-400">{d}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="relative text-xs text-slate-500">Nexora Technologies · synthetic demo data · MSDS Team 17</div>
      </div>

      <div className="flex flex-col justify-center px-6 py-10 sm:px-12">
        <div className="mx-auto w-full max-w-md">
          <h2 className="text-2xl font-extrabold text-slate-900">Sign in</h2>
          <p className="mt-1 text-sm text-slate-500">Choose your name, then enter your password.</p>
          {loading ? <Spinner /> : (
            <>
              <div className="mt-6 text-xs font-semibold uppercase tracking-wider text-slate-400">Project & delivery managers</div>
              <div className="scrollbar-thin mt-2 max-h-[46vh] space-y-2 overflow-y-auto pr-1">
                {managers.map(row)}
              </div>
              <div className="mt-6 text-xs font-semibold uppercase tracking-wider text-slate-400">Administration, HR & audit</div>
              <div className="mt-2 space-y-2">
                {others.map(row)}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function UserRow({ u, open, onToggle, onLogin }: { u: DemoUser; open: boolean; onToggle: () => void; onLogin: (password: string) => Promise<void> }) {
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (open) box.current?.scrollIntoView({ block: "nearest" });
    else { setPassword(""); setError(""); setShow(false); }
  }, [open]);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true); setError("");
    try { await onLogin(password); }
    catch (err: any) { setError(err.message); setPassword(""); setBusy(false); }
  };
  return (
    <div ref={box} className={cn("rounded-xl border bg-white transition", open ? "border-brand-400 ring-4 ring-brand-100" : "border-slate-200 hover:border-brand-300 hover:shadow-md")}>
      <button onClick={onToggle} aria-expanded={open} className="group flex w-full items-center gap-3 p-3 text-left">
        <Avatar name={u.full_name} size={38} />
        <div className="min-w-0 flex-1">
          <div className="font-medium text-slate-800">{u.full_name}</div>
          <div className="truncate text-xs text-slate-500">{u.designation ?? u.app_role.replace("_", " ")}{u.location ? ` · ${u.location}` : ""}</div>
        </div>
        <ArrowRight className={cn("h-4 w-4 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-brand-500", open && "rotate-90 text-brand-500")} />
      </button>
      {open && (
        <form onSubmit={submit} className="px-3 pb-3">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input autoFocus type={show ? "text" : "password"} autoComplete="off" placeholder="Password" aria-label={`Password for ${u.full_name}`}
                className={cn(inputCls, "pr-9", error && "border-rose-400")} value={password} onChange={(e) => { setPassword(e.target.value); setError(""); }} />
              <button type="button" onClick={() => setShow(!show)} aria-label={show ? "Hide password" : "Show password"} className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600">
                {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <Button type="submit" size="sm" loading={busy} disabled={!password}>Sign in</Button>
          </div>
          {error && <div role="alert" className="mt-1.5 text-sm text-rose-600">{error}</div>}
        </form>
      )}
    </div>
  );
}
