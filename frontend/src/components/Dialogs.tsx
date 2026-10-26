import { CheckCircle2, ChevronDown, Clock, Database, Mail, XCircle } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, type Candidate, type RoleView } from "../lib/api";
import { useLive } from "../lib/live";
import { Avatar, Badge, Button, LevelDots, Modal, Ring, cn, inputCls } from "./ui";

interface EmailDraft { employee_id: string; recipient: string | null; subject: string; body: string }

export function ApproveDialog({ open, onClose, role, people, requestId, onDone }: {
  open: boolean; onClose: () => void; role: RoleView; people: Candidate[]; requestId?: number; onDone: () => void }) {
  const { last } = useLive();
  const [drafts, setDrafts] = useState<EmailDraft[]>([]);
  const [openMail, setOpenMail] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [result, setResult] = useState<{ assignments: string[]; notifications: number[]; notification_of: Record<string, number>; decision: string } | null>(null);
  const [mailStatus, setMailStatus] = useState<Record<number, string>>({});

  useEffect(() => {
    if (!open) return;
    setResult(null); setError(null); setMailStatus({});
    setReason(people.length === 1 ? `Strongest match: ${people[0].explanation.split(";")[0]}` : "");
    api<EmailDraft[]>("/email-preview", { json: { role_id: role.role_id, employee_ids: people.map((p) => p.employee_id) } }).then(setDrafts);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {   // live delivery status from the server
    if (last?.type === "notification" && result?.notifications.includes(last.data.notification_id))
      setMailStatus((s) => ({ ...s, [last.data.notification_id]: last.data.status }));
  }, [last, result]);

  const submit = async () => {
    setBusy(true); setError(null);
    try {
      const r = await api("/decisions", { json: {
        role_id: role.role_id, decision: "approve", employee_ids: people.map((p) => p.employee_id), reason, notes: notes || null,
        request_id: requestId, emails: Object.fromEntries(drafts.map((d) => [d.employee_id, { subject: d.subject, body: d.body }])) } });
      setResult(r);
      onDone();
    } catch (e) { setError(e as ApiError); } finally { setBusy(false); }
  };

  if (result) return (
    <Modal open={open} onClose={onClose} title="Assignment complete"
      footer={<><Link to="/audit" className="rounded-xl px-4 py-2.5 text-sm text-slate-600 hover:bg-slate-100">View audit trail</Link>
        <Link to="/demands"><Button>Back to demands</Button></Link></>}>
      <div className="flex flex-col items-center text-center">
        <div className="grid h-16 w-16 animate-pop place-items-center rounded-full bg-emerald-100"><CheckCircle2 className="h-9 w-9 text-emerald-600" /></div>
        <div className="mt-3 text-lg font-bold text-slate-900">{people.length} {people.length === 1 ? "person" : "people"} assigned to {role.title}</div>
        <div className="text-sm text-slate-500">Decision recorded as <b>{result.decision}</b> with your reason.</div>
      </div>
      <div className="mt-6 space-y-2">
        <Step icon={<Database className="h-4 w-4" />} done text={`Database updated: ${result.assignments.join(", ")}, demand status, audit log`} />
        {drafts.map((d) => {
          const id = result.notification_of[d.employee_id];
          const st = !d.recipient ? "failed" : mailStatus[id] ?? "queued";
          const name = people.find((p) => p.employee_id === d.employee_id)?.name;
          return <Step key={d.employee_id} icon={<Mail className="h-4 w-4" />} done={st === "sent"} failed={st === "failed"}
            text={!d.recipient ? `${name}: no email on record - please inform them directly`
              : st === "failed" ? `Email to ${d.recipient} failed - mail server unavailable`
              : `Email to ${d.recipient}: ${st === "sent" ? "delivered" : "sending…"}`} />;
        })}
      </div>
    </Modal>
  );

  return (
    <Modal open={open} onClose={onClose} wide title={`Approve & assign · ${role.title}`}
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button onClick={submit} loading={busy} disabled={reason.trim().length < 5}><CheckCircle2 className="h-4 w-4" /> Confirm assignment</Button></>}>
      <div className="grid gap-6 md:grid-cols-[1fr_1.2fr]">
        <div>
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">You are assigning</div>
          <div className="space-y-2">
            {people.map((p) => (
              <div key={p.employee_id} className="flex items-center gap-3 rounded-xl border border-slate-200 p-3">
                <Avatar name={p.name} size={36} />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-slate-800">{p.name}</div>
                  <div className="text-xs text-slate-500">Workload {p.workload_on_start}% → {p.workload_after}% · {p.confidence} confidence</div>
                </div>
                <Ring value={p.success_probability} size={44} />
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-xl bg-slate-50 p-3 text-sm text-slate-600">
            <b>{role.project_name}</b><br />{role.start} → {role.end} · {role.allocation}% allocation
          </div>
          <label className="mt-4 block text-sm font-medium text-slate-700">Reason for this decision <span className="text-rose-500">*</span></label>
          <textarea className={cn(inputCls, "mt-1 h-24")} value={reason} onChange={(e) => setReason(e.target.value)}
            placeholder="Why these people? This is stored in the audit trail." />
          <input className={cn(inputCls, "mt-2")} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Optional notes" />
          {error && (
            <div className="mt-3 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">
              <b>{error.message}</b>
              {error.details && Object.entries(error.details).map(([n, b]) => <div key={n}>{n}: {b.join("; ")}</div>)}
            </div>
          )}
        </div>
        <div>
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Notification emails (editable)</div>
          <div className="space-y-2">
            {drafts.map((d, i) => (
              <div key={d.employee_id} className="rounded-xl border border-slate-200">
                <button onClick={() => setOpenMail(openMail === d.employee_id ? null : d.employee_id)} className="flex w-full items-center gap-2 p-3 text-left text-sm">
                  <Mail className="h-4 w-4 text-brand-500" />
                  <span className="flex-1 truncate">{d.recipient ?? <span className="text-rose-600">No email on record</span>}</span>
                  <ChevronDown className={cn("h-4 w-4 text-slate-400 transition", openMail === d.employee_id && "rotate-180")} />
                </button>
                {openMail === d.employee_id && (
                  <div className="space-y-2 border-t border-slate-100 p-3">
                    <input className={inputCls} value={d.subject} onChange={(e) => setDrafts(drafts.map((x, j) => j === i ? { ...x, subject: e.target.value } : x))} />
                    <textarea className={cn(inputCls, "h-56 font-mono text-xs")} value={d.body}
                      onChange={(e) => setDrafts(drafts.map((x, j) => j === i ? { ...x, body: e.target.value } : x))} />
                  </div>
                )}
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-slate-400">Emails go to the local demo inbox (Mailpit) - no real email is sent.</p>
        </div>
      </div>
    </Modal>
  );
}

function Step({ icon, text, done, failed }: { icon: ReactNode; text: string; done?: boolean; failed?: boolean }) {
  return (
    <div className={cn("flex items-center gap-3 rounded-xl border p-3 text-sm", done ? "border-emerald-200 bg-emerald-50/50" : failed ? "border-rose-200 bg-rose-50/50" : "border-slate-200")}>
      <span className="text-slate-500">{icon}</span>
      <span className="flex-1 text-slate-700">{text}</span>
      {done ? <CheckCircle2 className="h-5 w-5 text-emerald-500" /> : failed ? <XCircle className="h-5 w-5 text-rose-500" /> : <Clock className="h-5 w-5 animate-pulse text-slate-400" />}
    </div>
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
