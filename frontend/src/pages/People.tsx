import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Avatar, Badge, Card, Empty, LoadBar, PageHeader, Spinner, cn, inputCls } from "../components/ui";
import { api, useApi, type Meta } from "../lib/api";
import { useLive } from "../lib/live";

export default function People() {
  const { version } = useLive();
  const { data: meta } = useApi<Meta>("/meta");
  const [q, setQ] = useState("");
  const [practice, setPractice] = useState("");
  const [available, setAvailable] = useState(false);
  const [rows, setRows] = useState<any[] | null>(null);
  useEffect(() => {
    const t = setTimeout(() => {
      const ps = new URLSearchParams();
      if (q) ps.set("q", q);
      if (practice) ps.set("practice", practice);
      if (available) ps.set("available", "true");
      api(`/employees?${ps}`).then(setRows);
    }, 250);
    return () => clearTimeout(t);
  }, [q, practice, available, version]);
  const practices = [...new Set(meta?.families.map((f) => f.practice))];

  return (
    <div className="animate-rise">
      <PageHeader eyebrow="Workforce" title="People" subtitle="Search by name or skill; see who is free, busy or over-allocated." />
      <Card className="mb-5 flex flex-wrap items-center gap-3 p-3">
        <div className="relative min-w-64 flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input className={cn(inputCls, "pl-9")} placeholder="Name, ID or skill (e.g. Kafka)…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <select className={cn(inputCls, "w-64")} value={practice} onChange={(e) => setPractice(e.target.value)}>
          <option value="">All practices</option>{practices.map((p) => <option key={p}>{p}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={available} onChange={(e) => setAvailable(e.target.checked)} className="accent-brand-600" /> Has capacity
        </label>
      </Card>
      {!rows ? <Spinner /> : rows.length === 0 ? <Empty title="Nobody matches" /> : (
        <Card className="divide-y divide-slate-100">
          {rows.map((e) => (
            <Link key={e.employee_id} to={`/people/${e.employee_id}`} className="grid grid-cols-[40px_1fr_180px_160px] items-center gap-4 px-5 py-3 hover:bg-slate-50">
              <Avatar name={e.full_name} size={38} />
              <div className="min-w-0">
                <div className="font-medium text-slate-800">{e.full_name} <span className="text-xs font-normal text-slate-400">{e.employee_id}</span></div>
                <div className="truncate text-sm text-slate-500">{e.designation} · {e.primary_skill} · {e.location}</div>
              </div>
              <div>
                {e.employment_status !== "Active" ? <Badge tone="amber">{e.employment_status}</Badge>
                  : <><LoadBar now={e.current_allocation_pct} compact /><div className="mt-1 text-xs text-slate-500">{e.current_allocation_pct}% · {e.active_project_count} project(s)</div></>}
              </div>
              <div className="text-right text-sm text-slate-500">{e.total_experience_years} yrs · {e.job_level}</div>
            </Link>
          ))}
        </Card>
      )}
    </div>
  );
}
