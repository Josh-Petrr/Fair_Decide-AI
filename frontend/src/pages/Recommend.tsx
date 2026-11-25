import { ArrowLeft, Bot, CalendarDays, Columns3, Eye, Filter, FlaskConical, Scale, ShieldCheck, UserX, Users } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import CandidateCard from "../components/CandidateCard";
import { CompareDialog, RejectDialog, RequestDialog, SuggestDialog } from "../components/Dialogs";
import { Assistant, WhatIfPanel, WhyNot, type WhatIfState } from "../components/Tools";
import { Avatar, Badge, Button, Card, Empty, Portal, Spinner, cn, fmtDate } from "../components/ui";
import { api, useApi, type Meta, type RecResult } from "../lib/api";
import { useLive } from "../lib/live";

export default function Recommend() {
  const { roleId = "" } = useParams();
  const { last } = useLive();
  const { data: meta } = useApi<Meta>("/meta");
  const [base, setBase] = useState<RecResult | null>(null);       // the real recommendation (audited)
  const [shown, setShown] = useState<RecResult | null>(null);     // base or a what-if result
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [busyWhatIf, setBusyWhatIf] = useState(false);
  const [dialog, setDialog] = useState<"approve" | "reject" | "compare" | "suggest" | null>(null);
  const [assistant, setAssistant] = useState(false);

  const load = () => api<RecResult>(`/demands/${roleId}/recommendations`)
    .then((r) => { setBase(r); setShown(r); setSelected([]); setError(null); })
    .catch((e) => setError(e.message));
  useEffect(() => { setBase(null); load(); }, [roleId]); // eslint-disable-line react-hooks/exhaustive-deps

  // another manager assigned someone on this demand -> refresh so nobody is double-booked
  useEffect(() => {
    if ((last?.type === "decision" || last?.type === "allocation") && last.data.role_id === roleId && dialog !== "approve") load();
  }, [last]); // eslint-disable-line react-hooks/exhaustive-deps

  if (error) return <Empty title="Could not load recommendations" text={error} />;
  if (!shown || !base) return <Spinner label="Scoring candidates…" />;

  const r = shown.role;
  const whatIf = shown !== base;
  const access = base.access;
  const openRequests = access?.open_requests ?? {};
  const remaining = Math.max(0, base.role.headcount - base.role.filled - Object.keys(openRequests).length);
  const chosen = base.candidates.filter((c) => selected.includes(c.employee_id));
  const toggle = (id: string) => setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]);
  const canAllocate = !!access?.can_allocate;

  const runWhatIf = async (w: WhatIfState) => {
    setBusyWhatIf(true);
    try {
      setShown(await api<RecResult>(`/demands/${roleId}/whatif`, { json: {
        allocation: w.allocation, start_date: w.start_date, min_experience: w.min_experience, mandatory_certs: w.certs,
        mandatory_skills: w.skills.map((s) => ({ skill_id: s.skill_id, min_level: s.min_level })) } }));
    } finally { setBusyWhatIf(false); }
  };

  const reasons = Object.entries(shown.pool.exclusion_reasons).sort((a, b) => b[1] - a[1]);
  const fair = shown.fairness;

  return (
    <div className="animate-rise pb-24">
      <Link to="/demands" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-brand-600"><ArrowLeft className="h-4 w-4" /> All demands</Link>

      {/* demand header */}
      <Card className="relative overflow-hidden p-6">
        <div className="absolute right-0 top-0 h-40 w-72 bg-gradient-to-bl from-brand-100/70 to-transparent" />
        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="brand">{r.project_status === "Pipeline" ? "New project" : "Running project"}</Badge>
              <Badge tone={r.priority === "Critical" ? "red" : r.priority === "High" ? "amber" : "gray"}>{r.priority} priority</Badge>
              <span className="text-sm text-slate-500">{r.client_name} · {r.industry}</span>
            </div>
            <h1 className="mt-2 text-2xl font-extrabold text-slate-900">{r.title}</h1>
            <Link to={`/projects/${r.project_id}`} className="text-slate-600 hover:text-brand-700">{r.project_name}</Link>
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm text-slate-600">
              <span><CalendarDays className="mr-1 inline h-4 w-4 text-slate-400" />{fmtDate(r.start)} → {fmtDate(r.end)}</span>
              <span><Users className="mr-1 inline h-4 w-4 text-slate-400" />{base.role.filled}/{r.headcount} filled</span>
              <span>{r.allocation}% allocation</span><span>{r.min_experience}+ years</span>
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {r.mandatory_skills.map((s) => <Badge key={s.skill} tone="brand">{s.skill} ≥ {s.min_level}</Badge>)}
              {r.preferred_skills.map((s) => <Badge key={s}>{s} (nice)</Badge>)}
              {r.mandatory_certs.map((c) => <Badge key={c} tone="amber">{c}</Badge>)}
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setAssistant(true)}><Bot className="h-4 w-4 text-brand-500" /> Ask assistant</Button>
          </div>
        </div>
      </Card>

      {!canAllocate && (
        <div className="mt-4 flex items-center gap-3 rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">
          <Eye className="h-4 w-4 shrink-0" /> View only. Only the project head, <b>{access?.head}</b>, can allocate people here.
          {access?.can_suggest && <Button size="sm" variant="secondary" className="ml-auto shrink-0" onClick={() => setDialog("suggest")}>I have someone free</Button>}
        </div>
      )}

      {whatIf && (
        <div className="mt-4 flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <FlaskConical className="h-4 w-4" /> What-if mode: results for a modified demand. Eligible changed from <b>{base.pool.eligible}</b> to <b>{shown.pool.eligible}</b>. Reset to approve.
          <button onClick={() => setShown(base)} className="ml-auto font-medium underline">Back to real demand</button>
        </div>
      )}

      <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_340px]">
        <div className="space-y-4">
          {/* funnel */}
          <div className="grid gap-4 md:grid-cols-[1.3fr_1fr]">
            <Card className="p-5">
              <div className="mb-3 flex items-center gap-2 font-bold text-slate-800"><Filter className="h-4 w-4 text-brand-500" /> How the shortlist was built</div>
              <div className="flex items-center gap-2 text-center">
                {[["People considered", shown.pool.considered], ["Passed every rule", shown.pool.eligible], ["Shortlisted", shown.candidates.length]].map(([l, v], i) => (
                  <div key={l} className="flex flex-1 items-center gap-2">
                    <div className={cn("flex-1 rounded-xl py-3", i === 2 ? "bg-brand-600 text-white" : "bg-slate-50")}>
                      <div className="font-display text-2xl font-extrabold">{v}</div>
                      <div className={cn("text-[11px]", i === 2 ? "text-brand-100" : "text-slate-500")}>{l}</div>
                    </div>
                    {i < 2 && <span className="text-slate-300">›</span>}
                  </div>
                ))}
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {reasons.slice(0, 5).map(([k, v]) => <Badge key={k}>{k}: {v}</Badge>)}
              </div>
            </Card>
            <Card className="p-5">
              <div className="mb-2 flex items-center gap-2 font-bold text-slate-800"><Scale className="h-4 w-4 text-brand-500" /> Fairness check</div>
              <div className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
                fair.status === "ok" ? "bg-emerald-50 text-emerald-700" : fair.status.startsWith("review") ? "bg-amber-50 text-amber-800" : "bg-slate-100 text-slate-600")}>
                <ShieldCheck className="h-3.5 w-3.5" />{fair.status === "ok" ? "Balanced shortlist" : fair.status}
              </div>
              {fair.women_in_eligible_pool !== null && (
                <div className="mt-3 space-y-2 text-xs text-slate-600">
                  {[["Eligible pool", fair.women_in_eligible_pool], ["Shortlist", fair.women_in_shortlist ?? 0]].map(([l, v]) => (
                    <div key={l as string}>
                      <div className="mb-0.5 flex justify-between"><span>{l} - women</span><b>{Math.round((v as number) * 100)}%</b></div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full bg-violet-400" style={{ width: `${(v as number) * 100}%` }} /></div>
                    </div>
                  ))}
                </div>
              )}
              <p className="mt-2 text-[11px] text-slate-400">{fair.note}</p>
            </Card>
          </div>

          {/* candidates */}
          {shown.candidates.length === 0 ? (
            <Card><Empty icon={<UserX className="h-5 w-5" />} title="No one meets every requirement"
              text="Look at the near misses below, or relax a requirement in the what-if panel." /></Card>
          ) : shown.candidates.map((c) => (
            <CandidateCard key={c.employee_id} c={c} selected={selected.includes(c.employee_id)} onToggle={() => toggle(c.employee_id)}
              canSelect={!whatIf && canAllocate && selected.length < remaining} requested={openRequests[c.employee_id]} />
          ))}

          {shown.near_misses.length > 0 && (
            <Card className="p-5">
              <div className="mb-1 font-bold text-slate-800">Almost there</div>
              <p className="mb-3 text-sm text-slate-500">Strong people blocked by exactly one rule - worth a conversation.</p>
              <div className="grid gap-2 md:grid-cols-2">
                {shown.near_misses.map((n) => (
                  <Link key={n.employee_id} to={`/people/${n.employee_id}`} className="flex items-center gap-3 rounded-xl border border-slate-200 p-3 hover:border-brand-200">
                    <Avatar name={n.name} size={34} />
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium text-slate-800">{n.name} <span className="font-normal text-slate-400">· {Math.round(n.success_probability * 100)}%</span></div>
                      <div className="truncate text-xs text-rose-600">{n.blocker}</div>
                    </div>
                  </Link>
                ))}
              </div>
            </Card>
          )}
        </div>

        <div className="space-y-4">
          <WhatIfPanel role={base.role} meta={meta} active={whatIf} busy={busyWhatIf} onRun={runWhatIf} onReset={() => setShown(base)} />
          <WhyNot roleId={roleId} />
          <Card className="p-5 text-xs text-slate-500">
            <div className="mb-1 font-semibold text-slate-700">About these scores</div>
            Predicted success comes from a {shown.model.variant} model (test AUC {shown.model.test_auc}). It ranks; it never decides.
            <Link to="/model" className="mt-1 block text-brand-600 hover:underline">See how the model was built and audited →</Link>
          </Card>
        </div>
      </div>

      {/* action bar */}
      {canAllocate && !whatIf && (
        <Portal>
        <div className="fixed bottom-0 left-0 right-0 z-30 border-t border-slate-200 bg-white/90 backdrop-blur lg:left-64">
          <div className="mx-auto flex max-w-[1400px] items-center gap-3 px-6 py-3">
            <div className="flex -space-x-2">{chosen.map((c) => <div key={c.employee_id} className="rounded-full ring-2 ring-white"><Avatar name={c.name} size={32} /></div>)}</div>
            <div className="text-sm text-slate-600">
              {remaining === 0 ? "This demand is fully staffed." : chosen.length ? <><b>{chosen.length}</b> of {remaining} open position(s) selected</>
                : <>Select up to <b>{remaining}</b> candidate(s) to assign</>}
            </div>
            <div className="ml-auto flex gap-2">
              <Button variant="ghost" onClick={() => setDialog("reject")}>Reject</Button>
              <Button variant="secondary" disabled={chosen.length < 2} onClick={() => setDialog("compare")}><Columns3 className="h-4 w-4" /> Compare</Button>
              <Button disabled={!chosen.length} onClick={() => setDialog("approve")}>Request allocation</Button>
            </div>
          </div>
        </div>
        </Portal>
      )}

      <RequestDialog open={dialog === "approve"} onClose={() => { setDialog(null); load(); }} role={base.role} people={chosen} requestId={base.request_id} onDone={() => {}} />
      <RejectDialog open={dialog === "reject"} onClose={() => setDialog(null)} role={base.role} requestId={base.request_id} onDone={load} />
      <SuggestDialog open={dialog === "suggest"} onClose={() => setDialog(null)} roleId={roleId} head={access?.head ?? ""} />
      <CompareDialog open={dialog === "compare"} onClose={() => setDialog(null)} people={chosen} />
      {assistant && <Assistant roleId={roleId} nearMiss={shown.near_misses[0]?.name} onClose={() => setAssistant(false)} />}
    </div>
  );
}
