import { CheckCircle2 } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, type Candidate, type RoleView } from "../lib/api";
import { Avatar, Badge, Button, Empty, LevelDots, Modal, Ring, Spinner, cn, inputCls } from "./ui";

export function RequestDialog({ open, onClose, role, people, requestId, onDone }: {
  open: boolean; onClose: () => void; role: RoleView; people: Candidate[]; requestId?: number; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!open) return;
    setDone(false); setError(null);
    setReason(people.length === 1 ? `Strongest match: ${people[0].explanation.split(";")[0]}` : "");
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async () => {
    setBusy(true); setError(null);
    try {
      await api("/allocations", { json: { role_id: role.role_id, employee_ids: people.map((p) => p.employee_id), reason, notes: notes || null, request_id: requestId } });
      setDone(true);
      onDone();
    } catch (e) { setError(e as ApiError); } finally { setBusy(false); }
  };

  const approvers = (p: Candidate) => p.approvers?.length
    ? <div className="mt-2 flex flex-wrap gap-1.5">{p.approvers.map((a) => <Badge key={a.user_id} tone="amber">{a.name} · {a.relation}</Badge>)}</div>
    : <div className="mt-2 text-xs text-emerald-600">No approval needed</div>;

  if (done) return (
    <Modal open={open} onClose={onClose} title="Request sent"
      footer={<Link to="/"><Button>Go to notifications</Button></Link>}>
      <div className="flex flex-col items-center text-center">
        <div className="grid h-16 w-16 animate-pop place-items-center rounded-full bg-emerald-100"><CheckCircle2 className="h-9 w-9 text-emerald-600" /></div>
        <div className="mt-3 text-lg font-bold text-slate-900">Waiting for approval</div>
        <div className="text-sm text-slate-500">Once everyone approves, you can send it from your notifications. Nothing is assigned or emailed until then.</div>
      </div>
      <div className="mt-5 space-y-2">
        {people.map((p) => <div key={p.employee_id} className="rounded-xl border border-slate-200 p-3 text-sm font-medium text-slate-800">{p.name}{approvers(p)}</div>)}
      </div>
    </Modal>
  );

  return (
    <Modal open={open} onClose={onClose} title={`Request allocation · ${role.title}`}
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button onClick={submit} loading={busy} disabled={reason.trim().length < 5}><CheckCircle2 className="h-4 w-4" /> Send for approval</Button></>}>
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Approval needed from</div>
      <div className="space-y-2">
        {people.map((p) => (
          <div key={p.employee_id} className="rounded-xl border border-slate-200 p-3">
            <div className="flex items-center gap-3">
              <Avatar name={p.name} size={36} />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-slate-800">{p.name}</div>
                <div className="text-xs text-slate-500">Workload {p.workload_on_start}% → {p.workload_after}% · {p.confidence} confidence</div>
              </div>
              <Ring value={p.success_probability} size={44} />
            </div>
            {approvers(p)}
          </div>
        ))}
      </div>
      <div className="mt-4 rounded-xl bg-slate-50 p-3 text-sm text-slate-600">
        <b>{role.project_name}</b><br />{role.start} → {role.end} · {role.allocation}% allocation
      </div>
      <label className="mt-4 block text-sm font-medium text-slate-700">Reason for this decision <span className="text-rose-500">*</span></label>
      <textarea className={cn(inputCls, "mt-1 h-24")} value={reason} onChange={(e) => setReason(e.target.value)}
        placeholder="Why these people? Approvers see this, and it is stored in the audit trail." />
      <input className={cn(inputCls, "mt-2")} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Optional notes" />
      {error && (
        <div className="mt-3 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">
          <b>{error.message}</b>
          {error.details && Object.entries(error.details).map(([n, b]) => <div key={n}>{n}: {b.join("; ")}</div>)}
        </div>
      )}
    </Modal>
  );
}

