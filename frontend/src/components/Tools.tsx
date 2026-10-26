import { Bot, CheckCircle2, FlaskConical, HelpCircle, Minus, Plus, RotateCcw, Search, Send, X, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, type Meta, type RoleView } from "../lib/api";
import { Avatar, Badge, Button, Card, Portal, cn, inputCls } from "./ui";

// ---------------------------------------------------------------- What-if
export interface WhatIfState { allocation: number; start_date: string; min_experience: number; skills: { skill_id: string; skill: string; min_level: number }[] }

export function WhatIfPanel({ role, meta, active, busy, onRun, onReset }: { role: RoleView; meta: Meta | null; active: boolean; busy: boolean;
  onRun: (w: WhatIfState) => void; onReset: () => void }) {
  const idOf = (name: string) => meta?.skills.find((s) => s.skill_name === name)?.skill_id ?? "";
  const initial = (): WhatIfState => ({ allocation: role.allocation, start_date: role.start, min_experience: role.min_experience,
    skills: role.mandatory_skills.map((s) => ({ skill_id: idOf(s.skill), skill: s.skill, min_level: s.min_level })) });
  const [w, setW] = useState<WhatIfState>(initial);
  useEffect(() => { setW(initial()); }, [role.role_id, meta]); // eslint-disable-line react-hooks/exhaustive-deps
  const setLevel = (i: number, d: number) => setW({ ...w, skills: w.skills.map((s, j) => j === i ? { ...s, min_level: Math.min(5, Math.max(1, s.min_level + d)) } : s) });

  return (
    <Card className="p-5">
      <div className="mb-1 flex items-center gap-2 font-bold text-slate-800"><FlaskConical className="h-4 w-4 text-brand-500" /> What-if simulation</div>
      <p className="mb-4 text-xs text-slate-500">Change the demand and see the shortlist re-rank instantly. Nothing is saved.</p>
      <label className="text-xs font-medium text-slate-600">Allocation: {w.allocation}%</label>
      <input type="range" min={10} max={100} step={10} value={w.allocation} onChange={(e) => setW({ ...w, allocation: +e.target.value })} className="w-full accent-brand-600" />
      <div className="mt-3 grid grid-cols-2 gap-2">
        <div><label className="text-xs font-medium text-slate-600">Start date</label>
          <input type="date" className={inputCls} value={w.start_date} onChange={(e) => setW({ ...w, start_date: e.target.value })} /></div>
        <div><label className="text-xs font-medium text-slate-600">Min. experience</label>
          <input type="number" min={0} max={30} step={0.5} className={inputCls} value={w.min_experience} onChange={(e) => setW({ ...w, min_experience: +e.target.value })} /></div>
      </div>
      <div className="mt-3 text-xs font-medium text-slate-600">Mandatory skills</div>
      <div className="mt-1 space-y-1">
        {w.skills.map((s, i) => (
          <div key={s.skill_id} className="flex items-center gap-2 rounded-lg bg-slate-50 px-2 py-1 text-sm">
            <span className="flex-1 truncate">{s.skill}</span>
            <button onClick={() => setLevel(i, -1)} className="rounded p-0.5 hover:bg-white"><Minus className="h-3 w-3" /></button>
            <span className="w-4 text-center font-medium">{s.min_level}</span>
            <button onClick={() => setLevel(i, 1)} className="rounded p-0.5 hover:bg-white"><Plus className="h-3 w-3" /></button>
            <button onClick={() => setW({ ...w, skills: w.skills.filter((_, j) => j !== i) })} className="rounded p-0.5 text-slate-400 hover:bg-white hover:text-rose-500" title="Drop requirement"><X className="h-3.5 w-3.5" /></button>
          </div>
        ))}
      </div>
      <div className="mt-4 flex gap-2">
        <Button className="flex-1" loading={busy} onClick={() => onRun(w)}>Run what-if</Button>
        {active && <Button variant="secondary" onClick={() => { setW(initial()); onReset(); }}><RotateCcw className="h-4 w-4" /></Button>}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------- Why not?
export function WhyNot({ roleId }: { roleId: string }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<{ employee_id: string; full_name: string; designation: string }[]>([]);
  const [res, setRes] = useState<any>(null);
  useEffect(() => {
    if (q.length < 2) { setHits([]); return; }
    const t = setTimeout(() => api(`/employees?q=${encodeURIComponent(q)}`).then((r) => setHits(r.slice(0, 6))), 250);
    return () => clearTimeout(t);
  }, [q]);
  const check = async (id: string) => {
    setHits([]); setQ("");
    setRes(await api(`/demands/${roleId}/why-not/${id}`));
  };
  return (
    <Card className="p-5">
      <div className="mb-1 flex items-center gap-2 font-bold text-slate-800"><HelpCircle className="h-4 w-4 text-brand-500" /> Why not someone else?</div>
      <p className="mb-3 text-xs text-slate-500">Check any employee against this demand's rules.</p>
      <div className="relative">
        <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
        <input className={cn(inputCls, "pl-9")} placeholder="Type a name or skill…" value={q} onChange={(e) => setQ(e.target.value)} />
        {hits.length > 0 && (
          <div className="absolute z-20 mt-1 w-full overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg">
            {hits.map((h) => (
              <button key={h.employee_id} onClick={() => check(h.employee_id)} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-slate-50">
                <Avatar name={h.full_name} size={26} /><span className="flex-1">{h.full_name}</span><span className="text-xs text-slate-400">{h.designation}</span>
              </button>
            ))}
          </div>
        )}
      </div>
      {res && (
        <div className={cn("mt-3 rounded-xl p-3 text-sm", res.eligible ? "bg-emerald-50" : "bg-rose-50")}>
          <div className="flex items-center gap-2 font-medium">
            {res.eligible ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <XCircle className="h-4 w-4 text-rose-600" />}
            {res.employee.name} {res.eligible ? "meets every rule" : "is not eligible"}
          </div>
          {res.blockers.map((b: string) => <div key={b} className="ml-6 text-rose-700">• {b}</div>)}
          {res.warnings.map((b: string) => <div key={b} className="ml-6 text-amber-700">• {b}</div>)}
          {res.eligible && <div className="ml-6 mt-1 text-xs text-emerald-700">Eligible but ranked below the shortlist on predicted success.</div>}
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------- Assistant
/** Minimal formatting for LLM answers: paragraphs, "*"/"-" bullets and **bold**. */
function Formatted({ text }: { text: string }) {
  const bold = (s: string) => s.split(/(\*\*[^*]+\*\*)/g).map((p, i) => p.startsWith("**") ? <b key={i}>{p.slice(2, -2)}</b> : p);
  const lines = text.replace(/\s\*\s(?=\*\*)/g, "\n* ").split("\n").filter((l) => l.trim());
  return (
    <div className="space-y-1.5">
      {lines.map((l, i) => /^\s*[*-]\s+/.test(l)
        ? <div key={i} className="flex gap-2"><span className="text-brand-400">•</span><span>{bold(l.replace(/^\s*[*-]\s+/, ""))}</span></div>
        : <p key={i}>{bold(l)}</p>)}
    </div>
  );
}

export function Assistant({ roleId, nearMiss, onClose }: { roleId: string; nearMiss?: string; onClose: () => void }) {
  const [msgs, setMsgs] = useState<{ who: "me" | "ai"; text: string; source?: string }[]>([
    { who: "ai", text: "Hi! Ask me about this shortlist - who fits best, trade-offs, risks, fairness, or why someone is missing." }]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);   // block body: scrollIntoView may return a Promise
  const ask = async (question: string) => {
    if (!question.trim() || busy) return;
    setMsgs((m) => [...m, { who: "me", text: question }]); setQ(""); setBusy(true);
    try {
      const r = await api("/assistant/chat", { json: { role_id: roleId, question } });
      setMsgs((m) => [...m, { who: "ai", text: r.answer, source: r.source }]);
    } catch (e: any) {
      setMsgs((m) => [...m, { who: "ai", text: `Sorry - ${e.message}` }]);
    } finally { setBusy(false); }
  };
  const chips = ["Who is the best fit?", "Compare the top two", "Any risks?", "Is the shortlist fair?", ...(nearMiss ? [`Why not ${nearMiss}?`] : [])];
  return (
    <Portal>
    <div className="fixed inset-y-0 right-0 z-40 flex w-full max-w-md animate-rise flex-col border-l border-slate-200 bg-white shadow-2xl">
      <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-4">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand-400 to-brand-700 text-white"><Bot className="h-5 w-5" /></div>
        <div className="flex-1"><div className="font-bold text-slate-800">Staffing assistant</div><div className="text-xs text-slate-500">Answers only from this recommendation</div></div>
        <button onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-slate-100"><X className="h-5 w-5" /></button>
      </div>
      <div className="scrollbar-thin flex-1 space-y-3 overflow-y-auto p-5">
        {msgs.map((m, i) => (
          <div key={i} className={cn("max-w-[88%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed", m.who === "me" ? "ml-auto bg-brand-600 text-white" : "bg-slate-100 text-slate-700")}>
            {m.who === "ai" ? <Formatted text={m.text} /> : m.text}
            {m.source && <div className="mt-1"><Badge tone={m.source === "groq" ? "brand" : "gray"}>{m.source === "groq" ? "AI · Groq" : "Rule engine"}</Badge></div>}
          </div>
        ))}
        {busy && <div className="w-16 animate-pulse rounded-2xl bg-slate-100 px-4 py-2.5 text-sm text-slate-400">…</div>}
        <div ref={end} />
      </div>
      <div className="border-t border-slate-100 p-4">
        <div className="mb-2 flex flex-wrap gap-1.5">
          {chips.map((c) => <button key={c} onClick={() => ask(c)} className="rounded-full bg-brand-50 px-3 py-1 text-xs text-brand-700 hover:bg-brand-100">{c}</button>)}
        </div>
        <form onSubmit={(e) => { e.preventDefault(); ask(q); }} className="flex gap-2">
          <input className={inputCls} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask a question…" />
          <Button type="submit" disabled={!q.trim()} loading={busy}><Send className="h-4 w-4" /></Button>
        </form>
      </div>
    </div>
    </Portal>
  );
}
