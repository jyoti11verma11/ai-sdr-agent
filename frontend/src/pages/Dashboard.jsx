import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { Link } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { motion } from "framer-motion";
import { ArrowUpRight, Users, CheckCircle2, TrendingUp, Gauge, Sparkles, Plus, Activity as ActIcon } from "lucide-react";
import { scoreColor, timeAgo } from "@/lib/utils";
import NewLeadDialog from "@/components/app/NewLeadDialog";

export default function Dashboard() {
  const { user } = useAuth();
  const [s, setS] = useState(null);
  const [acts, setActs] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const [a, b] = await Promise.all([api.get("/analytics/summary"), api.get("/analytics/activity?limit=8")]);
    setS(a.data); setActs(b.data); setLoading(false);
  };
  useEffect(() => { load(); }, []);

  return (
    <div className="p-8 max-w-[1400px] mx-auto" data-testid="dashboard-page">
      <div className="flex items-start justify-between gap-4 mb-8">
        <div>
          <div className="overline mb-2">Overview</div>
          <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tight">Good morning, {(user?.full_name || "").split(" ")[0] || "there"}.</h1>
          <p className="text-slate-500 mt-1 text-sm">Here's what your AI SDR handled recently.</p>
        </div>
        <button
          data-testid="new-lead-btn"
          onClick={() => setOpen(true)}
          className="inline-flex items-center gap-2 bg-[#0044FF] hover:bg-[#0033CC] text-white px-4 h-10 rounded-md text-sm font-medium transition-colors">
          <Plus className="h-4 w-4" /> New lead
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <Kpi icon={<Users className="h-4 w-4" />} label="Total leads" value={s?.total_leads ?? "—"} tid="kpi-total" />
        <Kpi icon={<CheckCircle2 className="h-4 w-4" />} label="Qualified" value={s?.qualified_leads ?? "—"} sub={s ? `${s.qualified_rate}%` : ""} tid="kpi-qualified" />
        <Kpi icon={<TrendingUp className="h-4 w-4" />} label="Conversion" value={s ? `${s.conversion_rate}%` : "—"} tid="kpi-conversion" />
        <Kpi icon={<Gauge className="h-4 w-4" />} label="Avg score" value={s?.avg_score ?? "—"} tid="kpi-score" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <motion.div initial={{opacity:0, y:12}} animate={{opacity:1,y:0}} transition={{duration:0.4}}
          className="lg:col-span-2 rounded-xl border border-slate-200 bg-white p-6" data-testid="ai-insights-card">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="overline">AI Insights</div>
              <h3 className="font-display text-xl font-semibold mt-1">Top signals from recent leads</h3>
            </div>
            <Sparkles className="h-5 w-5 text-[#0044FF]" />
          </div>
          {loading && <div className="text-slate-400 text-sm">Reading pipeline…</div>}
          {!loading && (s?.ai_insights?.length ?? 0) === 0 && (
            <EmptyInsight onClick={() => setOpen(true)} />
          )}
          <div className="space-y-3">
            {(s?.ai_insights || []).map((i) => (
              <div key={i.lead_id} className="border border-slate-100 rounded-lg p-4 hover:border-slate-300 transition-colors">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="text-sm font-semibold truncate">{i.name} <span className="text-slate-400 font-normal">·</span> {i.company}</div>
                    <div className="text-sm text-slate-600 mt-1 leading-relaxed">{i.summary}</div>
                    <div className="mt-2 text-xs text-slate-500">Recommended: <span className="text-slate-900 font-medium">{i.action}</span></div>
                  </div>
                  <div className={`score-badge border ${scoreColor(i.score)}`}>{i.score}</div>
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        <motion.div initial={{opacity:0, y:12}} animate={{opacity:1,y:0}} transition={{duration:0.4, delay:0.1}}
          className="rounded-xl border border-slate-200 bg-white p-6" data-testid="activity-card">
          <div className="flex items-center justify-between mb-4">
            <div className="overline">Recent activity</div>
            <ActIcon className="h-4 w-4 text-slate-400" />
          </div>
          {acts.length === 0 && <div className="text-sm text-slate-500">Nothing yet — capture a lead to get started.</div>}
          <ul className="space-y-3">
            {acts.map((a) => (
              <li key={a.id} className="text-sm">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-slate-900 truncate">{a.message}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{a.lead_name} · {a.company}</div>
                  </div>
                  <div className="text-xs text-slate-400 whitespace-nowrap">{timeAgo(a.at)}</div>
                </div>
              </li>
            ))}
          </ul>
        </motion.div>
      </div>

      <div className="mt-6 flex items-center justify-between text-sm">
        <div className="text-slate-500">Public capture link: <code className="font-mono bg-slate-100 px-2 py-0.5 rounded text-xs">{window.location.origin}/capture/{user?.email}</code></div>
        <Link to="/app/leads" data-testid="see-all-leads" className="text-[#0044FF] font-medium inline-flex items-center gap-1 hover:underline">See all leads <ArrowUpRight className="h-3.5 w-3.5" /></Link>
      </div>

      <NewLeadDialog open={open} onOpenChange={setOpen} onCreated={load} />
    </div>
  );
}

function Kpi({ icon, label, value, sub, tid }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5" data-testid={tid}>
      <div className="flex items-center justify-between text-slate-500">
        <span className="text-xs uppercase tracking-widest">{label}</span>
        <div className="h-7 w-7 rounded-md bg-slate-50 grid place-items-center text-slate-600">{icon}</div>
      </div>
      <div className="mt-3 font-display text-3xl font-bold tracking-tight">{value}</div>
      {sub && <div className="text-xs text-emerald-600 mt-1 font-medium">{sub} qualified</div>}
    </div>
  );
}

function EmptyInsight({ onClick }) {
  return (
    <div className="border border-dashed border-slate-200 rounded-lg p-8 text-center">
      <Sparkles className="h-6 w-6 text-[#0044FF] mx-auto mb-2" />
      <div className="font-medium">No leads yet</div>
      <div className="text-sm text-slate-500 mt-1">Capture your first lead and watch the AI qualify it in real time.</div>
      <button onClick={onClick} data-testid="empty-new-lead" className="mt-4 inline-flex items-center gap-2 bg-[#0044FF] text-white px-4 h-9 rounded-md text-sm font-medium hover:bg-[#0033CC] transition-colors">
        <Plus className="h-4 w-4" /> New lead
      </button>
    </div>
  );
}
