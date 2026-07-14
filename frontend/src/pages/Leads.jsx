import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Loader2, Plus, Search, SlidersHorizontal, Users } from "lucide-react";
import { scoreColor, statusColor, timeAgo } from "@/lib/utils";
import NewLeadDialog from "@/components/app/NewLeadDialog";
import LeadDrawer from "@/components/app/LeadDrawer";
import { SkeletonRow } from "@/components/app/Skeletons";
import EmptyState from "@/components/app/EmptyState";
import { motion } from "framer-motion";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "qualifying", label: "Qualifying" },
  { value: "qualified", label: "Qualified" },
  { value: "disqualified", label: "Disqualified" },
  { value: "contacted", label: "Contacted" },
  { value: "converted", label: "Converted" },
];

export default function Leads() {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [statusF, setStatusF] = useState("");
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (q) params.q = q;
      if (statusF) params.status = statusF;
      const { data } = await api.get("/leads", { params });
      setLeads(data);
    } catch (e) {
      setError("Failed to load leads");
      toast.error("Failed to load leads");
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [statusF]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); /* eslint-disable-next-line */ }, [q]);

  return (
    <div className="px-4 sm:px-6 lg:px-8 py-6 lg:py-8 max-w-[1400px] mx-auto" data-testid="leads-page">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-6">
        <div>
          <div className="overline mb-2">Pipeline</div>
          <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tighter">Leads</h1>
          <p className="text-sm text-muted-foreground mt-1.5">Every inbound qualified by your AI SDR.</p>
        </div>
        <button data-testid="new-lead-btn" onClick={() => setOpen(true)}
          className="inline-flex items-center gap-2 bg-primary hover:bg-primary/90 text-primary-foreground px-4 h-10 rounded-md text-sm font-medium transition-colors shadow-sm shadow-primary/20">
          <Plus className="h-4 w-4" /> New lead
        </button>
      </div>

      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-lg">
          <Search className="h-4 w-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2" />
          <input data-testid="leads-search" value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Search name, email or company…"
            className="w-full h-10 pl-9 pr-3 rounded-md border border-border bg-card field-focus text-sm" />
        </div>
        <div className="relative">
          <SlidersHorizontal className="h-4 w-4 text-muted-foreground absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <select data-testid="leads-status-filter" value={statusF} onChange={(e) => setStatusF(e.target.value)}
            className="h-10 pl-9 pr-8 rounded-md border border-border bg-card text-sm appearance-none">
            {STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div className="text-xs text-muted-foreground sm:ml-auto">
          {loading ? "loading…" : `${leads.length} lead${leads.length === 1 ? "" : "s"}`}
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 text-destructive text-sm px-4 py-3 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={load} className="text-xs underline">Retry</button>
        </div>
      )}

      {/* Desktop table */}
      <div className="hidden md:block rounded-xl border border-border bg-card overflow-hidden">
        <table className="w-full text-sm" data-testid="leads-table">
          <thead className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground border-b border-border">
            <tr>
              <th className="text-left px-4 py-3 font-semibold">Lead</th>
              <th className="text-left px-4 py-3 font-semibold">Company</th>
              <th className="text-left px-4 py-3 font-semibold">Industry</th>
              <th className="text-left px-4 py-3 font-semibold">Intent</th>
              <th className="text-left px-4 py-3 font-semibold">Score</th>
              <th className="text-left px-4 py-3 font-semibold">Status</th>
              <th className="text-left px-4 py-3 font-semibold">Created</th>
            </tr>
          </thead>
          <tbody>
            {loading && [...Array(5)].map((_, i) => (
              <tr key={i}><td colSpan={7} className="p-0"><SkeletonRow /></td></tr>
            ))}
            {!loading && leads.length === 0 && (
              <tr>
                <td colSpan={7} className="p-0">
                  <EmptyState
                    icon={<Users className="h-5 w-5" />}
                    title={q || statusF ? "No matching leads" : "No leads yet"}
                    description={q || statusF ? "Try clearing your filters." : "Capture your first inbound and let the AI qualify it in seconds."}
                    className="border-0 bg-transparent"
                    action={!q && !statusF && (
                      <button onClick={() => setOpen(true)} data-testid="leads-empty-new"
                        className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-4 h-9 rounded-md text-sm font-medium hover:bg-primary/90 transition-colors">
                        <Plus className="h-4 w-4" /> New lead
                      </button>
                    )}
                  />
                </td>
              </tr>
            )}
            {leads.map((l) => {
              const q_ = l.qualification || {};
              return (
                <motion.tr key={l.id} data-testid={`lead-row-${l.id}`}
                  onClick={() => setSelected(l.id)}
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }}
                  className="border-b border-border last:border-0 hover:bg-accent/50 cursor-pointer transition-colors">
                  <td className="px-4 py-3">
                    <div className="font-medium">{l.name}</div>
                    <div className="text-xs text-muted-foreground">{l.email}</div>
                  </td>
                  <td className="px-4 py-3">
                    <div>{l.company}</div>
                    <div className="text-xs text-muted-foreground">{l.job_title || "—"}</div>
                  </td>
                  <td className="px-4 py-3 text-foreground/80">{q_.industry || "—"}</td>
                  <td className="px-4 py-3 text-foreground/80">{q_.buying_intent || "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`score-badge border ${scoreColor(q_.score)}`}>{q_.score ?? "—"}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium border ${statusColor(l.status)}`}>{l.status}</span>
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">{timeAgo(l.created_at)}</td>
                </motion.tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile card list */}
      <div className="md:hidden space-y-3">
        {loading && [...Array(3)].map((_, i) => (
          <div key={i} className="rounded-xl border border-border bg-card p-4 shimmer h-24" />
        ))}
        {!loading && leads.length === 0 && (
          <EmptyState
            icon={<Users className="h-5 w-5" />}
            title={q || statusF ? "No matching leads" : "No leads yet"}
            description={q || statusF ? "Try clearing your filters." : "Capture your first inbound and let the AI qualify it in seconds."}
            action={!q && !statusF && (
              <button onClick={() => setOpen(true)} className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-4 h-9 rounded-md text-sm font-medium">
                <Plus className="h-4 w-4" /> New lead
              </button>
            )}
          />
        )}
        {leads.map((l) => {
          const q_ = l.qualification || {};
          return (
            <button key={l.id} onClick={() => setSelected(l.id)}
              data-testid={`lead-card-${l.id}`}
              className="w-full text-left rounded-xl border border-border bg-card p-4 hover:border-primary/40 transition-colors">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="font-semibold truncate">{l.name}</div>
                  <div className="text-xs text-muted-foreground truncate">{l.company} · {l.job_title || "—"}</div>
                </div>
                <span className={`score-badge border shrink-0 ${scoreColor(q_.score)}`}>{q_.score ?? "—"}</span>
              </div>
              <div className="flex items-center gap-2 mt-3 text-xs">
                <span className={`inline-flex items-center rounded-md px-2 py-0.5 border ${statusColor(l.status)}`}>{l.status}</span>
                {q_.industry && <span className="text-muted-foreground">· {q_.industry}</span>}
                <span className="text-muted-foreground ml-auto">{timeAgo(l.created_at)}</span>
              </div>
            </button>
          );
        })}
      </div>

      <NewLeadDialog open={open} onOpenChange={setOpen} onCreated={load} />
      <LeadDrawer leadId={selected} onClose={() => setSelected(null)} onChanged={load} />
    </div>
  );
}
