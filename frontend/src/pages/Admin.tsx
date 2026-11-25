import { ArrowRight, Plus, Search, UserCog, UserPlus, X } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Avatar, Badge, Button, Card, PageHeader, Spinner, cn, fmtDate, inputCls } from "../components/ui";
import { api, useApi, type Meta } from "../lib/api";
import { useLive } from "../lib/live";

interface Pick { employee_id: string; full_name: string; designation?: string }
interface AdminUser {
  user_id: string; full_name: string; app_role: string; is_active: boolean; start_date: string | null; end_date: string | null;
  employee_id: string | null; designation: string | null; reports_to: string | null; projects: number; reports: number; approvals: number;
}

/** Search any current employee by name, ID or skill. */
function PersonPicker({ value, onChange, placeholder = "Search by name or ID…" }: { value: Pick | null; onChange: (p: Pick | null) => void; placeholder?: string }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Pick[]>([]);
  useEffect(() => {
    if (q.length < 2) { setHits([]); return; }
    const t = setTimeout(() => api<Pick[]>(`/employees?q=${encodeURIComponent(q)}`).then((r) => setHits(r.slice(0, 6))), 250);
    return () => clearTimeout(t);
  }, [q]);
  if (value) return (
    <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-sm">
      <Avatar name={value.full_name} size={26} /><span className="flex-1 truncate font-medium">{value.full_name}</span>
      <button onClick={() => onChange(null)} aria-label="Clear" className="text-slate-400 hover:text-slate-600"><X className="h-4 w-4" /></button>
    </div>
  );
  return (
    <div className="relative">
      <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
      <input className={cn(inputCls, "pl-9")} placeholder={placeholder} value={q} onChange={(e) => setQ(e.target.value)} />
      {hits.length > 0 && (
        <div className="absolute z-20 mt-1 w-full overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg">
          {hits.map((h) => (
            <button key={h.employee_id} onClick={() => { onChange(h); setQ(""); }} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-slate-50">
              <Avatar name={h.full_name} size={24} /><span className="flex-1">{h.full_name}</span><span className="text-xs text-slate-400">{h.designation}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

const Field = ({ label, children, wide }: { label: string; children: ReactNode; wide?: boolean }) => (
  <label className={cn("block", wide && "sm:col-span-2")}><span className="text-xs font-medium text-slate-600">{label}</span><div className="mt-1">{children}</div></label>
);
const Result = ({ ok, children }: { ok: boolean; children: ReactNode }) => (
  <div className={cn("mt-3 rounded-xl p-3 text-sm", ok ? "bg-emerald-50 text-emerald-800" : "bg-rose-50 text-rose-700")}>{children}</div>
);
const errText = (e: any) => e.details ? `${e.message}: ${Object.values(e.details).flat().join("; ")}` : e.message;

// ---------------------------------------------------------------- users
function AddManager() {
  const { refresh } = useLive();
  const [mode, setMode] = useState<"promote" | "hire">("promote");
  const [who, setWho] = useState<Pick | null>(null);
  const [start, setStart] = useState("");
  const [title, setTitle] = useState("");
  const [level, setLevel] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: ReactNode } | null>(null);
  const promote = async () => {
    try {
      await api("/admin/managers", { json: { employee_id: who!.employee_id, start_date: start || null, designation: title || null, job_level: level || null } });
      setMsg({ ok: true, text: `${who!.full_name} is now a manager and can sign in.` }); setWho(null); setTitle(""); setLevel(""); refresh();
    } catch (e: any) { setMsg({ ok: false, text: errText(e) }); }
  };
  return (
    <Card className="p-5">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 font-bold text-slate-800"><UserPlus className="h-4 w-4 text-brand-500" /> Add a manager</div>
        <div className="inline-flex rounded-xl bg-slate-100 p-1 text-sm">
          {([["promote", "Promote an employee"], ["hire", "Hire a new manager"]] as const).map(([k, l]) => (
            <button key={k} onClick={() => { setMode(k); setMsg(null); }} className={cn("rounded-lg px-3 py-1", mode === k ? "bg-white font-medium shadow-sm" : "text-slate-500")}>{l}</button>
          ))}
        </div>
      </div>
      {mode === "promote" ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-[1.4fr_1fr_110px_160px_auto] xl:items-end">
            <Field label="Employee"><PersonPicker value={who} onChange={setWho} /></Field>
            <Field label="New title (optional)"><input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Project Manager" /></Field>
            <Field label="New level"><select className={inputCls} value={level} onChange={(e) => setLevel(e.target.value)}><option value="">Same</option>{LEVELS.map((l) => <option key={l}>{l}</option>)}</select></Field>
            <Field label="Manager from"><input type="date" className={inputCls} value={start} onChange={(e) => setStart(e.target.value)} /></Field>
            <Button disabled={!who} onClick={promote}>Promote</Button>
          </div>
          {msg && <Result ok={msg.ok}>{msg.text}</Result>}
        </>
      ) : (
        <EmployeeForm hireManager onDone={refresh} />
      )}
    </Card>
  );
}

function UsersTab({ onHandover }: { onHandover: (u: AdminUser) => void }) {
  const { version } = useLive();
  const { data } = useApi<AdminUser[]>("/admin/users", [version]);
  if (!data) return <Spinner />;
  return (
    <div className="space-y-5">
      <AddManager />
      <Card className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr><th className="px-4 py-3">Login</th><th className="px-3">Role</th><th className="px-3">Manager from</th><th className="px-3">Left on</th>
              <th className="px-3 text-right">Projects</th><th className="px-3 text-right">Reports</th><th className="px-3 text-right">Approvals</th><th className="px-4" /></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.map((u) => (
              <tr key={u.user_id} className={cn(!u.is_active && "text-slate-400")}>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-2.5"><Avatar name={u.full_name} size={30} />
                    <div className="min-w-0">
                      {u.employee_id ? <Link to={`/people/${u.employee_id}`} className="font-medium text-slate-800 hover:text-brand-700">{u.full_name}</Link> : <span className="font-medium text-slate-800">{u.full_name}</span>}
                      <div className="text-xs text-slate-500">{u.designation ?? "-"}{u.reports_to ? ` · reports to ${u.reports_to}` : ""}</div>
                    </div></div>
                </td>
                <td className="px-3"><Badge tone={u.app_role === "admin" ? "red" : u.app_role === "manager" ? "brand" : "gray"}>{u.app_role.replace("_", " ")}</Badge>{!u.is_active && <Badge className="ml-1">inactive</Badge>}</td>
                <td className="px-3">{fmtDate(u.start_date)}</td>
                <td className="px-3">{fmtDate(u.end_date)}</td>
                <td className="px-3 text-right tabular-nums">{u.projects}</td>
                <td className="px-3 text-right tabular-nums">{u.reports}</td>
                <td className="px-3 text-right tabular-nums">{u.approvals}</td>
                <td className="px-4 text-right">{u.is_active && u.app_role === "manager" && <Button size="sm" variant="secondary" onClick={() => onHandover(u)}>Hand over</Button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------- employees
const LEVELS = ["L1", "L2", "L3", "L4", "L5", "L6"];
const blank = { first_name: "", last_name: "", designation: "", job_level: "L2", role_family: "python", location: "", work_mode: "Hybrid",
  date_of_joining: "", prior_experience_years: 0, gender: "" };
const blankManager = { ...blank, designation: "Project Manager", job_level: "L4", role_family: "pm", prior_experience_years: 8 };

/** New employee with skills; with hireManager the login is created too and the joining date is the manager-from date. */
function EmployeeForm({ hireManager, onDone }: { hireManager?: boolean; onDone?: () => void }) {
  const { data: meta } = useApi<Meta>("/meta");
  const start = hireManager ? blankManager : blank;
  const [f, setF] = useState(start);
  const [boss, setBoss] = useState<Pick | null>(null);
  const [skills, setSkills] = useState<{ skill_id: string; level: number }[]>([{ skill_id: "", level: 3 }]);
  const [certs, setCerts] = useState<{ cert_id: string; issue_date: string; expiry_date: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: ReactNode } | null>(null);
  if (!meta) return <Spinner />;
  const families = [...new Map(meta.families.map((x) => [x.role_family, x.practice])).entries()];
  const set = (k: keyof typeof blank, v: string | number) => setF({ ...f, [k]: v });
  const ready = f.first_name && f.last_name && f.designation && f.location && f.date_of_joining && boss && skills.some((s) => s.skill_id);
  const save = async () => {
    setBusy(true); setMsg(null);
    try {
      const r = await api("/admin/employees", { json: { ...f, gender: f.gender || null, reporting_manager_id: boss!.employee_id, make_manager: !!hireManager,
        skills: skills.filter((s) => s.skill_id), certifications: certs.filter((c) => c.cert_id && c.issue_date).map((c) => ({ ...c, expiry_date: c.expiry_date || null })) } });
      setMsg({ ok: true, text: <>{hireManager ? "Hired" : "Added"} {f.first_name} {f.last_name} ({r.email}){hireManager ? ", who can now sign in as a manager" : ""}.{" "}
        <Link to={`/people/${r.employee_id}`} className="font-medium underline">Open profile</Link></> });
      setF(start); setBoss(null); setSkills([{ skill_id: "", level: 3 }]); setCerts([]); onDone?.();
    } catch (e: any) { setMsg({ ok: false, text: errText(e) }); } finally { setBusy(false); }
  };
  return (
    <div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="First name"><input className={inputCls} value={f.first_name} onChange={(e) => set("first_name", e.target.value)} /></Field>
        <Field label="Last name"><input className={inputCls} value={f.last_name} onChange={(e) => set("last_name", e.target.value)} /></Field>
        <Field label="Designation"><input className={inputCls} value={f.designation} onChange={(e) => set("designation", e.target.value)} placeholder="e.g. Data Engineer" /></Field>
        <Field label="Level"><select className={inputCls} value={f.job_level} onChange={(e) => set("job_level", e.target.value)}>{LEVELS.map((l) => <option key={l}>{l}</option>)}</select></Field>
        <Field label="Practice"><select className={inputCls} value={f.role_family} onChange={(e) => set("role_family", e.target.value)}>{families.map(([k, p]) => <option key={k} value={k}>{p}</option>)}</select></Field>
        <Field label="Location"><select className={inputCls} value={f.location} onChange={(e) => set("location", e.target.value)}><option value="">Choose…</option>{meta.locations.map((l) => <option key={l}>{l}</option>)}</select></Field>
        <Field label="Work mode"><select className={inputCls} value={f.work_mode} onChange={(e) => set("work_mode", e.target.value)}>{["Hybrid", "Remote", "Work from Office"].map((m) => <option key={m}>{m}</option>)}</select></Field>
        <Field label={hireManager ? "Joining date (manager from)" : "Joining date"}><input type="date" className={inputCls} value={f.date_of_joining} onChange={(e) => set("date_of_joining", e.target.value)} /></Field>
        <Field label="Experience before joining (years)"><input type="number" min={0} max={40} step={0.5} className={inputCls} value={f.prior_experience_years} onChange={(e) => set("prior_experience_years", +e.target.value)} /></Field>
        <Field label="Gender (fairness audit only, optional)"><select className={inputCls} value={f.gender} onChange={(e) => set("gender", e.target.value)}><option value="">Not recorded</option><option>Female</option><option>Male</option></select></Field>
        <Field label="Reports to" wide><PersonPicker value={boss} onChange={setBoss} placeholder="Search for their manager…" /></Field>
      </div>
      <div className="mt-4 text-xs font-medium text-slate-600">Skills (at least one, so they can be recommended)</div>
      <div className="mt-1 space-y-2">
        {skills.map((s, i) => (
          <div key={i} className="flex gap-2">
            <select className={inputCls} value={s.skill_id} onChange={(e) => setSkills(skills.map((x, j) => j === i ? { ...x, skill_id: e.target.value } : x))} aria-label="Skill">
              <option value="">Choose a skill…</option>{meta.skills.map((k) => <option key={k.skill_id} value={k.skill_id}>{k.skill_name}</option>)}
            </select>
            <select className={cn(inputCls, "w-36!")} value={s.level} onChange={(e) => setSkills(skills.map((x, j) => j === i ? { ...x, level: +e.target.value } : x))} aria-label="Level">
              {[1, 2, 3, 4, 5].map((l) => <option key={l} value={l}>Level {l}</option>)}
            </select>
            <button onClick={() => setSkills(skills.filter((_, j) => j !== i))} className="rounded-lg px-2 text-slate-400 hover:text-rose-500" aria-label="Remove skill"><X className="h-4 w-4" /></button>
          </div>
        ))}
        <Button size="sm" variant="ghost" onClick={() => setSkills([...skills, { skill_id: "", level: 3 }])}><Plus className="h-4 w-4" /> Add skill</Button>
      </div>
      <div className="mt-3 text-xs font-medium text-slate-600">Certifications (optional)</div>
      <div className="mt-1 space-y-2">
        {certs.map((c, i) => (
          <div key={i} className="grid gap-2 sm:grid-cols-[1fr_150px_150px_auto]">
            <select className={inputCls} value={c.cert_id} onChange={(e) => setCerts(certs.map((x, j) => j === i ? { ...x, cert_id: e.target.value } : x))} aria-label="Certification">
              <option value="">Choose…</option>{meta.certifications.map((k) => <option key={k.cert_id} value={k.cert_id}>{k.vendor}: {k.cert_name}</option>)}
            </select>
            <input type="date" className={inputCls} value={c.issue_date} onChange={(e) => setCerts(certs.map((x, j) => j === i ? { ...x, issue_date: e.target.value } : x))} aria-label="Issued" />
            <input type="date" className={inputCls} value={c.expiry_date} onChange={(e) => setCerts(certs.map((x, j) => j === i ? { ...x, expiry_date: e.target.value } : x))} aria-label="Expires" />
            <button onClick={() => setCerts(certs.filter((_, j) => j !== i))} className="rounded-lg px-2 text-slate-400 hover:text-rose-500" aria-label="Remove certification"><X className="h-4 w-4" /></button>
          </div>
        ))}
        <Button size="sm" variant="ghost" onClick={() => setCerts([...certs, { cert_id: "", issue_date: "", expiry_date: "" }])}><Plus className="h-4 w-4" /> Add certification</Button>
      </div>
      <Button className="mt-4 w-full" loading={busy} disabled={!ready} onClick={save}>{hireManager ? "Hire manager" : "Add employee"}</Button>
      {msg && <Result ok={msg.ok}>{msg.text}</Result>}
    </div>
  );
}

function EmployeesTab() {
  const [who, setWho] = useState<Pick | null>(null);
  const [newBoss, setNewBoss] = useState<Pick | null>(null);
  const [moveMsg, setMoveMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const move = async () => {
    try { await api(`/admin/employees/${who!.employee_id}/manager`, { method: "PATCH", json: { reporting_manager_id: newBoss!.employee_id } });
      setMoveMsg({ ok: true, text: `${who!.full_name} now reports to ${newBoss!.full_name}.` }); setWho(null); setNewBoss(null); }
    catch (e: any) { setMoveMsg({ ok: false, text: errText(e) }); }
  };
  return (
    <div className="grid items-start gap-5 xl:grid-cols-[1.6fr_1fr]">
      <Card className="p-5">
        <div className="mb-3 flex items-center gap-2 font-bold text-slate-800"><UserPlus className="h-4 w-4 text-brand-500" /> Add an employee</div>
        <EmployeeForm />
      </Card>
      <Card className="p-5">
        <div className="mb-3 flex items-center gap-2 font-bold text-slate-800"><UserCog className="h-4 w-4 text-brand-500" /> Change who someone reports to</div>
        <div className="space-y-3">
          <Field label="Employee"><PersonPicker value={who} onChange={setWho} /></Field>
          <Field label="New manager"><PersonPicker value={newBoss} onChange={setNewBoss} /></Field>
          <Button className="w-full" disabled={!who || !newBoss} onClick={move}>Save</Button>
        </div>
        {moveMsg && <Result ok={moveMsg.ok}>{moveMsg.text}</Result>}
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------- handover
function HandoverTab({ from, setFrom }: { from: string; setFrom: (id: string) => void }) {
  const { version, refresh } = useLive();
  const { data: users } = useApi<AdminUser[]>("/admin/users", [version]);
  const [to, setTo] = useState<Pick | null>(null);
  const [end, setEnd] = useState("");
  const [preview, setPreview] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  useEffect(() => { setPreview(null); }, [from, to]);       // the result message stays after a handover resets the form
  const managers = (users ?? []).filter((u) => u.is_active && u.app_role === "manager");
  const look = async () => {
    setMsg(null);
    try { setPreview(await api(`/admin/handover/preview?from_user=${from}&to_employee=${to!.employee_id}`)); }
    catch (e: any) { setMsg({ ok: false, text: errText(e) }); }
  };
  const go = async () => {
    setBusy(true);
    try {
      const r = await api("/admin/handover", { json: { from_user: from, to_employee: to!.employee_id, end_date: end || null } });
      setMsg({ ok: true, text: `Done. ${preview.successor} now heads ${r.projects} project(s) and leads ${r.reports} people; ${r.approvals} approval(s), ${r.requests} request(s) and ${r.offers} offer(s) moved. ${preview.leaving}'s login is closed.` });
      setPreview(null); setTo(null); setFrom(""); refresh();
    } catch (e: any) { setMsg({ ok: false, text: errText(e) }); } finally { setBusy(false); }
  };
  const groups: [string, string, (r: any) => string][] = [
    ["projects", "Projects they head", (r) => r.project_name], ["delivery", "Projects they deliver", (r) => r.project_name],
    ["reports", "Direct reports", (r) => r.full_name], ["approvals", "Approvals waiting", (r) => `${r.employee} · ${r.role_title}`],
    ["requests", "Their open requests", (r) => `${r.employee} · ${r.role_title}`], ["offers", "Offers sent to them", () => "Offer"]];
  return (
    <Card className="p-5">
      <p className="mb-4 text-sm text-slate-600">When a manager leaves, everything they are responsible for moves to their successor in one step. Their history stays as it was.</p>
      <div className="grid gap-3 sm:grid-cols-[1fr_auto_1fr_170px] sm:items-end">
        <Field label="Leaving manager">
          <select className={inputCls} value={from} onChange={(e) => setFrom(e.target.value)}>
            <option value="">Choose…</option>{managers.map((u) => <option key={u.user_id} value={u.user_id}>{u.full_name} · {u.designation}</option>)}
          </select>
        </Field>
        <ArrowRight className="mb-2.5 hidden h-5 w-5 text-slate-400 sm:block" />
        <Field label="Successor"><PersonPicker value={to} onChange={setTo} placeholder="Search for the new manager…" /></Field>
        <Field label="Last working day"><input type="date" className={inputCls} value={end} onChange={(e) => setEnd(e.target.value)} /></Field>
      </div>
      <Button className="mt-4" variant="secondary" disabled={!from || !to} onClick={() => { setMsg(null); look(); }}>Preview handover</Button>
      {preview && (
        <div className="mt-4 rounded-2xl border border-slate-200 p-4">
          <div className="text-sm text-slate-700"><b>{preview.leaving}</b> → <b>{preview.successor}</b>{!preview.successor_is_manager && <Badge tone="amber" className="ml-2">will be made a manager</Badge>}</div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {groups.map(([k, label, show]) => (
              <div key={k} className="rounded-xl bg-slate-50 p-3">
                <div className="flex items-center justify-between text-sm"><span className="text-slate-600">{label}</span><b className="tabular-nums text-slate-900">{preview[k].length}</b></div>
                {preview[k].slice(0, 3).map((r: any, i: number) => <div key={i} className="truncate text-xs text-slate-500">{show(r)}</div>)}
                {preview[k].length > 3 && <div className="text-xs text-slate-400">and {preview[k].length - 3} more</div>}
              </div>
            ))}
          </div>
          <Button className="mt-4" loading={busy} onClick={go}>Confirm handover</Button>
        </div>
      )}
      {msg && <Result ok={msg.ok}>{msg.text}</Result>}
    </Card>
  );
}

export default function Admin() {
  const [tab, setTab] = useState<"users" | "employees" | "handover">("users");
  const [from, setFrom] = useState("");
  const tabs = [["users", "Users & managers"], ["employees", "Employees"], ["handover", "Handover"]] as const;
  return (
    <div className="animate-rise">
      <PageHeader eyebrow="Administration" title="Admin" subtitle="Manage logins, managers and employees, and hand over a leaving manager's work." />
      <div className="mb-5 inline-flex rounded-xl bg-slate-100 p-1 text-sm">
        {tabs.map(([k, l]) => <button key={k} onClick={() => setTab(k)} className={cn("rounded-lg px-4 py-1.5", tab === k ? "bg-white font-medium shadow-sm" : "text-slate-500")}>{l}</button>)}
      </div>
      {tab === "users" && <UsersTab onHandover={(u) => { setFrom(u.user_id); setTab("handover"); }} />}
      {tab === "employees" && <EmployeesTab />}
      {tab === "handover" && <HandoverTab from={from} setFrom={setFrom} />}
    </div>
  );
}
