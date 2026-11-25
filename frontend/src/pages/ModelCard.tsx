import { Activity, BrainCircuit, Scale, ShieldCheck, Target } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Card, PageHeader, Spinner, Stat, cn } from "../components/ui";
import { useApi } from "../lib/api";

/** Tiny markdown renderer for our generated reports (headings, tables, bold, paragraphs). */
function Markdown({ text }: { text: string }) {
  const out: ReactNode[] = [];
  const lines = text.split("\n");
  const inline = (s: string) => s.split(/(\*\*[^*]+\*\*)/g).map((p, i) => p.startsWith("**") ? <b key={i}>{p.slice(2, -2)}</b> : p);
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (l.startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        if (!/^\|[\s:|-]+\|$/.test(lines[i])) rows.push(lines[i].split("|").slice(1, -1).map((c) => c.trim()));
        i++;
      }
      i--;
      out.push(
        <div key={i} className="my-3 overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full text-sm">
            <thead className="bg-slate-50"><tr>{rows[0].map((c, j) => <th key={j} className="px-3 py-2 text-left font-semibold text-slate-600">{c}</th>)}</tr></thead>
            <tbody>{rows.slice(1).map((r, k) => <tr key={k} className="border-t border-slate-100">{r.map((c, j) => <td key={j} className="px-3 py-1.5 tabular-nums text-slate-700">{inline(c)}</td>)}</tr>)}</tbody>
          </table>
        </div>);
    } else if (l.startsWith("## ")) out.push(<h3 key={i} className="mt-6 text-base font-bold text-slate-800">{l.slice(3)}</h3>);
    else if (l.startsWith("# ")) out.push(<h2 key={i} className="text-lg font-extrabold text-slate-900">{l.slice(2)}</h2>);
    else if (l.trim()) out.push(<p key={i} className="my-2 text-sm text-slate-600">{inline(l)}</p>);
  }
  return <div>{out}</div>;
}

export default function ModelCard() {
  const { data } = useApi<any>("/model");
  const [tab, setTab] = useState<"evaluation_report" | "bias_audit_report" | "preprocessing_report">("evaluation_report");
  if (!data) return <Spinner />;
  const m = data.meta;
  return (
    <div className="animate-rise">
      <PageHeader eyebrow="AI transparency" title="How the recommendations are made"
        subtitle="Model card: what the model learned from, how well it works, and how bias was measured and reduced." />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Stat label="Production model" value={<span className="text-lg">LightGBM</span>} hint={m.variant} icon={<BrainCircuit className="h-5 w-5" />} />
        <Stat label="Test AUC (2025-26)" value={m.test_auc.toFixed(3)} hint="vs 0.750 for a hand-weighted formula" icon={<Activity className="h-5 w-5" />} tone="green" />
        <Stat label="Test F1 (2025-26)" value={m.test_f1?.toFixed(3) ?? "-"} hint={`precision ${m.test_precision?.toFixed(2)} · recall ${m.test_recall?.toFixed(2)} · cut-off ${m.f1_threshold}`} icon={<Target className="h-5 w-5" />} />
        <Stat label="Equal-opportunity gap" value={m.equal_opportunity_gap.toFixed(3)} hint="gender gap when truly top-5 (raw model: 0.083)" icon={<Scale className="h-5 w-5" />} tone="blue" />
        <Stat label="Calibration" value={m.calibration === "none" ? "Native" : m.calibration} hint="chosen by cross-validation" icon={<ShieldCheck className="h-5 w-5" />} tone="amber" />
      </div>
      <Card className="mt-6 p-6">
        <div className="mb-4 flex rounded-xl bg-slate-100 p-1 text-sm">
          {([["evaluation_report", "Evaluation & fairness"], ["bias_audit_report", "Rating bias audit"], ["preprocessing_report", "Training data"]] as const).map(([k, l]) => (
            <button key={k} onClick={() => setTab(k)} className={cn("flex-1 rounded-lg px-3 py-1.5", tab === k ? "bg-white font-medium shadow-sm" : "text-slate-500")}>{l}</button>
          ))}
        </div>
        <Markdown text={data[tab]} />
      </Card>
      <Card className="mt-6 p-6 text-sm leading-relaxed text-slate-600">
        <h3 className="mb-2 font-bold text-slate-800">Principles</h3>
        <ul className="list-disc space-y-1 pl-5">
          <li>Hard business rules (availability, mandatory skills and certificates, workload limits) filter first; the model only ranks eligible people.</li>
          <li>Gender, age and career breaks are never model inputs. They are used offline to audit and correct historical rating bias, and live to check shortlist balance.</li>
          <li>Every score is explained with SHAP factor contributions; data problems (unverified claims, missing levels, inconsistent records) are flagged, not hidden.</li>
          <li>The language model only reads requests and phrases answers from computed results - it never scores, ranks or decides.</li>
          <li>No assignment happens without a manager's approval and recorded reason; every decision is kept in an append-only audit trail.</li>
        </ul>
      </Card>
    </div>
  );
}
