import { AlertTriangle, ArrowRight, Briefcase, ClipboardList, Rocket, UserCheck, Users } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import Notifications from "../components/Notifications";
import { Avatar, Badge, Card, Empty, Spinner, Stat, cn, fmtDate } from "../components/ui";
import { useApi } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useLive } from "../lib/live";

const SEGMENTS = [
  { key: "free", label: "Free", bar: "bg-emerald-400" },
  { key: "busy", label: "On projects", bar: "bg-brand-400" },
  { key: "over", label: "Overloaded", bar: "bg-rose-500" },
  { key: "away", label: "On leave / exiting", bar: "bg-slate-300" },
] as const;
type Split = Record<(typeof SEGMENTS)[number]["key"], number>;

const split = (total: number, bench: number, over: number, away: number): Split =>
  ({ free: bench, busy: total - bench - over - away, over, away });
const shortDate = (d: string) => fmtDate(d).split(" ").slice(0, 2).join(" ");

function CapacityBar({ s, total, tall }: { s: Split; total: number; tall?: boolean }) {
  return (
    <div className={cn("flex gap-0.5 overflow-hidden rounded-full bg-slate-100", tall ? "h-4" : "h-2")}>
      {SEGMENTS.map((g) => s[g.key] > 0 && <div key={g.key} className={g.bar} style={{ width: `${(s[g.key] / total) * 100}%` }} />)}
    </div>
  );
}

function TeamCapacity({ k, practices }: { k: any; practices: any[] }) {
  const overall = split(k.headcount, k.bench, k.overallocated, k.away);
  return (
    <Card className="p-5">
      <h3 className="mb-4 font-bold text-slate-800">Team capacity</h3>
      <CapacityBar s={overall} total={k.headcount} tall />
      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
        {SEGMENTS.map((g) => (
          <div key={g.key} className="flex items-center gap-2">
            <span className={cn("h-2.5 w-2.5 rounded-full", g.bar)} />
            <span className="truncate text-slate-500">{g.label}</span>
            <b className="ml-auto tabular-nums text-slate-800">{overall[g.key]}</b>
          </div>
        ))}
      </div>
      <div className="mt-5 space-y-0.5 border-t border-slate-100 pt-3">
        {practices.map((p) => (
          <Link key={p.practice} to={`/people?practice=${encodeURIComponent(p.practice)}`}
            title={`${p.people} people: ${p.bench} free, ${p.overallocated} overloaded`}
            className="grid grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_2.25rem] items-center gap-3 rounded-lg px-1.5 py-1.5 text-sm hover:bg-slate-50">
            <span className="truncate text-slate-600">{p.practice}</span>
            <CapacityBar s={split(p.people, p.bench, p.overallocated, p.away)} total={p.people} />
            <b className="text-right tabular-nums text-slate-800">{p.people}</b>
          </Link>
        ))}
      </div>
    </Card>
  );
}

