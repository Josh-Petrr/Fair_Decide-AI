import { ArrowLeft, ArrowRight } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Avatar, Badge, Card, Empty, Spinner, fmtDate } from "../components/ui";
import { useApi } from "../lib/api";
import { useLive } from "../lib/live";

export default function ProjectDetail() {
  const { projectId } = useParams();
  const { version } = useLive();
  const { data, loading } = useApi<any>(`/projects/${projectId}`, [version]);
  if (loading && !data) return <Spinner />;
  if (!data) return <Empty title="Project not found" />;
  const p = data.project;
  return (
    <div className="animate-rise">
      <Link to="/projects" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-brand-600"><ArrowLeft className="h-4 w-4" /> Projects</Link>
      <Card className="p-6">
        <div className="flex flex-wrap gap-2"><Badge tone="brand">{p.status === "Pipeline" ? "New project" : p.status}</Badge><Badge>{p.priority}</Badge><Badge>{p.engagement_model}</Badge></div>
        <h1 className="mt-2 text-2xl font-extrabold text-slate-900">{p.project_name}</h1>
        <div className="text-slate-600">{p.client_name} ({p.country}) · {p.industry} · {p.project_code}</div>
        <p className="mt-3 max-w-4xl text-sm leading-relaxed text-slate-600">{p.description}</p>
        <div className="mt-3 flex flex-wrap gap-x-5 text-sm text-slate-500">
          <span>{fmtDate(p.start_date)} → {fmtDate(p.end_date)}</span><span>Delivery: {p.delivery_location}</span>
          <span>Project manager: {p.project_manager ?? "-"}</span>{p.outcome && <span>Outcome: {p.outcome} · CSAT {p.client_csat}</span>}
        </div>
      </Card>
      <h3 className="mb-3 mt-6 font-bold text-slate-800">Roles & team</h3>
      <div className="space-y-3">
        {data.roles.map((r: any) => {
          const open = ["Open", "Partially Filled"].includes(r.demand_status);
          const people = (r.people ?? []).filter((x: any) => x.status !== "Completed");
          return (
            <Card key={r.project_role_id} className="p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="font-semibold text-slate-800">{r.role_title} <span className="font-normal text-slate-400">× {r.headcount}</span></div>
                  <div className="text-xs text-slate-500">{r.allocation_pct}% · {r.min_experience_years}+ yrs · {fmtDate(r.start_date)} → {fmtDate(r.end_date)} · {r.demand_type}</div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={open ? "amber" : r.demand_status === "Filled" ? "green" : "gray"}>{r.demand_status}</Badge>
                  {open && <Link to={`/demands/${r.project_role_id}`} className="inline-flex items-center gap-1 rounded-xl bg-brand-600 px-3 py-1.5 text-sm text-white hover:bg-brand-700">Find people <ArrowRight className="h-3.5 w-3.5" /></Link>}
                </div>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {(r.skills ?? []).map((s: any) => <Badge key={s.skill} tone={s.importance === "Mandatory" ? "brand" : "gray"}>{s.skill}{s.min ? ` ≥ ${s.min}` : ""}</Badge>)}
              </div>
              {people.length > 0 && <div className="mt-3 flex flex-wrap gap-2">
                {people.map((x: any) => (
                  <Link key={x.employee_id + x.start} to={`/people/${x.employee_id}`} className="flex items-center gap-2 rounded-xl bg-slate-50 px-2 py-1 text-sm hover:bg-brand-50">
                    <Avatar name={x.name} size={24} />{x.name}<span className="text-xs text-slate-400">{x.status}</span>
                  </Link>
                ))}
              </div>}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
