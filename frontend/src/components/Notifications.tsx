import { Check, Clock, Mail, Send, UserPlus, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, useApi, type AllocationItem, type Approver, type Inbox, type Suggestion } from "../lib/api";
import { useLive } from "../lib/live";
import { Avatar, Badge, Button, Card, Modal, cn, fmtDate, inputCls } from "./ui";

/** One chip per approver, so the requester can see whose sign-off is still missing. */
export function ApproverChips({ approvers }: { approvers: Approver[] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {approvers.map((a) => (
        <span key={a.name} title={a.relation} className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
          a.status === "approved" ? "bg-emerald-50 text-emerald-700" : a.status === "rejected" ? "bg-rose-50 text-rose-700" : "bg-amber-50 text-amber-800")}>
          {a.status === "approved" ? <Check className="h-3 w-3" /> : a.status === "rejected" ? <X className="h-3 w-3" /> : <Clock className="h-3 w-3" />}
          {a.name}
        </span>
      ))}
    </div>
  );
}

function Who({ i }: { i: Pick<AllocationItem, "employee_id" | "employee_name" | "project_role_id" | "role_title" | "project_name"> }) {
  return (
    <div className="flex min-w-0 flex-1 items-center gap-3">
      <Avatar name={i.employee_name} size={38} />
      <div className="min-w-0">
        <Link to={`/people/${i.employee_id}`} className="block truncate font-medium text-slate-800 hover:text-brand-700">{i.employee_name}</Link>
        <Link to={`/demands/${i.project_role_id}`} className="block truncate text-sm text-slate-500 hover:text-brand-700">{i.role_title} · {i.project_name}</Link>
      </div>
    </div>
  );
}

const SOURCE = {
  shortlist: ["brand", "From AI shortlist"], eligibility: ["amber", "Hand-picked after eligibility check"], suggestion: ["blue", "Offered by another manager"],
} as const;

function ApprovalRow({ i, me }: { i: AllocationItem; me: string }) {
  const [rejecting, setRejecting] = useState(false);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { refresh } = useLive();
  const relation = i.approvers?.find((a) => a.user_id === me)?.relation.replace("Your manager", `${i.requester}'s manager`).replace("Above", "above");
  const respond = async (approve: boolean) => {
    setBusy(true); setError("");
    try { await api(`/allocations/${i.allocation_id}/respond`, { json: { approve, comment: comment || null } }); refresh(); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };
  return (
    <div className="py-3">
      <div className="flex flex-wrap items-center gap-3">
        <Who i={i} />
        <div className="flex shrink-0 gap-2">
          <Button size="sm" variant="secondary" onClick={() => setRejecting(!rejecting)}>Reject</Button>
          <Button size="sm" loading={busy && !rejecting} onClick={() => respond(true)}><Check className="h-4 w-4" /> Approve</Button>
        </div>
      </div>
      <div className="mt-1.5 pl-[50px] text-sm text-slate-500">
        <b className="font-medium text-slate-700">{i.requester}</b> · {i.allocation_pct}% from {fmtDate(i.start_date)} · now {i.workload}% booked · you are {relation}
        <div className="mt-1 flex flex-wrap items-center gap-2"><Badge tone={SOURCE[i.source][0]}>{SOURCE[i.source][1]}</Badge><span className="italic">"{i.reason}"</span></div>
      </div>
      {rejecting && (
        <div className="mt-2 flex gap-2 pl-[50px]">
          <input autoFocus className={inputCls} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Why are you rejecting this?" />
          <Button size="sm" variant="danger" loading={busy} disabled={comment.trim().length < 5} onClick={() => respond(false)}>Confirm</Button>
        </div>
      )}
      {error && <div className="mt-1 pl-[50px] text-sm text-rose-600">{error}</div>}
    </div>
  );
}

function SuggestionRow({ s }: { s: Suggestion }) {
  const { refresh } = useLive();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const act = async (what: "accept" | "dismiss") => {
    setBusy(true); setError("");
    try { await api(`/suggestions/${s.suggestion_id}/${what}`, { method: "POST" }); refresh(); }
    catch (e: any) { setError(e.message); }
    finally { setBusy(false); }
  };
  return (
    <div className="py-3">
      <div className="flex flex-wrap items-center gap-3">
        <Who i={s} />
        <div className="flex shrink-0 gap-2">
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => act("dismiss")}>Dismiss</Button>
          <Button size="sm" loading={busy} onClick={() => act("accept")}><UserPlus className="h-4 w-4" /> Request allocation</Button>
        </div>
      </div>
      <div className="mt-1.5 pl-[50px] text-sm text-slate-500">
        <b className="font-medium text-slate-700">{s.suggested_by}</b> says {s.employee_name.split(" ")[0]} is free{s.note ? `: "${s.note}"` : ""}
        {s.approvers.length > 0 && <div className="mt-1 flex flex-wrap items-center gap-2">Approval from <ApproverChips approvers={s.approvers} /></div>}
      </div>
      {error && <div className="mt-1 pl-[50px] text-sm text-rose-600">{error}</div>}
    </div>
  );
}

