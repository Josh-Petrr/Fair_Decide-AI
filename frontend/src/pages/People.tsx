import { Search, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Avatar, Badge, Card, Empty, LoadBar, PageHeader, Spinner, cn, inputCls } from "../components/ui";
import { api, useApi, type Meta } from "../lib/api";
import { useLive } from "../lib/live";

export default function People() {
  const { version } = useLive();
  const { data: meta } = useApi<Meta>("/meta");
  const [params, setParams] = useSearchParams();
  const load = params.get("load");
  const [q, setQ] = useState("");
  const [practice, setPractice] = useState(params.get("practice") ?? "");
  const [available, setAvailable] = useState(false);
  const [rows, setRows] = useState<any[] | null>(null);
  const [picked, setPicked] = useState<"mine" | "others" | null>(null);
  // a dashboard link asks for specific people, so it starts across the whole company
  const scope = picked ?? (load || params.get("practice") || !meta ? null : meta.team_size > 0 ? "mine" : "others");
  const scopes = [["mine", "My team"], ["others", "All employees"]] as const;
  useEffect(() => {
    const t = setTimeout(() => {
      const ps = new URLSearchParams();
      if (q) ps.set("q", q);
      if (practice) ps.set("practice", practice);
      if (available) ps.set("available", "true");
      if (load) ps.set("load", load);
      if (scope && !q) ps.set("scope", scope);      // the tabs list teams; search always covers everyone
      api(`/employees?${ps}`).then(setRows);
    }, 250);
    return () => clearTimeout(t);
  }, [q, practice, available, load, scope, version]);
  const practices = [...new Set(meta?.families.map((f) => f.practice))];

  return (
    <div className="animate-rise">
      <PageHeader eyebrow="Workforce" title="People" subtitle="Search by name or skill; see who is free, busy or over-allocated." />
      <Card className="mb-5 flex flex-wrap items-center gap-3 p-3">
        <div className="relative min-w-full flex-1 sm:min-w-64">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input className={cn(inputCls, "pl-9")} placeholder="Search everyone by name, ID or skill…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="flex rounded-xl bg-slate-100 p-1 text-sm">
          {scopes.map(([k, label]) => (
            <button key={k} onClick={() => setPicked(k)} className={cn("rounded-lg px-3 py-1.5", scope === k && !q ? "bg-white font-medium shadow-sm" : "text-slate-500")}>{label}</button>
          ))}
        </div>
        <select className={cn(inputCls, "sm:w-64!")} value={practice} onChange={(e) => setPractice(e.target.value)}>
          <option value="">All practices</option>{practices.map((p) => <option key={p}>{p}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={available} onChange={(e) => setAvailable(e.target.checked)} className="accent-brand-600" /> Has capacity
        </label>
        {load && <button onClick={() => setParams({})} className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-3 py-1 text-sm text-brand-700 hover:bg-brand-100">
          {load === "free" ? "Free now" : "Overloaded"} <X className="h-3.5 w-3.5" /></button>}
      </Card>
      {!rows ? <Spinner /> : rows.length === 0 ? <Empty title={scope === "mine" && meta?.team_size === 0 ? "Nobody reports to you" : "Nobody matches"} /> : (
        <Card className="divide-y divide-slate-100">
          {rows.map((e) => (
            <Link key={e.employee_id} to={`/people/${e.employee_id}`} className="grid grid-cols-[40px_minmax(0,1fr)] items-center gap-x-4 gap-y-2 px-5 py-3 hover:bg-slate-50 md:grid-cols-[40px_minmax(0,1fr)_180px_160px]">
              <Avatar name={e.full_name} size={38} />
              <div className="min-w-0">
                <div className="font-medium text-slate-800">{e.full_name} <span className="text-xs font-normal text-slate-400">{e.employee_id}</span></div>
                <div className="truncate text-sm text-slate-500">{e.designation} · {e.primary_skill} · {e.location}</div>
              </div>
              <div className="col-start-2 md:col-start-auto">
                {e.employment_status !== "Active" ? <Badge tone="amber">{e.employment_status}</Badge>
                  : <><LoadBar now={e.current_allocation_pct} compact /><div className="mt-1 text-xs text-slate-500">{e.current_allocation_pct}% · {e.active_project_count} project(s)</div></>}
              </div>
              <div className="hidden text-right text-sm text-slate-500 md:block">{e.total_experience_years} yrs · {e.job_level}</div>
            </Link>
          ))}
          {rows.length === 200 && <div className="px-5 py-3 text-center text-sm text-slate-500">Showing the first 200. Search or filter to narrow this down.</div>}
        </Card>
      )}
    </div>
  );
}
