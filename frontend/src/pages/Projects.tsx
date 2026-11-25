import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Badge, Card, Empty, PageHeader, Spinner, cn, fmtDate, inputCls } from "../components/ui";
import { api } from "../lib/api";
import { useLive } from "../lib/live";

const STATUS_TONE = { Pipeline: "brand", Active: "green", Completed: "gray" } as const;

export default function Projects() {
  const { version } = useLive();
  const [params] = useSearchParams();
  const [status, setStatus] = useState(params.get("status") ?? "Pipeline");
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<any[] | null>(null);
  useEffect(() => {
    const t = setTimeout(() => {
      const ps = new URLSearchParams();
      if (status) ps.set("status", status);
      if (q) ps.set("q", q);
      api(`/projects?${ps}`).then(setRows);
    }, 200);
    return () => clearTimeout(t);
  }, [status, q, version]);

  return (
    <div className="animate-rise">
      <PageHeader eyebrow="Portfolio" title="Projects" subtitle="New, running and completed engagements." />
      <Card className="mb-5 flex flex-wrap items-center gap-3 p-3">
        <div className="relative min-w-64 flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input className={cn(inputCls, "pl-9")} placeholder="Project, client or code…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="flex rounded-xl bg-slate-100 p-1 text-sm">
          {[["Pipeline", "New"], ["Active", "Running"], ["Completed", "Completed"], ["", "All"]].map(([v, l]) => (
            <button key={l} onClick={() => setStatus(v)} className={cn("rounded-lg px-3 py-1.5", status === v ? "bg-white font-medium shadow-sm" : "text-slate-500")}>{l}</button>
          ))}
        </div>
      </Card>
      {!rows ? <Spinner /> : rows.length === 0 ? <Empty title="No projects" /> : (
        <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {rows.map((p) => (
            <Link key={p.project_id} to={`/projects/${p.project_id}`} className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0"><div className="truncate font-display font-bold text-slate-900">{p.project_name}</div>
                  <div className="text-sm text-slate-500">{p.client_name} · {p.project_code}</div></div>
                <Badge tone={STATUS_TONE[p.status as keyof typeof STATUS_TONE] ?? "gray"}>{p.status === "Pipeline" ? "New" : p.status}</Badge>
              </div>
              <div className="mt-3 text-sm text-slate-500">{p.project_type} · {p.industry}</div>
              <div className="mt-3 flex justify-between text-xs text-slate-500">
                <span>{fmtDate(p.start_date)} → {fmtDate(p.end_date)}</span>
                <span>{p.team_size} people{p.open_demands > 0 && <b className="text-brand-600"> · {p.open_demands} open</b>}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
