import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid, PieChart, Pie, Cell } from "recharts";

const CHART_COLORS = ["#0044FF", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#14B8A6", "#F97316"];

export default function Analytics() {
  const [s, setS] = useState(null);
  useEffect(() => { api.get("/analytics/summary").then((r) => setS(r.data)); }, []);

  return (
    <div className="p-8 max-w-[1400px] mx-auto" data-testid="analytics-page">
      <div className="mb-8">
        <div className="overline mb-2">Reporting</div>
        <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tight">Analytics</h1>
        <p className="text-slate-500 mt-1 text-sm">Pipeline health, score distribution, and industry mix.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard title="Leads over time" subtitle="Last 14 days" testId="chart-timeline">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={s?.timeline || []} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#94a3b8" />
              <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" allowDecimals={false} />
              <Tooltip contentStyle={{ border: "1px solid #e2e8f0", borderRadius: 8, fontSize: 12 }} />
              <Line type="monotone" dataKey="count" stroke="#0044FF" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Score distribution" subtitle="Fit + intent buckets" testId="chart-distribution">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={s?.score_distribution || []} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="bucket" tick={{ fontSize: 11 }} stroke="#94a3b8" />
              <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" allowDecimals={false} />
              <Tooltip contentStyle={{ border: "1px solid #e2e8f0", borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="count" fill="#0044FF" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="By industry" subtitle="Top segments" testId="chart-industry">
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={s?.by_industry || []} dataKey="count" nameKey="industry" cx="50%" cy="50%" innerRadius={60} outerRadius={90} paddingAngle={2}>
                {(s?.by_industry || []).map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ border: "1px solid #e2e8f0", borderRadius: 8, fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
            {(s?.by_industry || []).map((r, i) => (
              <div key={r.industry} className="flex items-center gap-2 text-slate-600">
                <span className="h-2 w-2 rounded-sm" style={{ background: CHART_COLORS[i % CHART_COLORS.length] }} />
                {r.industry} · {r.count}
              </div>
            ))}
          </div>
        </ChartCard>

        <ChartCard title="Conversion funnel" subtitle="Live pipeline" testId="chart-funnel">
          <div className="space-y-3 py-4">
            {[
              { label: "Total leads", value: s?.total_leads ?? 0, color: "#0044FF" },
              { label: "Qualified", value: s?.qualified_leads ?? 0, color: "#10B981" },
              { label: "Conversion %", value: s ? `${s.conversion_rate}%` : "—", color: "#F59E0B" },
              { label: "Avg score", value: s?.avg_score ?? 0, color: "#8B5CF6" },
            ].map((r) => (
              <div key={r.label} className="flex items-center justify-between border-b border-slate-100 pb-2 last:border-0">
                <div className="flex items-center gap-3">
                  <span className="h-2.5 w-2.5 rounded-sm" style={{ background: r.color }} />
                  <span className="text-sm text-slate-700">{r.label}</span>
                </div>
                <div className="font-display text-xl font-bold tracking-tight">{r.value}</div>
              </div>
            ))}
          </div>
        </ChartCard>
      </div>
    </div>
  );
}

function ChartCard({ title, subtitle, testId, children }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6" data-testid={testId}>
      <div className="mb-4">
        <div className="overline">{subtitle}</div>
        <h3 className="font-display text-lg font-semibold mt-1">{title}</h3>
      </div>
      {children}
    </div>
  );
}
