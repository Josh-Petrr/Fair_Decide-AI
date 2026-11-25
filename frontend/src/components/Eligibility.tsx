import { AlertTriangle, CheckCircle2, Gauge, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useLive } from "../lib/live";
import { api, useApi, type Approver, type Meta, type RoleView } from "../lib/api";
import { WhatIfPanel, type WhatIfState } from "./Tools";
import { Badge, Button, Empty, LoadBar, Modal, Spinner, cn, inputCls } from "./ui";

interface Result {
  role: RoleView; eligible: boolean; blockers: string[]; warnings: string[]; success_probability: number | null;
  approvers: Approver[]; request_status: string | null; positions_left: number;
  workload: { today: number; on_start: number; after: number; projects_on_start: number; current_projects: { project: string; allocation: number; ends: string }[] };
}

function RequestBox({ result, roleId, employeeId }: { result: Result; roleId: string; employeeId: string }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const { refresh } = useLive();
  const submit = async () => {
    setBusy(true); setError("");
    try { await api("/allocations", { json: { role_id: roleId, employee_ids: [employeeId], reason, source: "eligibility" } }); setSent(true); refresh(); }
    catch (e: any) { setError(e.message); } finally { setBusy(false); }
  };
  if (result.request_status && !sent) return <Badge tone="amber" className="w-full justify-center py-2">A request for this person is already in progress</Badge>;
  if (result.positions_left === 0 && !sent) return <Badge className="w-full justify-center py-2">All positions on this role are taken</Badge>;
  if (sent) return (
    <div className="rounded-2xl bg-emerald-50 p-4 text-sm text-emerald-700">
      <b>Sent for approval.</b> Nothing is assigned or emailed until everyone approves and you send it.
      <Link to="/" className="mt-2 block"><Button variant="secondary" className="w-full">Go to notifications</Button></Link>
    </div>
  );
  return (
    <div className="rounded-2xl border border-slate-200 p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Approval needed from</div>
      {result.approvers.length ? <div className="mt-2 flex flex-wrap gap-1.5">{result.approvers.map((a) => <Badge key={a.user_id} tone="amber">{a.name} · {a.relation}</Badge>)}</div>
        : <div className="mt-2 text-sm text-emerald-600">No approval needed</div>}
      <label className="mt-3 block text-sm font-medium text-slate-700" htmlFor="elig-reason">Why are you requesting this person? <span className="text-rose-500">*</span></label>
      <textarea id="elig-reason" className={cn(inputCls, "mt-1 h-20")} value={reason} onChange={(e) => setReason(e.target.value)}
        placeholder="e.g. Worked with her on the Kafka migration; the client asked for her" />
      <p className="mt-1 text-xs text-slate-500">Approvers see this, and it is kept in the audit trail.</p>
      {error && <div className="mt-1 text-sm text-rose-600">{error}</div>}
      <Button className="mt-2 w-full" loading={busy} disabled={reason.trim().length < 5} onClick={submit}>Request allocation</Button>
    </div>
  );
}

