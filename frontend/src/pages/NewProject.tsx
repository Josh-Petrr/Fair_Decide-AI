import { ArrowRight, Plus, Sparkles, Trash2, Wand2, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Badge, Button, Card, PageHeader, Spinner, cn, inputCls } from "../components/ui";
import { api, useApi, type Meta } from "../lib/api";
import { useLive } from "../lib/live";

interface RoleForm {
  title: string; family: string; headcount: number; min_experience: number; allocation: number;
  mandatory_skills: { skill_id: string; min_level: number }[]; preferred_skills: string[]; mandatory_certs: string[]; preferred_certs: string[];
}
const blankRole = (): RoleForm => ({ title: "", family: "java", headcount: 1, min_experience: 3, allocation: 100,
  mandatory_skills: [], preferred_skills: [], mandatory_certs: [], preferred_certs: [] });

const EXAMPLES = [
  "Need 2 senior Java developers with Spring Boot, Kafka and PostgreSQL, 6+ years, from January for 8 months. Payments experience and Redis are nice to have.",
  "Looking for one QA automation engineer with Selenium and REST Assured, 3 years, 50% allocation, starting 15 Dec. ISTQB preferred, Playwright a plus.",
  "A data scientist for a GenAI customer-care chatbot using LangChain, RAG and Python, 3+ years, from February.",
];

