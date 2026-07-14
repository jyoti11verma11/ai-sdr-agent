import React, { useEffect, useState, useRef } from "react";
import api from "@/lib/api";
import { Link } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { motion } from "framer-motion";
import {
  ArrowUpRight, Users, CheckCircle2, TrendingUp, Gauge, Sparkles, Plus,
  Activity as ActIcon, Zap, MessageSquare, Webhook, Circle, XCircle,
  Clock, LoaderPinwheel, AlertTriangle
} from "lucide-react";
import { scoreColor, timeAgo } from "@/lib/utils";
import NewLeadDialog from "@/components/app/NewLeadDialog";
import { SkeletonKpi, SkeletonInsight, SkeletonBlock } from "@/components/app/Skeletons";
import EmptyState from "@/components/app/EmptyState";
import { AreaChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts";

const container = { hidden: {}, show: { transition: { staggerChildren: 0.06 } } };
const item = { hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0, transition: { duration: 0.35 } } };

export default function Dashboard() {
  const { user } = useAuth();
  const [s, setS] = useState(null);
  const [acts, setActs] = useState([]);
  const [integrations, setIntegrations] = useState(null);
  const [counts, setCounts] = useState(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);

  const load = async () => {
    setError(null);
    try {
      const [a, b, c, d] = await Promise.all([
        api.get("/analytics/summary"),
        api.get("/analytics/activity?limit=8"),
        api.get("/integrations/status"),
        api.get("/leads/status-counts"),
      ]);
      setS(a.data); setActs(b.data); setIntegrations(c.data); setCounts(d.data);
    } catch (e) { setError("Couldn't load your pipeline. Try again in a moment."); }
    finally { setLoading(false); }
  };

  const pollCounts = async () => {
    try {
      const [{ data: cnt }, { data: act }] = await Promise.all([
        api.get("/leads/status-counts"),
        api.get("/analytics/activity?limit=8"),
      ]);
      setCounts(cnt); setActs(act);
    } catch {}
  };

  useEffect(() => { load(); }, []);

  // Live polling while there are pending/analyzing leads
  useEffect(() => {
    const active = (counts?.pending || 0) + (counts?.analyzing || 0);
    if (active > 0) {
      pollRef.current = setInterval(pollCounts, 4000);
      return () => clearInterval(pollRef.current);
    }
    return undefined;
  }, [counts?.pending, counts?.analyzing]);

  return (
    <div className="px-4 sm:px-6 lg:px-8 py-6 lg:py-8 max-w-[1400px] mx-auto" data-testid="dashboard-page">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-6 lg:mb-8">
        <div>
          <div className="overline mb-2">Overview</div>
          <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tighter leading-tight">
            {greeting()}, {(user?.full_name || "").split(" ")[0] || "there"}.
          </h1>
          <p className="text-sm text-muted-foreground mt-1.5">Here's what your AI SDR handled recently.</p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/app/leads" className="inline-flex items-center gap-1.5 h-10 px-4 rounded-md border border-border bg-card hover:bg-accent text-sm font-medium transition-colors">View leads</Link>
          <button data-testid="new-lead-btn" onClick={() => setOpen(true)}
            className="inline-flex items-center gap-1.5 bg-primary hover:bg-primary/90 text-primary-foreground px-4 h-10 rounded-md text-sm font-medium transition-colors shadow-sm shadow-primary/20">
            <Plus className="h-4 w-4" /> New lead
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-destructive/30 bg-destructive/5 text-destructive text-sm px-4 py-3 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={load} className="text-xs underline">Retry</button>
        </div>
      )}

      {/* Processing status strip (Phase 3) */}
      {counts && (
        <div className="mb-6 lg:mb-8 grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="processing-strip">
          <ProcCard label="Pending" value={counts.pending} icon={<Clock className="h-3.5 w-3.5" />} tone="muted" tid="proc-pending" />
          <ProcCard label="Analyzing" value={counts.analyzing} icon={<LoaderPinwheel className={`h-3.5 w-3.5 ${counts.analyzing ? "animate-spin" : ""}`} />} tone="primary" tid="proc-analyzing" />
          <ProcCard label="Qualified" value={counts.qualified} icon={<CheckCircle2 className="h-3.5 w-3.5" />} tone="success" tid="proc-qualified" />
          <ProcCard label="Failed" value={counts.failed} icon={<AlertTriangle className="h-3.5 w-3.5" />} tone="danger" tid="proc-failed" />
        </div>
      )}

      {/* KPIs */}
      {loading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6 lg:mb-8">
          {[...Array(4)].map((_, i) => <SkeletonKpi key={i} />)}
        </div>
      ) : (
        <motion.div initial="hidden" animate="show" variants={container}
          className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6 lg:mb-8">
          <Kpi icon={<Users className="h-4 w-4" />} label="Total leads" value={s?.total_leads ?? 0}
            hint={s?.timeline?.length ? `${s.timeline[s.timeline.length-1].count} today` : "—"}
            spark={s?.timeline || []} tid="kpi-total" />
          <Kpi icon={<CheckCircle2 className="h-4 w-4" />} label="Qualified" value={s?.qualified_leads ?? 0}
            hint={`${s?.qualified_rate ?? 0}% of total`} spark={s?.timeline || []}
            variant="success" tid="kpi-qualified" />
          <Kpi icon={<TrendingUp className="h-4 w-4" />} label="Conversion" value={`${s?.conversion_rate ?? 0}%`}
            hint="Converted / total" tid="kpi-conversion" />
          <Kpi icon={<Gauge className="h-4 w-4" />} label="Avg score" value={s?.avg_score ?? 0}
            hint={hintForScore(s?.avg_score)} tid="kpi-score" />
        </motion.div>
      )}

      {/* Integration health */}
      {integrations && (
        <div className="mb-6 lg:mb-8 rounded-xl border border-border bg-card p-4 flex flex-col sm:flex-row items-start sm:items-center gap-3" data-testid="integrations-strip">
          <div className="overline shrink-0">Integrations</div>
          <div className="flex flex-wrap items-center gap-2 flex-1">
            <IntChip name="HubSpot" data={integrations.hubspot} Icon={Zap} />
            <IntChip name="Slack" data={integrations.slack} Icon={MessageSquare} />
            <IntChip name="n8n" data={integrations.n8n} Icon={Webhook} />
          </div>
          <Link to="/app/settings" className="text-xs text-primary font-medium hover:underline shrink-0">Configure →</Link>
        </div>
      )}

      {/* Insights + Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <motion.div initial={item.hidden} animate={item.show}
          className="lg:col-span-2 rounded-xl border border-border bg-card p-6" data-testid="ai-insights-card">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="overline">AI Insights</div>
              <h3 className="font-display text-xl font-semibold mt-1 tracking-tight">Top signals from recent leads</h3>
            </div>
            <div className="h-9 w-9 rounded-md bg-primary/10 text-primary grid place-items-center"><Sparkles className="h-4 w-4" /></div>
          </div>
          {loading && (<div className="space-y-3"><SkeletonInsight /><SkeletonInsight /></div>)}
          {!loading && (s?.ai_insights?.length ?? 0) === 0 && (
            <EmptyState icon={<Sparkles className="h-5 w-5" />}
              title="No leads yet"
              description="Capture your first lead and watch the AI qualify it in real time."
              testId="dash-empty-insights"
              action={<button onClick={() => setOpen(true)} data-testid="empty-new-lead"
                className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-4 h-9 rounded-md text-sm font-medium hover:bg-primary/90 transition-colors">
                <Plus className="h-4 w-4" /> New lead</button>} />
          )}
          <div className="space-y-3">
            {(s?.ai_insights || []).map((i) => (
              <div key={i.lead_id} className="border border-border rounded-lg p-4 hover:border-primary/40 hover:bg-accent/30 transition-colors">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="text-sm font-semibold truncate">{i.name} <span className="text-muted-foreground font-normal">·</span> {i.company}</div>
                    <div className="text-sm text-muted-foreground mt-1.5 leading-relaxed line-clamp-3">{i.summary}</div>
                    <div className="mt-2.5 flex items-center gap-2 text-xs text-muted-foreground">
                      <Zap className="h-3.5 w-3.5 text-primary" /> Next step: <span className="text-foreground font-medium">{i.action}</span>
                    </div>
                  </div>
                  <div className={`score-badge border shrink-0 ${scoreColor(i.score)}`}>{i.score}</div>
                </div>
              </div>
            ))}
          </div>
        </motion.div>

        <motion.div initial={item.hidden} animate={item.show}
          className="rounded-xl border border-border bg-card p-6" data-testid="activity-card">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="overline">Live feed</div>
              <h3 className="font-display text-lg font-semibold mt-1 tracking-tight">Recent activity</h3>
            </div>
            <div className="h-9 w-9 rounded-md bg-accent grid place-items-center text-muted-foreground"><ActIcon className="h-4 w-4" /></div>
          </div>
          {loading && <div className="space-y-3">{[...Array(5)].map((_, i) => <SkeletonBlock key={i} className="h-3 w-full rounded" />)}</div>}
          {!loading && acts.length === 0 && <div className="text-sm text-muted-foreground">Nothing yet — capture a lead to get started.</div>}
          <ul className="space-y-3.5">
            {acts.map((a) => (
              <li key={a.id} className="text-sm relative pl-4">
                <span className="absolute left-0 top-1.5 h-1.5 w-1.5 rounded-full bg-primary/60" />
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-foreground line-clamp-1">{a.message}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">{a.lead_name} · {a.company}</div>
                  </div>
                  <div className="text-xs text-muted-foreground whitespace-nowrap">{timeAgo(a.at)}</div>
                </div>
              </li>
            ))}
          </ul>
          {!loading && acts.length > 0 && (
            <Link to="/app/leads" className="mt-5 inline-flex items-center gap-1 text-xs text-primary font-medium hover:underline">
              View all leads <ArrowUpRight className="h-3 w-3" />
            </Link>
          )}
        </motion.div>
      </div>

      <NewLeadDialog open={open} onOpenChange={setOpen} onCreated={load} />
    </div>
  );
}

function ProcCard({ label, value, icon, tone, tid }) {
  const toneCls = {
    muted: "bg-muted text-muted-foreground border-border",
    primary: "bg-primary/10 text-primary border-primary/20",
    success: "bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900",
    danger: "bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-900",
  }[tone];
  return (
    <div className="rounded-xl border border-border bg-card p-4" data-testid={tid}>
      <div className="flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-widest font-semibold text-muted-foreground">{label}</span>
        <span className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-semibold border ${toneCls}`}>{icon}</span>
      </div>
      <div className="mt-2 font-display text-2xl font-bold tracking-tight">{value ?? 0}</div>
    </div>
  );
}

function Kpi({ icon, label, value, hint, spark, variant = "default", tid }) {
  const stripe = variant === "success" ? "bg-emerald-500" : "bg-primary";
  return (
    <motion.div variants={item}
      className="relative overflow-hidden rounded-xl border border-border bg-card p-5 hover:shadow-sm transition-shadow" data-testid={tid}>
      <div className={`absolute left-0 top-0 h-full w-[3px] ${stripe}`} />
      <div className="flex items-center justify-between text-muted-foreground">
        <span className="text-[11px] uppercase tracking-widest font-semibold">{label}</span>
        <div className="h-8 w-8 rounded-md bg-accent text-foreground grid place-items-center">{icon}</div>
      </div>
      <div className="mt-3 font-display text-3xl font-bold tracking-tight">{value}</div>
      <div className="text-xs text-muted-foreground mt-1">{hint}</div>
      {spark && spark.length > 1 && (
        <div className="mt-3 h-12 -mx-1">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={spark}>
              <defs>
                <linearGradient id={`g-${tid}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                </linearGradient>
              </defs>
              <Tooltip contentStyle={{background:"hsl(var(--popover))",border:"1px solid hsl(var(--border))",borderRadius:6,fontSize:11,padding:6}} labelFormatter={() => ""} />
              <XAxis dataKey="date" hide />
              <YAxis hide />
              <Area type="monotone" dataKey="count" stroke="hsl(var(--primary))" strokeWidth={1.5} fill={`url(#g-${tid})`} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </motion.div>
  );
}

function greeting() {
  const h = new Date().getHours();
  if (h < 5) return "Working late";
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}
function hintForScore(s) {
  if (s == null) return "—";
  if (s >= 80) return "Enterprise-grade pipeline";
  if (s >= 60) return "Solid mid-market";
  if (s >= 40) return "Warming up";
  return "Needs more traffic";
}

function IntChip({ name, data, Icon }) {
  const errored = data?.last_status === "error";
  const live = data?.mode === "live";
  const cls = errored ? "border-destructive/30 bg-destructive/5 text-destructive"
    : live ? "border-emerald-200 dark:border-emerald-900 bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300"
    : "border-border bg-muted text-muted-foreground";
  const label = errored ? "error" : live ? "live" : "mock";
  const StatusIcon = errored ? XCircle : live ? CheckCircle2 : Circle;
  return (
    <div className={`inline-flex items-center gap-2 rounded-md border px-2.5 py-1 text-xs ${cls}`}>
      <Icon className="h-3.5 w-3.5" /><span className="font-medium">{name}</span>
      <span className="opacity-70">·</span>
      <span className="inline-flex items-center gap-1 font-medium"><StatusIcon className="h-3 w-3" /> {label}</span>
      {data?.last_sync && <span className="opacity-70 hidden md:inline">· {timeAgo(data.last_sync)}</span>}
    </div>
  );
}