export default function EligibilityDialog({ open, onClose, employeeId, name }: { open: boolean; onClose: () => void; employeeId: string; name: string }) {
  const { data: demands } = useApi<any[]>("/demands");
  const { data: meta } = useApi<Meta>("/meta");
  const mine = useMemo(() => (demands ?? []).filter((d) => d.mine), [demands]);
  const [roleId, setRoleId] = useState("");
  const [base, setBase] = useState<RoleView | null>(null);        // the demand as it really is, for the filters
  const [result, setResult] = useState<Result | null>(null);
  const [changed, setChanged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const run = async (w?: WhatIfState) => {
    setBusy(true); setError("");
    try {
      const r = await api<Result>(`/employees/${employeeId}/eligibility`, { json: { role_id: roleId, ...(w && {
        allocation: w.allocation, start_date: w.start_date, min_experience: w.min_experience, mandatory_certs: w.certs,
        mandatory_skills: w.skills.map((s) => ({ skill_id: s.skill_id, min_level: s.min_level })) }) } });
      setResult(r); setChanged(!!w);
      if (!w) setBase(r.role);
    } catch (e: any) { setError(e.message); } finally { setBusy(false); }
  };
  useEffect(() => {
    setBase(null); setResult(null);
    if (roleId) run();
  }, [roleId]); // eslint-disable-line react-hooks/exhaustive-deps

  const first = name.split(" ")[0];
  const w = result?.workload;
  return (
    <Modal open={open} onClose={onClose} wide title={`Check eligibility · ${name}`}>
      {!demands ? <Spinner /> : mine.length === 0 ? <Empty title="You have no open demands" text="Only demands on projects you head can be checked here." /> : (
        <>
          <label className="text-sm font-medium text-slate-700" htmlFor="elig-role">Your project and role</label>
          <select id="elig-role" className={cn(inputCls, "mt-1")} value={roleId} onChange={(e) => setRoleId(e.target.value)}>
            <option value="">Choose a role…</option>
            {mine.map((d) => <option key={d.project_role_id} value={d.project_role_id}>{d.project_name} · {d.role_title}</option>)}
          </select>
          {error && <div className="mt-3 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}
          {roleId && !result && !error && <Spinner />}
          {base && result && w && (
            <div className="mt-4 grid gap-5 md:grid-cols-2">
              <WhatIfPanel role={base} meta={meta} active={changed} busy={busy} onRun={run} onReset={() => run()}
                title="Requirements" hint="Adjust these to see what would change. Nothing is saved." runLabel="Check again" />
              <div className="space-y-4">
                <div className={cn("rounded-2xl p-4", result.eligible ? "bg-emerald-50" : "bg-rose-50")}>
                  <div className={cn("flex items-center gap-2 font-bold", result.eligible ? "text-emerald-700" : "text-rose-700")}>
                    {result.eligible ? <CheckCircle2 className="h-5 w-5" /> : <XCircle className="h-5 w-5" />}
                    {result.eligible ? `${first} is eligible` : `${first} is not eligible`}
                  </div>
                  {changed && <Badge tone="amber" className="mt-1">With changed requirements</Badge>}
                  {result.blockers.map((b) => <div key={b} className="mt-1 text-sm text-rose-700">• {b}</div>)}
                  {result.success_probability !== null && <div className="mt-1 text-sm text-emerald-700">Predicted success: <b>{Math.round(result.success_probability * 100)}%</b></div>}
                  {result.warnings.map((b) => <div key={b} className="mt-1 flex gap-1.5 text-sm text-amber-700"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />{b}</div>)}
                </div>
                <div className="rounded-2xl border border-slate-200 p-4">
                  <div className="mb-3 flex items-center gap-2 font-bold text-slate-800"><Gauge className="h-4 w-4 text-brand-500" /> Workload</div>
                  <LoadBar now={w.on_start} after={w.after} compact />
                  <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                    {[["Today", w.today], ["On start date", w.on_start], ["If assigned", w.after]].map(([l, v]) => (
                      <div key={l} className="rounded-xl bg-slate-50 py-2">
                        <div className={cn("font-display text-xl font-extrabold", (v as number) > 100 ? "text-rose-600" : "text-slate-900")}>{v}%</div>
                        <div className="text-[11px] text-slate-500">{l}</div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-3 space-y-1 text-sm text-slate-600">
                    {w.current_projects.length === 0 ? "Not on any project today." : w.current_projects.map((p) => <div key={p.project}>{p.project} · {p.allocation}% until {p.ends}</div>)}
                  </div>
                </div>
                {result.eligible && !changed && <RequestBox key={roleId} result={result} roleId={roleId} employeeId={employeeId} />}
                {result.eligible && changed && <p className="text-sm text-slate-500">Reset the requirements to request this person: a request uses the role as it really is.</p>}
              </div>
            </div>
          )}
        </>
      )}
    </Modal>
  );
}
