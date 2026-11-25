import { CalendarDays, ClipboardList, Search, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Card, Empty, PageHeader, Spinner, cn, fmtDate, inputCls } from "../components/ui";
import { useApi } from "../lib/api";
import { useLive } from "../lib/live";

interface Demand {
  project_role_id: string; role_title: string; role_family: string; headcount: number; filled: number; allocation_pct: number;
  min_experience_years: number; start_date: string; end_date: string; demand_type: string; project_name: string; project_id: string;
  priority: string; project_status: string; client_name: string; skills: string | null; mine: boolean; head_name: string;
}

export default function Demands() {
  const { version } = useLive();
  const { data, loading } = useApi<Demand[]>("/demands", [version]);
  const [q, setQ] = useState("");
  const [kind, setKind] = useState<"all" | "new" | "running">("all");
  const [priority, setPriority] = useState("all");
  const [picked, setPicked] = useState<"mine" | "all" | null>(null);
  const scope = picked ?? (data?.some((d) => d.mine) ? "mine" : "all");
  const scopes = [["mine", "My projects"], ["all", "All projects"]] as const;

  const list = useMemo(() => (data ?? []).filter((d) =>
    (kind === "all" || (kind === "new" ? d.project_status === "Pipeline" : d.project_status !== "Pipeline")) &&
    (priority === "all" || d.priority === priority) && (scope === "mine") === !!d.mine &&
    (!q || `${d.role_title} ${d.project_name} ${d.client_name} ${d.skills}`.toLowerCase().includes(q.toLowerCase()))), [data, q, kind, priority, scope]);

  return (
    <div className="animate-rise">
      <PageHeader eyebrow="Staffing" title="Open staffing demands"
        subtitle="Each demand is a role that needs people. Open one to get explained, fairness-checked recommendations."
        actions={<Link to="/new" className="inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-medium text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50">
          <Sparkles className="h-4 w-4 text-brand-500" /> New project</Link>} />

      <Card className="mb-5 flex flex-wrap items-center gap-3 p-3">
        <div className="relative min-w-full flex-1 sm:min-w-64">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input className={cn(inputCls, "pl-9")} placeholder="Search role, project, client or skill…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="flex flex-wrap rounded-xl bg-slate-100 p-1 text-sm">
          {scopes.map(([k, label]) => (
            <button key={k} onClick={() => setPicked(k)} className={cn("rounded-lg px-3 py-1.5", scope === k ? "bg-white font-medium shadow-sm" : "text-slate-500")}>{label}</button>
          ))}
        </div>
        <select className={cn(inputCls, "w-44!")} value={kind} onChange={(e) => setKind(e.target.value as typeof kind)} aria-label="Project type">
          <option value="all">Any project</option><option value="new">New projects</option><option value="running">Running projects</option>
        </select>
        <select className={cn(inputCls, "w-36!")} value={priority} onChange={(e) => setPriority(e.target.value)}>
          <option value="all">Any priority</option>{["Critical", "High", "Medium", "Low"].map((p) => <option key={p}>{p}</option>)}
        </select>
      </Card>

      {loading && !data ? <Spinner /> : list.length === 0 ? <Empty icon={<ClipboardList className="h-5 w-5" />} title={scope === "mine" ? "None of your projects match" : "No matching demands"} /> : (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {list.map((d) => (
            <Link key={d.project_role_id} to={`/demands/${d.project_role_id}`}
              className="group rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-brand-200 hover:shadow-md">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate font-display text-[17px] font-bold text-slate-900 group-hover:text-brand-700">{d.role_title}</div>
                  <div className="truncate text-sm text-slate-500">{d.project_name}</div>
                </div>
                <div className="flex shrink-0 gap-1">
                  {d.mine && <Badge tone="green">Your project</Badge>}
                  <Badge tone={d.priority === "Critical" ? "red" : d.priority === "High" ? "amber" : "gray"}>{d.priority}</Badge>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {(d.skills ?? "").split(", ").filter(Boolean).slice(0, 5).map((s) => <Badge key={s} tone="brand">{s}</Badge>)}
              </div>
              <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
                <span className="truncate">{d.mine ? d.client_name : `Head: ${d.head_name}`}</span>
                <span className="inline-flex items-center gap-1"><CalendarDays className="h-3.5 w-3.5" />{fmtDate(d.start_date)}</span>
              </div>
              <div className="mt-3 flex items-center gap-3">
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full bg-emerald-500" style={{ width: `${(d.filled / d.headcount) * 100}%` }} />
                </div>
                <span className="text-xs font-medium text-slate-600">{d.filled}/{d.headcount} filled</span>
                <span className="text-xs text-slate-400">· {d.allocation_pct}% · {d.min_experience_years}+ yrs</span>
              </div>
              {d.demand_type !== "Initial" && <Badge tone="blue" className="mt-3">{d.demand_type} on running project</Badge>}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