export function SuggestDialog({ open, onClose, roleId, head }: { open: boolean; onClose: () => void; roleId: string; head: string }) {
  const [people, setPeople] = useState<{ employee_id: string; name: string; designation: string; blockers: string[] }[] | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!open) return;
    setPeople(null); setPicked([]); setNote(""); setSent(false); setError("");
    api(`/demands/${roleId}/bench-team`).then(setPeople);
  }, [open, roleId]);
  const submit = async () => {
    setBusy(true); setError("");
    try { await api("/suggestions", { json: { role_id: roleId, employee_ids: picked, note: note || null } }); setSent(true); }
    catch (e: any) { setError(e.message); } finally { setBusy(false); }
  };
  if (sent) return (
    <Modal open={open} onClose={onClose} title="Notification sent" footer={<Button onClick={onClose}>Done</Button>}>
      <p className="text-sm text-slate-600"><b>{head}</b> will see this in their notifications and can request the allocation.</p>
    </Modal>
  );
  return (
    <Modal open={open} onClose={onClose} title={`Notify ${head}`}
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button loading={busy} disabled={!picked.length} onClick={submit}>Send notification</Button></>}>
      {!people ? <Spinner /> : people.length === 0 ? <Empty title="No free people in your team" text="Nobody reporting to you is on the bench right now." /> : (
        <>
          <p className="mb-3 text-sm text-slate-600">Free people in your team:</p>
          <div className="scrollbar-thin max-h-72 space-y-2 overflow-y-auto">
            {people.map((p) => {
              const on = picked.includes(p.employee_id), blocked = p.blockers.length > 0;
              return (
                <label key={p.employee_id} className={cn("flex items-center gap-3 rounded-xl border p-3", blocked ? "border-slate-100 opacity-60" : on ? "border-brand-400 bg-brand-50/50" : "cursor-pointer border-slate-200")}>
                  <input type="checkbox" disabled={blocked} checked={on} className="accent-brand-600"
                    onChange={() => setPicked(on ? picked.filter((x) => x !== p.employee_id) : [...picked, p.employee_id])} />
                  <Avatar name={p.name} size={34} />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium text-slate-800">{p.name}</div>
                    <div className="truncate text-xs text-slate-500">{blocked ? p.blockers[0] : p.designation}</div>
                  </div>
                </label>
              );
            })}
          </div>
          <input className={cn(inputCls, "mt-3")} maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional message" />
          {error && <div className="mt-2 text-sm text-rose-600">{error}</div>}
        </>
      )}
    </Modal>
  );
}

export function RejectDialog({ open, onClose, role, requestId, onDone }: { open: boolean; onClose: () => void; role: RoleView; requestId?: number; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try {
      await api("/decisions", { json: { role_id: role.role_id, decision: "reject", reason, request_id: requestId } });
      onDone(); onClose();
    } finally { setBusy(false); }
  };
  return (
    <Modal open={open} onClose={onClose} title="Reject this recommendation"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="danger" loading={busy} disabled={reason.trim().length < 5} onClick={submit}>Reject</Button></>}>
      <p className="text-sm text-slate-600">Nobody will be assigned. Your reason is recorded so the decision can be reviewed later.</p>
      <textarea className={cn(inputCls, "mt-3 h-28")} value={reason} onChange={(e) => setReason(e.target.value)}
        placeholder="e.g. Client wants to interview external candidates first" />
    </Modal>
  );
}

export function CompareDialog({ open, onClose, people }: { open: boolean; onClose: () => void; people: Candidate[] }) {
  const rows: [string, (c: Candidate) => ReactNode][] = [
    ["Predicted success", (c) => <Ring value={c.success_probability} size={52} />],
    ["Confidence", (c) => <Badge tone={c.confidence === "High" ? "green" : c.confidence === "Medium" ? "amber" : "red"}>{c.confidence}</Badge>],
    ["Evidence score", (c) => `${Math.round(c.evidence_score * 100)}%`],
    ["Experience", (c) => `${c.experience_years} yrs`],
    ["Industry projects", (c) => c.domain_projects],
    ["Past rating (bias-corrected)", (c) => c.past_rating?.toFixed(2) ?? "No history"],
    ["Workload on start → after", (c) => `${c.workload_on_start}% → ${c.workload_after}%`],
    ["Most similar project", (c) => c.similar_projects[0] ? `${c.similar_projects[0].project} (${Math.round(c.similar_projects[0].similarity * 100)}%)` : "-"],
    ["Skills", (c) => <div className="space-y-1">{c.skills.map((s) => <div key={s.skill} className="flex items-center justify-between gap-2 text-xs"><span>{s.skill}</span><LevelDots level={s.level} required={s.required} /></div>)}</div>],
    ["Top factor", (c) => `${c.factors[0].factor} (${c.factors[0].impact > 0 ? "+" : ""}${c.factors[0].impact})`],
    ["Flags", (c) => c.flags.length ? <span className="text-amber-700">{c.flags.join("; ")}</span> : <span className="text-emerald-600">None</span>],
  ];
  return (
    <Modal open={open} onClose={onClose} wide title="Side-by-side comparison">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr><th className="w-44" />{people.map((p) => <th key={p.employee_id} className="p-2 text-left">
            <div className="flex items-center gap-2"><Avatar name={p.name} size={30} /><div><div className="font-semibold">{p.name}</div><div className="text-xs font-normal text-slate-500">{p.designation}</div></div></div></th>)}</tr></thead>
          <tbody>{rows.map(([label, f]) => (
            <tr key={label} className="border-t border-slate-100 align-top">
              <td className="py-2.5 pr-3 text-slate-500">{label}</td>
              {people.map((p) => <td key={p.employee_id} className="p-2 text-slate-700">{f(p)}</td>)}
            </tr>))}
          </tbody>
        </table>
      </div>
    </Modal>
  );
}