export default function NewProject() {
  const nav = useNavigate();
  const { notify } = useLive();
  const { data: meta } = useApi<Meta>("/meta");
  const [text, setText] = useState("");
  const [parsing, setParsing] = useState(false);
  const [source, setSource] = useState<string | null>(null);
  const [step, setStep] = useState<"describe" | "form">("describe");
  const [p, setP] = useState({ project_name: "", client_id: "", description: "", priority: "High", delivery_location: "Bengaluru",
    project_type: "New Development", start_date: "", end_date: "" });
  const [roles, setRoles] = useState<RoleForm[]>([blankRole()]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!meta) return <Spinner />;

  const read = async () => {
    setParsing(true);
    try {
      const r = await api("/assistant/parse", { json: { text } });
      const q = r.requirements;
      setSource(r.source);
      setP((x) => ({ ...x, description: text, start_date: q.start_date, end_date: q.end_date }));
      setRoles([{ title: q.title, family: q.family, headcount: q.headcount, min_experience: q.min_experience, allocation: q.allocation,
        mandatory_skills: q.mandatory_skills.map((s: any) => ({ skill_id: s.skill_id, min_level: s.min_level })),
        preferred_skills: q.preferred_skills, mandatory_certs: q.mandatory_certs, preferred_certs: q.preferred_certs }]);
      setStep("form");
    } finally { setParsing(false); }
  };

  const save = async () => {
    setSaving(true); setError(null);
    try {
      const r = await api("/projects", { json: { ...p, roles } });
      notify({ tone: "success", title: "Project created", text: `${r.project_code} · ${r.role_ids.length} demand(s)` });
      nav(`/demands/${r.role_ids[0]}`);
    } catch (e: any) { setError(e.message); } finally { setSaving(false); }
  };

  const valid = p.project_name.length >= 3 && p.client_id && p.description.length >= 10 && p.start_date && p.end_date > p.start_date &&
    roles.every((r) => r.title && r.mandatory_skills.length > 0);
  const setRole = (i: number, patch: Partial<RoleForm>) => setRoles(roles.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  if (step === "describe") return (
    <div className="mx-auto max-w-3xl animate-rise">
      <PageHeader eyebrow="New project" title="What do you need?" subtitle="Describe the people you need in plain English - the assistant turns it into structured requirements you can check." />
      <Card className="p-6">
        <textarea className={cn(inputCls, "h-36 text-base")} value={text} onChange={(e) => setText(e.target.value)}
          placeholder="e.g. Need 2 senior Java developers with Spring Boot and Kafka, 6+ years, from January…" />
        <div className="mt-3 flex flex-wrap gap-2">
          {EXAMPLES.map((e) => <button key={e} onClick={() => setText(e)} className="rounded-full bg-slate-100 px-3 py-1 text-left text-xs text-slate-600 hover:bg-brand-50 hover:text-brand-700">{e.slice(0, 60)}…</button>)}
        </div>
        <div className="mt-5 flex items-center justify-between">
          <button onClick={() => setStep("form")} className="text-sm text-slate-500 hover:text-brand-600">Fill in a form instead</button>
          <Button onClick={read} loading={parsing} disabled={text.trim().length < 10}><Wand2 className="h-4 w-4" /> Read my request</Button>
        </div>
      </Card>
    </div>
  );

  return (
    <div className="mx-auto max-w-5xl animate-rise">
      <PageHeader eyebrow="New project" title="Confirm the requirements"
        subtitle="Check what was understood, adjust anything, then create the project to get recommendations."
        actions={source && <Badge tone={source === "groq" ? "brand" : "gray"}><Sparkles className="h-3 w-3" />{source === "groq" ? "Read by AI (Groq)" : "Read by rule engine"}</Badge>} />

      <Card className="p-6">
        <h3 className="mb-4 font-bold text-slate-800">Project</h3>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Project name"><input className={inputCls} value={p.project_name} onChange={(e) => setP({ ...p, project_name: e.target.value })} placeholder="e.g. UPI AutoPay Mandate Platform" /></Field>
          <Field label="Client">
            <select className={inputCls} value={p.client_id} onChange={(e) => setP({ ...p, client_id: e.target.value })}>
              <option value="">Choose client…</option>{meta.clients.map((c) => <option key={c.client_id} value={c.client_id}>{c.client_name} · {c.industry}</option>)}
            </select>
          </Field>
          <Field label="Description (used for semantic matching with past projects)" wide>
            <textarea className={cn(inputCls, "h-24")} value={p.description} onChange={(e) => setP({ ...p, description: e.target.value })} />
          </Field>
          <Field label="Start date"><input type="date" className={inputCls} value={p.start_date} onChange={(e) => setP({ ...p, start_date: e.target.value })} /></Field>
          <Field label="End date"><input type="date" className={inputCls} value={p.end_date} onChange={(e) => setP({ ...p, end_date: e.target.value })} /></Field>
          <Field label="Priority"><select className={inputCls} value={p.priority} onChange={(e) => setP({ ...p, priority: e.target.value })}>{["Critical", "High", "Medium", "Low"].map((x) => <option key={x}>{x}</option>)}</select></Field>
          <Field label="Delivery location"><select className={inputCls} value={p.delivery_location} onChange={(e) => setP({ ...p, delivery_location: e.target.value })}>{meta.locations.map((x) => <option key={x}>{x}</option>)}</select></Field>
        </div>
      </Card>

      {roles.map((r, i) => (
        <Card key={i} className="mt-4 p-6">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-bold text-slate-800">Role {i + 1}</h3>
            {roles.length > 1 && <button onClick={() => setRoles(roles.filter((_, j) => j !== i))} className="text-slate-400 hover:text-rose-500"><Trash2 className="h-4 w-4" /></button>}
          </div>
          <div className="grid gap-4 md:grid-cols-5">
            <Field label="Role title" wide2><input className={inputCls} value={r.title} onChange={(e) => setRole(i, { title: e.target.value })} /></Field>
            <Field label="Practice"><select className={inputCls} value={r.family} onChange={(e) => setRole(i, { family: e.target.value })}>
              {meta.families.map((f) => <option key={f.role_family} value={f.role_family}>{f.practice}</option>)}</select></Field>
            <Field label="Headcount"><input type="number" min={1} max={20} className={inputCls} value={r.headcount} onChange={(e) => setRole(i, { headcount: +e.target.value })} /></Field>
            <Field label="Min. years"><input type="number" min={0} max={30} step={0.5} className={inputCls} value={r.min_experience} onChange={(e) => setRole(i, { min_experience: +e.target.value })} /></Field>
            <Field label={`Allocation: ${r.allocation}%`} wide2><input type="range" min={10} max={100} step={10} value={r.allocation} onChange={(e) => setRole(i, { allocation: +e.target.value })} className="mt-2 w-full accent-brand-600" /></Field>
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <Field label="Mandatory skills (with minimum level)">
              <Picker items={meta.skills.map((s) => ({ id: s.skill_id, label: s.skill_name, hint: s.category }))} value={r.mandatory_skills.map((s) => s.skill_id)}
                onAdd={(id) => setRole(i, { mandatory_skills: [...r.mandatory_skills, { skill_id: id, min_level: 3 }] })}
                onRemove={(id) => setRole(i, { mandatory_skills: r.mandatory_skills.filter((s) => s.skill_id !== id) })}
                level={(id) => r.mandatory_skills.find((s) => s.skill_id === id)!.min_level}
                setLevel={(id, l) => setRole(i, { mandatory_skills: r.mandatory_skills.map((s) => s.skill_id === id ? { ...s, min_level: l } : s) })} />
            </Field>
            <Field label="Preferred skills">
              <Picker items={meta.skills.map((s) => ({ id: s.skill_id, label: s.skill_name, hint: s.category }))} value={r.preferred_skills}
                onAdd={(id) => setRole(i, { preferred_skills: [...r.preferred_skills, id] })}
                onRemove={(id) => setRole(i, { preferred_skills: r.preferred_skills.filter((s) => s !== id) })} />
            </Field>
            <Field label="Mandatory certifications">
              <Picker items={meta.certifications.map((c) => ({ id: c.cert_id, label: c.cert_name, hint: c.vendor }))} value={r.mandatory_certs}
                onAdd={(id) => setRole(i, { mandatory_certs: [...r.mandatory_certs, id] })}
                onRemove={(id) => setRole(i, { mandatory_certs: r.mandatory_certs.filter((s) => s !== id) })} />
            </Field>
            <Field label="Preferred certifications">
              <Picker items={meta.certifications.map((c) => ({ id: c.cert_id, label: c.cert_name, hint: c.vendor }))} value={r.preferred_certs}
                onAdd={(id) => setRole(i, { preferred_certs: [...r.preferred_certs, id] })}
                onRemove={(id) => setRole(i, { preferred_certs: r.preferred_certs.filter((s) => s !== id) })} />
            </Field>
          </div>
        </Card>
      ))}

      <div className="mt-4 flex items-center justify-between">
        <Button variant="secondary" onClick={() => setRoles([...roles, blankRole()])}><Plus className="h-4 w-4" /> Add another role</Button>
        <div className="flex items-center gap-3">
          {error && <span className="text-sm text-rose-600">{error}</span>}
          <Button variant="ghost" onClick={() => setStep("describe")}>Back</Button>
          <Button onClick={save} loading={saving} disabled={!valid}>Create & find people <ArrowRight className="h-4 w-4" /></Button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children, wide, wide2 }: { label: string; children: ReactNode; wide?: boolean; wide2?: boolean }) {
  return <div className={cn("block", wide && "md:col-span-2", wide2 && "md:col-span-2")}><span className="mb-1 block text-xs font-medium text-slate-600">{label}</span>{children}</div>;
}

function Picker({ items, value, onAdd, onRemove, level, setLevel }: { items: { id: string; label: string; hint: string }[]; value: string[];
  onAdd: (id: string) => void; onRemove: (id: string) => void; level?: (id: string) => number; setLevel?: (id: string, l: number) => void }) {
  const [q, setQ] = useState("");
  const label = (id: string) => items.find((x) => x.id === id)?.label ?? id;
  const hits = q.length < 1 ? [] : items.filter((x) => !value.includes(x.id) && `${x.label} ${x.hint}`.toLowerCase().includes(q.toLowerCase())).slice(0, 7);
  return (
    <div className="rounded-xl border border-slate-200 p-2">
      <div className="flex flex-wrap gap-1.5">
        {value.map((id) => (
          <span key={id} className="inline-flex items-center gap-1 rounded-lg bg-brand-50 py-1 pl-2 pr-1 text-xs text-brand-800">
            {label(id)}
            {level && setLevel && <select value={level(id)} onChange={(e) => setLevel(id, +e.target.value)} onClick={(e) => e.preventDefault()}
              className="rounded bg-white px-1 text-[11px]">{[1, 2, 3, 4, 5].map((l) => <option key={l} value={l}>≥{l}</option>)}</select>}
            <button type="button" onClick={(e) => { e.preventDefault(); onRemove(id); }} className="rounded p-0.5 hover:bg-brand-100"><X className="h-3 w-3" /></button>
          </span>
        ))}
      </div>
      <div className="relative mt-1.5">
        <input className="w-full rounded-lg px-2 py-1 text-sm outline-none" placeholder="Type to add…" value={q} onChange={(e) => setQ(e.target.value)} />
        {hits.length > 0 && (
          <div className="absolute z-20 mt-1 w-full overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg">
            {hits.map((h) => (
              <button type="button" key={h.id} onClick={(e) => { e.preventDefault(); onAdd(h.id); setQ(""); }}
                className="flex w-full justify-between px-3 py-1.5 text-left text-sm hover:bg-slate-50">
                <span>{h.label}</span><span className="text-xs text-slate-400">{h.hint}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