function Activity({ rolloffs, decisions }: { rolloffs: any[]; decisions: any[] }) {
  const [tab, setTab] = useState<"free" | "done">("free");
  const tabCls = (on: boolean) => cn("rounded-lg px-3 py-1.5 text-sm font-medium transition", on ? "bg-white text-slate-800 shadow-sm" : "text-slate-500 hover:text-slate-700");
  return (
    <Card className="p-5">
      <div className="mb-3 inline-flex rounded-xl bg-slate-100 p-1">
        <button className={tabCls(tab === "free")} onClick={() => setTab("free")}>Freeing up soon</button>
        <button className={tabCls(tab === "done")} onClick={() => setTab("done")}>Recent decisions</button>
      </div>
      {tab === "free" ? (rolloffs.length === 0 ? <Empty title="Nobody frees up in the next 30 days" /> : rolloffs.map((r) => (
        <Link key={r.employee_id + r.end_date} to={`/people/${r.employee_id}`} className="flex items-center gap-3 rounded-xl px-2 py-2 hover:bg-slate-50">
          <Avatar name={r.full_name} size={34} />
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium text-slate-800">{r.full_name}</div>
            <div className="truncate text-xs text-slate-500">{r.designation}</div>
          </div>
          <div className="shrink-0 text-right text-sm"><b className="text-slate-800">{shortDate(r.end_date)}</b></div>
        </Link>
      ))) : (decisions.length === 0 ? <Empty title="No decisions yet" /> : decisions.map((d) => (
        <Link key={d.decision_id} to="/audit" className="flex items-center gap-3 rounded-xl px-2 py-2 hover:bg-slate-50">
          <Badge tone={d.decision === "rejected" ? "red" : d.decision === "modified" ? "amber" : "green"}>{d.decision}</Badge>
          <div className="min-w-0 flex-1 truncate text-sm font-medium text-slate-800">{d.role_title}</div>
          <div className="hidden max-w-[40%] truncate text-xs text-slate-500 sm:block">{d.project_name}</div>
        </Link>
      )))}
    </Card>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const { version } = useLive();
  const { data, loading } = useApi<any>("/dashboard", [version]);
  if (loading && !data) return <Spinner label="Loading dashboard" />;
  if (!data) return null;
  const k = data.kpi;
  const pct = (n: number) => `${Math.round((n / k.headcount) * 100)}% of people`;
  const hour = new Date().getHours();
  return (
    <div className="animate-rise">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">Good {hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening"}, {user?.full_name.split(" ")[0]}</h1>
        <Link to="/demands" className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm shadow-brand-600/30 hover:bg-brand-700">
          Start staffing <ArrowRight className="h-4 w-4" /></Link>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat to="/demands" label="Open positions" value={k.open_positions} icon={<ClipboardList className="h-5 w-5" />} />
        <Stat to="/projects?status=Pipeline" label="New projects" value={k.pipeline_projects} icon={<Rocket className="h-5 w-5" />} tone="amber" />
        <Stat to="/projects?status=Active" label="Active projects" value={k.active_projects} icon={<Briefcase className="h-5 w-5" />} tone="blue" />
        <Stat to="/people" label="Utilised people" value={k.headcount - k.bench - k.away} hint={<>of {k.headcount} employees<br />{k.utilisation}% booked</>} icon={<Users className="h-5 w-5" />} />
        <Stat to="/people?load=free" label="Free now" value={k.bench} hint={pct(k.bench)} icon={<UserCheck className="h-5 w-5" />} tone="green" />
        <Stat to="/people?load=over" label="Overloaded" value={k.overallocated} hint="booked over 100%" icon={<AlertTriangle className="h-5 w-5" />} tone="red" />
      </div>

      {user?.app_role === "manager" && <Notifications me={user.user_id} />}

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] items-start gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <div className="space-y-6">
          <Card className="p-5">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="font-bold text-slate-800">Needs people first</h3>
              <Link to="/demands" className="text-sm text-brand-600 hover:underline">View all</Link>
            </div>
            {data.urgent_demands.length === 0 && <Empty title="None of your projects need people right now" />}
            <div className="divide-y divide-slate-100">
              {data.urgent_demands.map((d: any) => (
                <Link key={d.project_role_id} to={`/demands/${d.project_role_id}`} className="group flex items-center gap-3 py-2.5">
                  <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-50 text-sm font-bold text-brand-700">{d.headcount}</div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium text-slate-800 group-hover:text-brand-700">{d.role_title}</div>
                    <div className="truncate text-sm text-slate-500">{d.project_name}</div>
                  </div>
                  {d.priority === "Critical" && <Badge tone="red">Critical</Badge>}
                  <div className="w-14 shrink-0 text-right text-sm font-medium text-slate-600">{shortDate(d.start_date)}</div>
                </Link>
              ))}
            </div>
          </Card>
          <Activity rolloffs={data.rolloffs} decisions={data.recent_decisions} />
        </div>
        <TeamCapacity k={k} practices={data.by_practice} />
      </div>
    </div>
  );
}
