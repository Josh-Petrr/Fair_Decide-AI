import { AlertTriangle, ArrowRight, CalendarClock, ClipboardList, Gauge, Layers, UserMinus } from "lucide-react";
import { Link } from "react-router-dom";
import { Avatar, Badge, Card, Empty, PageHeader, Spinner, Stat, fmtDate } from "../components/ui";
import { useApi } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useLive } from "../lib/live";

export default function Dashboard() {
  const { user } = useAuth();
  const { version } = useLive();
  const { data, loading } = useApi<any>("/dashboard", [version]);
  if (loading && !data) return <Spinner label="Loading dashboard" />;
  if (!data) return null;
  const k = data.kpi;
  const hour = new Date().getHours();
  return (
    <div className="animate-rise">
      <PageHeader eyebrow="Resource management" title={`Good ${hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening"}, ${user?.full_name.split(" ")[0]}`}
        subtitle={`${k.open_positions} open positions across ${k.open_demands} staffing demands need people.`}
        actions={<Link to="/demands" className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm shadow-brand-600/30 hover:bg-brand-700">
          Start staffing <ArrowRight className="h-4 w-4" /></Link>} />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Open positions" value={k.open_positions} hint={`${k.pipeline_projects} new projects in pipeline`} icon={<ClipboardList className="h-5 w-5" />} />
        <Stat label="Utilisation" value={`${k.utilisation}%`} hint={`${k.headcount} people · ${k.active_projects} active projects`} icon={<Gauge className="h-5 w-5" />} tone="green" />
        <Stat label="On the bench" value={k.bench} hint={`${Math.round((k.bench / k.headcount) * 100)}% of workforce available`} icon={<UserMinus className="h-5 w-5" />} tone="blue" />
        <Stat label="Over-allocated" value={k.overallocated} hint={`${k.multi_project} people on 2+ projects`} icon={<AlertTriangle className="h-5 w-5" />} tone="red" />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <Card className="p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-bold text-slate-800">Most urgent demands</h3>
            <Link to="/demands" className="text-sm text-brand-600 hover:underline">View all</Link>
          </div>
          <div className="divide-y divide-slate-100">
            {data.urgent_demands.map((d: any) => (
              <Link key={d.project_role_id} to={`/demands/${d.project_role_id}`} className="group flex items-center gap-4 py-3">
                <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-brand-50 text-sm font-bold text-brand-700">{d.headcount}×</div>
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium text-slate-800 group-hover:text-brand-700">{d.role_title}</div>
                  <div className="truncate text-sm text-slate-500">{d.project_name} · {d.client_name}</div>
                </div>
                <Badge tone={d.priority === "Critical" ? "red" : d.priority === "High" ? "amber" : "gray"}>{d.priority}</Badge>
                <div className="w-24 text-right text-sm text-slate-500"><CalendarClock className="mr-1 inline h-3.5 w-3.5" />{fmtDate(d.start_date)}</div>
              </Link>
            ))}
          </div>
        </Card>

        <Card className="p-5">
          <h3 className="mb-4 font-bold text-slate-800">Utilisation by practice</h3>
          <div className="space-y-3">
            {data.by_practice.map((p: any) => (
              <div key={p.practice}>
                <div className="mb-1 flex justify-between text-sm">
                  <span className="text-slate-600">{p.practice}</span>
                  <span className="text-slate-500"><b className="text-slate-800">{p.utilisation}%</b> · {p.people} people{p.overallocated > 0 && <span className="text-rose-500"> · {p.overallocated} over</span>}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full bg-gradient-to-r from-brand-400 to-brand-600" style={{ width: `${p.utilisation}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <Card className="p-5">
          <h3 className="mb-1 font-bold text-slate-800">Rolling off in the next 30 days</h3>
          <p className="mb-3 text-sm text-slate-500">People becoming available - good candidates for upcoming demands.</p>
          {data.rolloffs.length === 0 ? <Empty title="No roll-offs soon" /> : data.rolloffs.map((r: any) => (
            <Link key={r.employee_id + r.end_date} to={`/people/${r.employee_id}`} className="flex items-center gap-3 rounded-xl px-2 py-2 hover:bg-slate-50">
              <Avatar name={r.full_name} size={34} />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-slate-800">{r.full_name}</div>
                <div className="truncate text-xs text-slate-500">{r.designation} · {r.project_name}</div>
              </div>
              <Badge tone="blue">frees {r.allocation_pct}% on {fmtDate(r.end_date)}</Badge>
            </Link>
          ))}
        </Card>
        <Card className="p-5">
          <h3 className="mb-1 font-bold text-slate-800">Recent decisions</h3>
          <p className="mb-3 text-sm text-slate-500">Every approval and rejection is recorded with its reason.</p>
          {data.recent_decisions.length === 0 ? <Empty icon={<Layers className="h-5 w-5" />} title="No decisions yet" text="Approve a recommendation and it will appear here instantly." /> :
            data.recent_decisions.map((d: any) => (
              <Link key={d.decision_id} to="/audit" className="flex items-center gap-3 rounded-xl px-2 py-2 hover:bg-slate-50">
                <Badge tone={d.decision === "rejected" ? "red" : d.decision === "modified" ? "amber" : "green"}>{d.decision}</Badge>
                <div className="min-w-0 flex-1 text-sm">
                  <div className="truncate font-medium text-slate-800">{d.role_title} · {d.project_name}</div>
                  <div className="truncate text-xs text-slate-500">{d.decided_by} - "{d.decision_reason}"</div>
                </div>
              </Link>
            ))}
        </Card>
      </div>
    </div>
  );
}
