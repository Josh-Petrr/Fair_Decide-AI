import { ArrowLeft, Award, BadgeCheck, CalendarOff, FolderGit2, Mail, MapPin, Star } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Avatar, Badge, Card, Empty, LevelDots, LoadBar, Spinner, fmtDate } from "../components/ui";
import { useApi } from "../lib/api";
import { useLive } from "../lib/live";

export default function Person() {
  const { employeeId } = useParams();
  const { version } = useLive();
  const { data, loading } = useApi<any>(`/employees/${employeeId}`, [version]);
  if (loading && !data) return <Spinner />;
  if (!data) return <Empty title="Employee not found" />;
  const e = data.employee;
  const active = data.assignments.filter((a: any) => a.status === "Active" || a.status === "Upcoming");
  const done = data.assignments.filter((a: any) => a.status === "Completed");
  return (
    <div className="animate-rise">
      <button onClick={() => history.back()} className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-brand-600"><ArrowLeft className="h-4 w-4" /> Back</button>
      <Card className="p-6">
        <div className="flex flex-wrap items-center gap-5">
          <Avatar name={e.full_name} size={72} />
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl font-extrabold text-slate-900">{e.full_name}</h1>
            <div className="text-slate-600">{e.designation} · {e.practice}</div>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-500">
              <span><MapPin className="mr-1 inline h-4 w-4" />{e.location} · {e.work_mode}</span>
              <span><Mail className="mr-1 inline h-4 w-4" />{e.email ?? <span className="text-rose-600">no email on record</span>}</span>
              <span>{e.employee_id} · {e.job_level} · joined {fmtDate(e.date_of_joining)}</span>
              <span>{e.total_experience_years} yrs experience</span>
            </div>
          </div>
          <div className="w-64">
            {e.employment_status !== "Active" && <Badge tone="amber" className="mb-2">{e.employment_status}{e.exit_date ? ` · ${fmtDate(e.exit_date)}` : ""}</Badge>}
            <LoadBar now={e.current_allocation_pct ?? 0} />
            <div className="mt-2 flex gap-3 text-xs text-slate-500">
              <span>{e.active_project_count ?? 0} active project(s)</span>
              {e.last_appraisal_rating && <span><Star className="inline h-3 w-3" /> {e.last_appraisal_rating}/5 ({e.appraisal_cycle})</span>}
            </div>
          </div>
        </div>
      </Card>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr_1fr]">
        <Card className="p-5">
          <h3 className="mb-3 font-bold text-slate-800">Skills</h3>
          <div className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
            {data.skills.map((s: any) => (
              <div key={s.skill_name} className="flex items-center gap-2 border-b border-slate-50 py-1.5 text-sm">
                <span className="flex-1 truncate text-slate-700">{s.skill_name}</span>
                {s.is_manager_verified && <BadgeCheck className="h-3.5 w-3.5 text-sky-500" aria-label="Manager verified" />}
                {s.proven_on_project && <FolderGit2 className="h-3.5 w-3.5 text-emerald-500" aria-label="Used on a project" />}
                <LevelDots level={s.proficiency} />
                <span className="w-10 text-right text-xs text-slate-400">{s.years_used}y</span>
              </div>
            ))}
          </div>
          <div className="mt-3 text-xs text-slate-400"><BadgeCheck className="inline h-3.5 w-3.5 text-sky-500" /> verified by manager · <FolderGit2 className="inline h-3.5 w-3.5 text-emerald-500" /> used on a project · empty dots = level not recorded</div>
        </Card>

        <div className="space-y-6">
          <Card className="p-5">
            <h3 className="mb-3 font-bold text-slate-800">Current & upcoming work</h3>
            {active.length === 0 ? <div className="text-sm text-slate-500">Not allocated - available.</div> : active.map((a: any) => (
              <Link key={a.assignment_id} to={`/projects/${a.project_id}`} className="block rounded-xl border border-slate-200 p-3 hover:border-brand-200">
                <div className="flex justify-between text-sm"><b className="text-slate-800">{a.project_name}</b><Badge tone={a.status === "Upcoming" ? "blue" : "green"}>{a.status}</Badge></div>
                <div className="text-xs text-slate-500">{a.role_title} · {a.allocation_pct}% · {fmtDate(a.start_date)} → {fmtDate(a.end_date)}</div>
              </Link>
            ))}
            {data.leaves.length > 0 && <div className="mt-3 space-y-1">{data.leaves.map((l: any) => (
              <div key={l.start_date} className="flex items-center gap-2 text-sm text-amber-700"><CalendarOff className="h-4 w-4" />{l.leave_type}: {fmtDate(l.start_date)} → {fmtDate(l.end_date)} ({l.status})</div>))}</div>}
          </Card>
          <Card className="p-5">
            <h3 className="mb-3 font-bold text-slate-800">Certifications</h3>
            {data.certifications.length === 0 ? <div className="text-sm text-slate-500">None recorded.</div> : data.certifications.map((c: any) => (
              <div key={c.cert_name + c.issue_date} className="flex items-start gap-2 py-1.5 text-sm">
                <Award className={c.is_valid ? "h-4 w-4 text-emerald-500" : "h-4 w-4 text-slate-300"} />
                <div className="flex-1"><div className="text-slate-700">{c.cert_name}</div>
                  <div className="text-xs text-slate-400">{c.vendor} · issued {fmtDate(c.issue_date)}{c.expiry_date ? ` · expires ${fmtDate(c.expiry_date)}` : " · no expiry"}</div></div>
                {c.has_date_error ? <Badge tone="red">date error</Badge> : <Badge tone={c.is_valid ? "green" : "gray"}>{c.is_valid ? "valid" : "expired"}</Badge>}
              </div>
            ))}
          </Card>
        </div>
      </div>

      <Card className="mt-6 p-5">
        <h3 className="mb-3 font-bold text-slate-800">Project history</h3>
        <div className="space-y-3">
          {done.map((a: any) => (
            <div key={a.assignment_id} className="grid grid-cols-[1fr_auto] gap-2 border-l-2 border-brand-200 pl-4">
              <div>
                <div className="font-medium text-slate-800">{a.project_name} <span className="font-normal text-slate-400">· {a.client_name}</span></div>
                <div className="text-xs text-slate-500">{a.role_title} · {fmtDate(a.start_date)} → {fmtDate(a.end_date)} · {a.industry}{a.release_reason ? ` · ${a.release_reason}` : ""}</div>
                {a.feedback && <div className="mt-1 text-sm italic text-slate-600">"{a.feedback}"</div>}
              </div>
              {a.performance_rating && <Badge tone={a.performance_rating >= 4 ? "green" : a.performance_rating <= 2 ? "red" : "gray"}><Star className="h-3 w-3" />{a.performance_rating}</Badge>}
            </div>
          ))}
          {done.length === 0 && <div className="text-sm text-slate-500">No completed projects yet.</div>}
        </div>
      </Card>
    </div>
  );
}
