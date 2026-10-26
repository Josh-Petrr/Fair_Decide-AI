import { BadgeCheck, ChevronDown, Mail } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Avatar, Badge, Card, Empty, PageHeader, Spinner, cn } from "../components/ui";
import { api, useApi } from "../lib/api";
import { useLive } from "../lib/live";

export default function Audit() {
  const { version } = useLive();
  const { data, loading } = useApi<any[]>("/audit?limit=100", [version]);
  const [open, setOpen] = useState<number | null>(null);
  const [detail, setDetail] = useState<Record<number, any>>({});
  const toggle = async (id: number) => {
    setOpen(open === id ? null : id);
    if (!detail[id]) setDetail({ ...detail, [id]: await api(`/audit/${id}`) });
  };
  return (
    <div className="animate-rise">
      <PageHeader eyebrow="Accountability" title="Decision audit trail"
        subtitle="What the system recommended, what the manager decided, why - and whether the employee was notified. Records are append-only." />
      {loading && !data ? <Spinner /> : !data?.length ? <Card><Empty icon={<BadgeCheck className="h-5 w-5" />} title="No decisions yet" text="Approvals and rejections appear here the moment they are made." /></Card> : (
        <div className="space-y-3">
          {data.map((d) => (
            <Card key={d.decision_id} className="overflow-hidden">
              <button onClick={() => toggle(d.decision_id)} className="flex w-full items-center gap-4 p-4 text-left hover:bg-slate-50">
                <Badge tone={d.decision === "rejected" ? "red" : d.decision === "modified" ? "amber" : "green"}>{d.decision}</Badge>
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium text-slate-800">{d.role_title} · {d.project_name}</div>
                  <div className="truncate text-sm text-slate-500">"{d.decision_reason}"</div>
                </div>
                <div className="text-right text-xs text-slate-500"><div>{d.decided_by}</div><div>{new Date(d.decided_at).toLocaleString("en-IN")}</div></div>
                <ChevronDown className={cn("h-4 w-4 text-slate-400 transition", open === d.decision_id && "rotate-180")} />
              </button>
              {open === d.decision_id && (
                <div className="border-t border-slate-100 bg-slate-50/60 p-5">
                  {!detail[d.decision_id] ? <Spinner /> : <AuditDetail d={detail[d.decision_id]} />}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function AuditDetail({ d }: { d: any }) {
  const chosen: string[] = d.decision.selected_employee_ids ?? [];
  return (
    <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
      <div>
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
          What the system recommended {d.request && <span className="font-normal normal-case">· model {d.request.model_version}</span>}
        </div>
        {d.candidates.length === 0 ? <div className="text-sm text-slate-500">No recommendation was linked to this decision.</div> : (
          <div className="space-y-1.5">
            {d.candidates.map((c: any) => (
              <div key={c.employee_id} className={cn("flex items-center gap-3 rounded-xl px-3 py-2 text-sm", chosen.includes(c.employee_id) ? "bg-emerald-50 ring-1 ring-emerald-200" : "bg-white")}>
                <span className="w-5 text-xs text-slate-400">#{c.rank}</span>
                <Avatar name={c.full_name} size={26} />
                <Link to={`/people/${c.employee_id}`} className="flex-1 font-medium text-slate-700 hover:text-brand-700">{c.full_name}</Link>
                <span className="text-xs text-slate-500">{Math.round(c.match_score * 100)}% · {c.confidence}</span>
                {chosen.includes(c.employee_id) && <Badge tone="green">chosen</Badge>}
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="space-y-4 text-sm">
        <div><div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Reason</div><div className="mt-1 text-slate-700">{d.decision.decision_reason}</div></div>
        {d.decision.notes && <div><div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Notes</div><div className="mt-1 text-slate-700">{d.decision.notes}</div></div>}
        {d.notifications.length > 0 && <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Notifications</div>
          {d.notifications.map((n: any) => (
            <div key={n.notification_id} className="mt-1 flex items-center gap-2 text-slate-700"><Mail className="h-4 w-4 text-slate-400" />
              <span className="flex-1 truncate">{n.recipient ?? "no email"}</span><Badge tone={n.status === "sent" ? "green" : n.status === "failed" ? "red" : "amber"}>{n.status}</Badge></div>
          ))}
        </div>}
      </div>
    </div>
  );
}
