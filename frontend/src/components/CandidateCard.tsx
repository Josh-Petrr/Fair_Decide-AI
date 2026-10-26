import { AlertTriangle, BadgeCheck, Check, ChevronDown, FolderGit2, Medal, Star } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import type { Candidate } from "../lib/api";
import { Avatar, Badge, Card, FactorBars, LevelDots, LoadBar, Ring, cn } from "./ui";

export default function CandidateCard({ c, selected, onToggle, canSelect }: { c: Candidate; selected: boolean; onToggle: () => void; canSelect: boolean }) {
  const [open, setOpen] = useState(false);
  const medal = ["text-amber-500", "text-slate-400", "text-orange-400"][c.rank - 1];
  return (
    <Card className={cn("relative overflow-hidden transition", selected ? "border-brand-400 ring-4 ring-brand-100" : "hover:shadow-md")}>
      {selected && <div className="absolute inset-y-0 left-0 w-1 bg-brand-500" />}
      <div className="grid gap-5 p-5 lg:grid-cols-[230px_1fr_200px]">
        {/* who */}
        <div className="flex gap-3">
          <div className="relative h-fit shrink-0">
            <Avatar name={c.name} size={48} />
            <span className="absolute -bottom-1 -right-1 grid h-6 w-6 place-items-center rounded-full bg-white text-[11px] font-bold text-slate-600 shadow ring-1 ring-slate-200">
              {medal ? <Medal className={cn("h-3.5 w-3.5", medal)} /> : c.rank}
            </span>
          </div>
          <div className="min-w-0">
            <Link to={`/people/${c.employee_id}`} className="font-semibold text-slate-900 hover:text-brand-700">{c.name}</Link>
            <div className="text-sm text-slate-500">{c.designation}</div>
            <div className="text-xs text-slate-400">{c.level} · {c.location} · {c.experience_years} yrs</div>
            <div className="mt-2 flex flex-wrap gap-1">
              <Badge tone={c.confidence === "High" ? "green" : c.confidence === "Medium" ? "amber" : "red"}>{c.confidence} confidence</Badge>
              {c.workload_now === 0 && <Badge tone="blue">On bench</Badge>}
              {c.past_rating && <Badge><Star className="h-3 w-3" />{c.past_rating.toFixed(1)}</Badge>}
            </div>
          </div>
        </div>

        {/* why */}
        <div className="min-w-0 space-y-3">
          <p className="rounded-xl bg-slate-50 px-3 py-2 text-sm leading-relaxed text-slate-600">{c.explanation}</p>
          <div className="flex flex-wrap gap-1.5">
            {c.skills.map((s) => (
              <span key={s.skill} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs">
                <span className="font-medium text-slate-700">{s.skill}</span>
                <LevelDots level={s.level} required={s.required} />
                {s.verified && <BadgeCheck className="h-3.5 w-3.5 text-sky-500" aria-label="Manager verified" />}
                {s.proven_on_project && <FolderGit2 className="h-3.5 w-3.5 text-emerald-500" aria-label="Used on a project" />}
              </span>
            ))}
            {c.preferred.map((p) => (
              <span key={p.skill} className={cn("rounded-lg px-2 py-1 text-xs", p.has ? "bg-emerald-50 text-emerald-700" : "bg-slate-50 text-slate-400 line-through")}>
                {p.skill}
              </span>
            ))}
          </div>
          {c.similar_projects[0] && (
            <div className="text-xs text-slate-500">Most similar past work: <b className="text-slate-700">{c.similar_projects[0].project}</b>
              {" "}<Badge tone="brand">{Math.round(c.similar_projects[0].similarity * 100)}% similar</Badge></div>
          )}
          {c.flags.length > 0 && (
            <div className="space-y-1">
              {c.flags.map((f) => (
                <div key={f} className="flex items-start gap-1.5 text-xs text-amber-700"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />{f}</div>
              ))}
            </div>
          )}
        </div>

        {/* scores */}
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <Ring value={c.success_probability} size={76} label="success" />
            <div className="text-xs text-slate-500">
              <div>Evidence</div>
              <div className="mt-1 h-1.5 w-20 overflow-hidden rounded-full bg-slate-100">
                <div className="h-full rounded-full bg-sky-500" style={{ width: `${c.evidence_score * 100}%` }} />
              </div>
              <div className="mt-0.5 font-medium text-slate-700">{Math.round(c.evidence_score * 100)}%</div>
            </div>
          </div>
          <LoadBar now={c.workload_on_start} after={c.workload_after} />
          <button disabled={!canSelect && !selected} onClick={onToggle}
            className={cn("mt-auto inline-flex items-center justify-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-40",
              selected ? "bg-brand-600 text-white" : "bg-brand-50 text-brand-700 hover:bg-brand-100")}>
            {selected ? <><Check className="h-4 w-4" /> Selected</> : "Select"}
          </button>
        </div>
      </div>
      <button onClick={() => setOpen(!open)} className="flex w-full items-center justify-center gap-1 border-t border-slate-100 py-2 text-xs font-medium text-slate-500 hover:bg-slate-50">
        Why this score? <ChevronDown className={cn("h-3.5 w-3.5 transition", open && "rotate-180")} />
      </button>
      {open && (
        <div className="grid gap-6 border-t border-slate-100 bg-slate-50/60 p-5 md:grid-cols-2">
          <div>
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Factor impact on predicted success</div>
            <FactorBars factors={c.factors} />
            <p className="mt-2 text-[11px] text-slate-400">SHAP contributions in percentage points versus an average candidate. Gender and age are never inputs.</p>
          </div>
          <div className="space-y-3 text-sm">
            <div>
              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Current projects</div>
              {c.current_projects.length === 0 ? <div className="text-slate-500">None - available now</div> :
                c.current_projects.map((p) => <div key={p.project} className="text-slate-600">{p.project} · {p.allocation}% until {p.ends}</div>)}
            </div>
            {c.certifications.length > 0 && <div>
              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Relevant certifications</div>
              {c.certifications.map((x) => <div key={x} className="text-slate-600">{x}</div>)}
            </div>}
            <div className="text-xs text-slate-500">{c.domain_projects} project(s) in this industry · <BadgeCheck className="inline h-3.5 w-3.5 text-sky-500" /> verified by manager · <FolderGit2 className="inline h-3.5 w-3.5 text-emerald-500" /> used on a project</div>
          </div>
        </div>
      )}
    </Card>
  );
}
