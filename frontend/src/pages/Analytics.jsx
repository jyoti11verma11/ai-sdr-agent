import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart,
  Line, CartesianGrid, PieChart, Pie, Cell,
} from "recharts";
import { motion } from "framer-motion";
import { LineChart as LineIcon, PieChart as PieIcon, BarChart3, TrendingUp, Brain, Target, Timer, Zap, Percent } from "lucide-react";
import { SkeletonBlock } from "@/components/app/Skeletons";
import EmptyState from "@/components/app/EmptyState";
import { scoreColor } from "@/lib/utils";

const CHART_COLORS = ["hsl(var(--chart-1))", "hsl(var(--chart-2))", "hsl(var(--chart-3))", "hsl(var(--chart-4))", "hsl(var(--chart-5))", "#EC4899", "#14B8A6", "#F97316"];

const tooltipStyle = {
  background: "hsl(var(--popover))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 8,
  fontSize: 12,
  color: "hsl(var(--foreground))",
};

export default function Analytics() {
  const [s, setS] = useState(null);
  const [ai, setAI] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = () => {
    setLoading(true); setError(null);
    Promise.all([api.get("/analytics/summary"), api.get("/analytics/ai")])
      .then(([r, a]) => { setS(r.data); setAI(a.data); })
      .catch(() => setError("Couldn't load analytics"))
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const empty = !loading && s && (s.total_leads ?? 0) === 0;

  return (
    <div className="px-4 sm:px-6 lg:px-8 py-6 lg:py-8 max-w-[1400px] mx-auto" data-testid="analytics-page">
      <div className="mb-6 lg:mb-8">
        <div className="overline mb-2">Reporting</div>
        <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tighter">Analytics</h1>
        <p className="text-sm text-muted-foreground mt-1.5">Pipeline health, score distribution, and industry mix.</p>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-destructive/30 bg-destructive/5 text-destructive text-sm px-4 py-3 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={load} className="text-xs underline">Retry</button>
        </div>
      )}

      {empty ? (
        <EmptyState
          icon={<BarChart3 className="h-5 w-5" />}
          title="No pipeline data yet"
          description="Once you capture a few leads the analytics will populate automatically."
        />
      ) : (
        <>
          {/* AI Analytics (Phase 3) */}
          {ai && (
            <div className="mb-6 lg:mb-8" data-testid="ai-analytics-section">
              <div className="flex items-center gap-2 mb-3">
                <Brain className="h-4 w-4 text-primary" />
                <div className="overline">AI performance</div>
              </div>
              <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-4">
                <AIMetric icon={<Zap className="h-3.5 w-3.5" />} label="Avg AI score" value={ai.avg_ai_score} tid="ai-avg-score" />
                <AIMetric icon={<TrendingUp className="h-3.5 w-3.5" />} label="High-intent leads" value={ai.high_intent_leads} tid="ai-high-intent" />
                <AIMetric icon={<Percent className="h-3.5 w-3.5" />} label="Qualification success" value={`${ai.qualification_success_rate}%`} sub={`${ai.qualification_success_count}/${ai.qualification_total}`} tid="ai-success-rate" />
                <AIMetric icon={<Timer className="h-3.5 w-3.5" />} label="Avg processing" value={ai.avg_processing_ms ? `${(ai.avg_processing_ms/1000).toFixed(1)}s` : "—"} tid="ai-latency" />
                <AIMetric icon={<Target className="h-3.5 w-3.5" />} label="ICP matches" value={ai.top_icp_matches.length} tid="ai-icp-count" />
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
                <div className="rounded-xl border border-border bg-card p-6" data-testid="ai-top-icp">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <div className="overline">ICP Matches</div>
                      <h3 className="font-display text-lg font-semibold mt-1 tracking-tight">Top fits by AI</h3>
                    </div>
                    <Target className="h-4 w-4 text-primary" />
                  </div>
                  {ai.top_icp_matches.length === 0 ? (
                    <div className="text-sm text-muted-foreground">No ICP matches yet.</div>
                  ) : (
                    <ul className="space-y-2">
                      {ai.top_icp_matches.map((l) => (
                        <li key={l.lead_id} className="flex items-start gap-3 rounded-md border border-border p-2.5">
                          <span className={`score-badge border shrink-0 mt-0.5 ${scoreColor(l.score)}`}>{l.score}</span>
                          <div className="min-w-0 flex-1">
                            <div className="text-sm font-semibold truncate">{l.name} · <span className="font-normal text-muted-foreground">{l.company}</span></div>
                            <div className="text-xs text-muted-foreground mt-0.5">{l.industry}</div>
                            {l.reason && <div className="text-xs text-foreground/80 mt-1 line-clamp-2">{l.reason}</div>}
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="rounded-xl border border-border bg-card p-6" data-testid="ai-industry-dist">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <div className="overline">Distribution</div>
                      <h3 className="font-display text-lg font-semibold mt-1 tracking-tight">Industries by AI</h3>
                    </div>
                    <PieIcon className="h-4 w-4 text-primary" />
                  </div>
                  {ai.industry_distribution.length === 0 ? (
                    <div className="text-sm text-muted-foreground">Not enough data.</div>
                  ) : (
                    <div className="space-y-2">
                      {ai.industry_distribution.map((r, i) => (
                        <div key={r.industry}>
                          <div className="flex items-center justify-between text-xs mb-0.5">
                            <span className="text-foreground/90">{r.industry}</span>
                            <span className="text-muted-foreground font-mono">{r.count} · {r.pct}%</span>
                          </div>
                          <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${r.pct}%`, background: CHART_COLORS[i % CHART_COLORS.length] }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Pipeline charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6">
          <ChartCard title="Leads over time" subtitle="Last 14 days" icon={<LineIcon className="h-4 w-4" />} testId="chart-timeline" loading={loading}>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={s?.timeline || []} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} tickLine={false} stroke="hsl(var(--border))" />
                <YAxis tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} tickLine={false} stroke="hsl(var(--border))" allowDecimals={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Line type="monotone" dataKey="count" stroke="hsl(var(--chart-1))" strokeWidth={2.5} dot={{ r: 3, strokeWidth: 0, fill: "hsl(var(--chart-1))" }} activeDot={{ r: 5 }} />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Score distribution" subtitle="Fit + intent buckets" icon={<BarChart3 className="h-4 w-4" />} testId="chart-distribution" loading={loading}>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={s?.score_distribution || []} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="bucket" tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} tickLine={false} stroke="hsl(var(--border))" />
                <YAxis tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} tickLine={false} stroke="hsl(var(--border))" allowDecimals={false} />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "hsl(var(--accent))" }} />
                <Bar dataKey="count" fill="hsl(var(--chart-1))" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="By industry" subtitle="Top segments" icon={<PieIcon className="h-4 w-4" />} testId="chart-industry" loading={loading}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center">
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie data={s?.by_industry || []} dataKey="count" nameKey="industry" cx="50%" cy="50%" innerRadius={56} outerRadius={90} paddingAngle={2} stroke="hsl(var(--card))">
                    {(s?.by_industry || []).map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-1.5">
                {(s?.by_industry || []).map((r, i) => (
                  <div key={r.industry} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className="h-2.5 w-2.5 rounded-sm shrink-0" style={{ background: CHART_COLORS[i % CHART_COLORS.length] }} />
                      <span className="text-foreground/90">{r.industry}</span>
                    </div>
                    <span className="text-muted-foreground font-mono">{r.count}</span>
                  </div>
                ))}
              </div>
            </div>
          </ChartCard>

          <ChartCard title="Conversion funnel" subtitle="Live pipeline" icon={<TrendingUp className="h-4 w-4" />} testId="chart-funnel" loading={loading}>
            <div className="space-y-2.5 py-2">
              {[
                { label: "Total leads", value: s?.total_leads ?? 0, pct: 100, color: "hsl(var(--chart-1))" },
                { label: "Qualified", value: s?.qualified_leads ?? 0, pct: s?.qualified_rate ?? 0, color: "hsl(var(--chart-2))" },
                { label: "Conversion %", value: `${s?.conversion_rate ?? 0}%`, pct: s?.conversion_rate ?? 0, color: "hsl(var(--chart-3))" },
                { label: "Avg score", value: s?.avg_score ?? 0, pct: Math.min(100, s?.avg_score ?? 0), color: "hsl(var(--chart-5))" },
              ].map((r) => (
                <div key={r.label}>
                  <div className="flex items-center justify-between text-sm mb-1">
                    <div className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full" style={{ background: r.color }} />
                      <span className="text-foreground/90">{r.label}</span>
                    </div>
                    <span className="font-display font-bold tracking-tight">{r.value}</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                    <div className="h-full rounded-full transition-all duration-500" style={{ width: `${r.pct}%`, background: r.color }} />
                  </div>
                </div>
              ))}
            </div>
          </ChartCard>
        </div>
        </>
      )}
    </div>
  );
}

function AIMetric({ icon, label, value, sub, tid }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4" data-testid={tid}>
      <div className="flex items-center justify-between text-muted-foreground">
        <span className="text-[10px] uppercase tracking-widest font-semibold">{label}</span>
        <div className="h-6 w-6 rounded-md bg-primary/10 text-primary grid place-items-center">{icon}</div>
      </div>
      <div className="mt-2 font-display text-2xl font-bold tracking-tight">{value}</div>
      {sub && <div className="text-[10px] text-muted-foreground mt-0.5 font-mono">{sub}</div>}
    </div>
  );
}

function ChartCard({ title, subtitle, icon, testId, loading, children }) {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}
      className="rounded-xl border border-border bg-card p-6" data-testid={testId}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="overline">{subtitle}</div>
          <h3 className="font-display text-lg font-semibold mt-1 tracking-tight">{title}</h3>
        </div>
        <div className="h-8 w-8 rounded-md bg-accent grid place-items-center text-muted-foreground">{icon}</div>
      </div>
      {loading ? <SkeletonBlock className="h-64 w-full rounded-md" /> : children}
    </motion.div>
  );
}