function SendDialog({ item, onClose }: { item: AllocationItem; onClose: () => void }) {
  const { refresh } = useLive();
  const [draft, setDraft] = useState<{ recipient: string | null; subject: string; body: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  useEffect(() => {
    api("/email-preview", { json: { role_id: item.project_role_id, employee_ids: [item.employee_id] } }).then((r) => setDraft(r[0]));
  }, [item]);
  const send = async () => {
    setBusy(true); setError(null);
    try {
      await api(`/allocations/${item.allocation_id}/send`, { json: { emails: draft ? { [item.employee_id]: { subject: draft.subject, body: draft.body } } : null } });
      refresh();
      onClose();
    } catch (e) { setError(e as ApiError); setBusy(false); }
  };
  return (
    <Modal open onClose={onClose} title={`Send to ${item.employee_name}`}
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button loading={busy} disabled={!draft} onClick={send}><Send className="h-4 w-4" /> Send &amp; assign</Button></>}>
      <p className="mb-3 text-sm text-slate-600">Everyone has approved. Sending updates the database and emails {item.employee_name.split(" ")[0]}.</p>
      {draft && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm text-slate-600"><Mail className="h-4 w-4 text-brand-500" />{draft.recipient ?? <span className="text-rose-600">No email on record - please inform them directly</span>}</div>
          <input className={inputCls} value={draft.subject} onChange={(e) => setDraft({ ...draft, subject: e.target.value })} />
          <textarea className={cn(inputCls, "h-56 font-mono text-xs")} value={draft.body} onChange={(e) => setDraft({ ...draft, body: e.target.value })} />
          <p className="text-xs text-slate-400">Emails go to the local demo inbox (Mailpit) - no real email is sent.</p>
        </div>
      )}
      {error && (
        <div className="mt-3 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">
          <b>{error.message}</b>
          {error.details && Object.entries(error.details).map(([n, b]) => <div key={n}>{n}: {b.join("; ")}</div>)}
        </div>
      )}
    </Modal>
  );
}

export default function Notifications({ me }: { me: string }) {
  const { version, refresh } = useLive();
  const { data } = useApi<Inbox>("/inbox", [version]);
  const [picked, setPicked] = useState<"approve" | "suggestions" | "ready" | "waiting" | null>(null);
  const [sending, setSending] = useState<AllocationItem | null>(null);
  if (!data) return null;
  const waiting = [...data.waiting, ...data.rejected];
  const tabs = [["approve", "To approve", data.to_approve.length], ["suggestions", "Suggestions", data.suggestions.length], ["ready", "Ready to send", data.ready.length], ["waiting", "Waiting", waiting.length]] as const;
  const tab = picked ?? tabs.find((t) => t[2] > 0)?.[0] ?? "approve";
  const cancel = (id: number) => api(`/allocations/${id}/cancel`, { method: "POST" }).then(refresh);
  const none = (text: string) => <div className="py-6 text-center text-sm text-slate-400">{text}</div>;
  return (
    <Card className="mt-6 p-5">
      <div className="mb-1 flex flex-wrap items-center gap-3">
        <h3 className="font-bold text-slate-800">Notifications</h3>
        <div className="inline-flex rounded-xl bg-slate-100 p-1">
          {tabs.map(([k, label, n]) => (
            <button key={k} onClick={() => setPicked(k)} className={cn("inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition", tab === k ? "bg-white text-slate-800 shadow-sm" : "text-slate-500 hover:text-slate-700")}>
              {label}
              {n > 0 && <span className={cn("grid h-5 min-w-5 place-items-center rounded-full px-1 text-xs font-bold text-white", k === "waiting" ? "bg-slate-400" : "bg-rose-500")}>{n}</span>}
            </button>
          ))}
        </div>
      </div>
      <div className="divide-y divide-slate-100">
        {tab === "approve" && (data.to_approve.length ? data.to_approve.map((i) => <ApprovalRow key={i.allocation_id} i={i} me={me} />) : none("Nothing waiting for your approval"))}
        {tab === "suggestions" && (data.suggestions.length ? data.suggestions.map((s) => <SuggestionRow key={s.suggestion_id} s={s} />) : none("Other managers can tell you here when they have someone free"))}
        {tab === "ready" && (data.ready.length ? data.ready.map((i) => (
          <div key={i.allocation_id} className="flex flex-wrap items-center gap-3 py-3">
            <Who i={i} />
            <ApproverChips approvers={i.approvers ?? []} />
            <Button size="sm" onClick={() => setSending(i)}><Send className="h-4 w-4" /> Review &amp; send</Button>
          </div>
        )) : none("Approved requests will appear here for you to send"))}
        {tab === "waiting" && (waiting.length ? waiting.map((i) => (
          <div key={i.allocation_id} className="py-3">
            <div className="flex flex-wrap items-center gap-3">
              <Who i={i} />
              <ApproverChips approvers={i.approvers ?? []} />
              {i.status === "pending" && <Button size="sm" variant="ghost" onClick={() => cancel(i.allocation_id)}>Cancel</Button>}
            </div>
            {i.approvers?.filter((a) => a.status === "rejected").map((a) => <div key={a.name} className="mt-1 pl-[50px] text-sm text-rose-600">{a.name}: "{a.comment}"</div>)}
          </div>
        )) : none("Requests you are waiting on will appear here"))}
      </div>
      {sending && <SendDialog item={sending} onClose={() => setSending(null)} />}
    </Card>
  );
}
