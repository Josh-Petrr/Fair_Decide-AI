import { useCallback, useEffect, useState } from "react";

export class ApiError extends Error {
  status: number;
  details?: Record<string, string[]>;
  constructor(status: number, detail: unknown) {
    const d = detail as { message?: string; details?: Record<string, string[]> } | string | undefined;
    super(typeof d === "string" ? d : d?.message ?? (Array.isArray(detail) ? "Please check the form fields" : "Something went wrong"));
    this.status = status;
    if (d && typeof d === "object" && !Array.isArray(d)) this.details = d.details;
  }
}

export const token = {
  get: () => localStorage.getItem("fd_token"),
  set: (t: string) => localStorage.setItem("fd_token", t),
  clear: () => localStorage.removeItem("fd_token"),
};

export async function api<T = any>(path: string, opts: { method?: string; json?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const t = token.get();
  if (t) headers.Authorization = `Bearer ${t}`;
  if (opts.json !== undefined) headers["Content-Type"] = "application/json";
  const r = await fetch(`/api${path}`, {
    method: opts.method ?? (opts.json !== undefined ? "POST" : "GET"),
    headers,
    body: opts.json !== undefined ? JSON.stringify(opts.json) : undefined,
  });
  const data = await r.json().catch(() => null);
  if (r.status === 401 && !path.startsWith("/auth")) {
    token.clear();
    window.location.href = "/login";
  }
  if (!r.ok) throw new ApiError(r.status, data?.detail);
  return data as T;
}

/** GET with loading / error state; `deps` re-trigger the request. */
export function useApi<T = any>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const load = useCallback(() => {
    if (!path) return;
    setLoading(true);
    api<T>(path)
      .then((d) => { setData(d); setError(null); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps]);
  useEffect(() => { load(); }, [load]);
  return { data, error, loading, reload: load, setData };
}

// ---------------------------------------------------------------- shared response types
export interface Factor { factor: string; impact: number }
export interface SkillMatch { skill: string; required: number; level: number | null; verified: boolean; proven_on_project: boolean }
export interface Person {
  employee_id: string; name: string; email: string | null; designation: string; level: string; practice: string;
  location: string; workload_now: number; workload_on_start: number;
  current_projects: { project: string; allocation: number; ends: string }[];
}
export interface Candidate extends Person {
  rank: number; success_probability: number; confidence: "High" | "Medium" | "Low"; evidence_score: number;
  factors: Factor[]; skills: SkillMatch[]; preferred: { skill: string; has: boolean }[]; experience_years: number;
  domain_projects: number; similar_projects: { project: string; client_id: string; industry: string; similarity: number }[];
  past_rating: number | null; certifications: string[]; workload_after: number; flags: string[]; explanation: string;
}
export interface RoleView {
  role_id: string; title: string; project_id: string; project_name: string; client_name: string; industry: string;
  priority: string; project_status: string; description: string; filled: number; start: string; end: string; allocation: number;
  min_experience: number; headcount: number; mandatory_skills: { skill: string; min_level: number }[];
  preferred_skills: string[]; mandatory_certs: string[]; preferred_certs: string[];
}
export interface RecResult {
  request_id?: number; role: RoleView; candidates: Candidate[];
  near_misses: (Person & { success_probability: number; blocker: string })[];
  pool: { considered: number; eligible: number; excluded: number; exclusion_reasons: Record<string, number> };
  fairness: { women_in_eligible_pool: number | null; women_in_shortlist: number | null; representation_ratio: number | null; status: string; note: string };
  model: { variant: string; test_auc: number };
}
export interface Meta {
  as_of: string;
  skills: { skill_id: string; skill_name: string; category: string }[];
  certifications: { cert_id: string; cert_name: string; vendor: string }[];
  clients: { client_id: string; client_name: string; industry: string }[];
  families: { role_family: string; practice: string }[];
  locations: string[];
}
