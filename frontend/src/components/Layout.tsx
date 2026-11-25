import { BadgeCheck, Bell, BrainCircuit, Briefcase, ClipboardList, FolderKanban, Inbox, LayoutDashboard, LogOut, PlusCircle, Settings, Users, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { useApi, type Inbox as InboxData } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useLive } from "../lib/live";
import { Avatar, cn, fmtDate } from "./ui";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/demands", label: "Staffing demands", icon: ClipboardList },
  { to: "/new", label: "New project", icon: PlusCircle },
  { to: "/projects", label: "Projects", icon: FolderKanban },
  { to: "/people", label: "People", icon: Users },
  { to: "/audit", label: "Decision audit", icon: BadgeCheck },
  { to: "/model", label: "AI transparency", icon: BrainCircuit },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const { connected, toasts, dismiss, version, last, notify } = useLive();
  const { data: inbox } = useApi<InboxData>("/inbox", [version]);
  const pending = (inbox?.to_approve.length ?? 0) + (inbox?.ready.length ?? 0) + (inbox?.suggestions.length ?? 0);
  const signedInAt = useRef(Date.now());                   // events from before this sign-in are old news
  useEffect(() => {
    if (last?.type === "allocation" && last.at > signedInAt.current && user && last.data.users.includes(user.user_id)) notify({ tone: "info", title: last.data.title });
  }, [last]); // eslint-disable-line react-hooks/exhaustive-deps
  const { data: health } = useApi<{ as_of: string }>("/health");
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col bg-ink-900 px-4 py-6 text-slate-300 lg:flex">
        <div className="mb-8 flex items-center gap-3 px-2">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-700 shadow-lg shadow-brand-600/40">
            <Briefcase className="h-5 w-5 text-white" />
          </div>
          <div>
            <div className="font-display text-lg font-extrabold leading-tight text-white">FairDecide <span className="text-brand-400">AI</span></div>
            <div className="text-[11px] text-slate-400">Trustworthy staffing decisions</div>
          </div>
        </div>
        <nav className="flex-1 space-y-1">
          {[...NAV, ...(user?.app_role === "admin" ? [{ to: "/admin", label: "Admin", icon: Settings, end: false }] : [])].map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end}
              className={({ isActive }) => cn("flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition",
                isActive ? "bg-white/10 font-medium text-white" : "hover:bg-white/5 hover:text-white")}>
              <n.icon className="h-4.5 w-4.5" />{n.label}
            </NavLink>
          ))}
        </nav>
        <div className="rounded-xl bg-white/5 p-3 text-xs leading-relaxed text-slate-400">
          The AI recommends and explains. <span className="text-slate-200">You make every final decision.</span>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200/70 bg-white/80 px-6 py-3 backdrop-blur">
          <div className="flex items-center gap-3 text-sm text-slate-500">
            <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
              connected ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500")}>
              <span className={cn("h-2 w-2 rounded-full", connected ? "animate-pulse bg-emerald-500" : "bg-slate-400")} />
              {connected ? "Live" : "Connecting…"}
            </span>
            {health && <span>Data as of <b className="text-slate-700">{fmtDate(health.as_of)}</b></span>}
          </div>
          <div className="flex items-center gap-3">
            <a href="http://localhost:8025" target="_blank" rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm text-slate-600 hover:bg-slate-100" title="Demo mailbox (Mailpit)">
              <Inbox className="h-4 w-4" /> Demo inbox
            </a>
            <Link to="/" title="Notifications" aria-label="Notifications" className="relative rounded-xl p-2 text-slate-600 hover:bg-slate-100">
              <Bell className="h-5 w-5" />
              {pending > 0 && <span className="absolute -right-0.5 -top-0.5 grid h-5 min-w-5 place-items-center rounded-full bg-rose-500 px-1 text-xs font-bold text-white">{pending}</span>}
            </Link>
            <div className="flex items-center gap-2.5 border-l border-slate-200 pl-3">
              <Avatar name={user?.full_name ?? "?"} size={34} />
              <div className="hidden text-sm leading-tight sm:block">
                <div className="font-medium text-slate-800">{user?.full_name}</div>
                <div className="text-xs capitalize text-slate-500">{user?.app_role.replace("_", " ")}</div>
              </div>
              <button onClick={logout} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600" title="Sign out">
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-6 py-7"><Outlet /></main>
      </div>

      <div className="fixed bottom-5 right-5 z-[60] flex w-80 flex-col gap-2">
        {toasts.map((t) => (
          <div key={t.id} className={cn("flex animate-rise items-start gap-3 rounded-xl border bg-white p-3 shadow-lg",
            t.tone === "success" ? "border-emerald-200" : t.tone === "error" ? "border-rose-200" : "border-slate-200")}>
            <span className={cn("mt-1 h-2 w-2 shrink-0 rounded-full", t.tone === "success" ? "bg-emerald-500" : t.tone === "error" ? "bg-rose-500" : "bg-brand-500")} />
            <div className="min-w-0 flex-1 text-sm">
              <div className="font-medium text-slate-800">{t.title}</div>
              {t.text && <div className="truncate text-slate-500">{t.text}</div>}
            </div>
            <button onClick={() => dismiss(t.id)} className="text-slate-300 hover:text-slate-500"><X className="h-4 w-4" /></button>
          </div>
        ))}
      </div>
    </div>
  );
}
