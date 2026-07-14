import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Loader2, Plus, Search } from "lucide-react";
import { scoreColor, statusColor, timeAgo } from "@/lib/utils";
import NewLeadDialog from "@/components/app/NewLeadDialog";
import LeadDrawer from "@/components/app/LeadDrawer";

export default function Leads() {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [statusF, setStatusF] = useState("");
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const params = {};
      if (q) params.q = q;
      if (statusF) params.status = statusF;
      const { data } = await api.get("/leads", { params });
      setLeads(data);
    } catch (e) { toast.error("Failed to load leads"); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [statusF]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [q]);

  return (
    <div className="p-8 max-w-[1400px] mx-auto" data-testid="leads-page">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <div className="overline mb-2">Pipeline</div>
          <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tight">Leads</h1>
          <p className="text-slate-500 mt-1 text-sm">All inbound qualified by your AI SDR.</p>
        </div>
        <button data-testid="new-lead-btn" onClick={() => setOpen(true)}
          className="inline-flex items-center gap-2 bg-[#0044FF] hover:bg-[#0033CC] text-white px-4 h-10 rounded-md text-sm font-medium transition-colors">
          <Plus className="h-4 w-4" /> New lead
        </button>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-md">
          <Search className="h-4 w-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input data-testid="leads-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, email or company…"
            className="w-full h-10 pl-9 pr-3 rounded-md border border-slate-200 bg-white outline-none focus:border-[#0044FF] focus:ring-2 focus:ring-[#0044FF]/20 transition-colors" />
        </div>
        <select data-testid="leads-status-filter" value={statusF} onChange={(e) => setStatusF(e.target.value)}
          className="h-10 px-3 rounded-md border border-slate-200 bg-white text-sm">
          <option value="">All statuses</option>
          <option value="qualifying">Qualifying</option>
          <option value="qualified">Qualified</option>
          <option value="disqualified">Disqualified</option>
          <option value="contacted">Contacted</option>
          <option value="converted">Converted</option>
        </select>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        <table className="w-full text-sm" data-testid="leads-table">
          <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500 border-b border-slate-200">
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
            {loading && <tr><td colSpan={7} className="p-8 text-center text-slate-400"><Loader2 className="h-4 w-4 animate-spin inline mr-2" /> loading…</td></tr>}
            {!loading && leads.length === 0 && (
              <tr><td colSpan={7} className="p-12 text-center text-slate-500">No leads. Click "New lead" to capture one.</td></tr>
            )}
            {leads.map((l) => {
              const q_ = l.qualification || {};
              return (
                <tr key={l.id} data-testid={`lead-row-${l.id}`}
                  onClick={() => setSelected(l.id)}
                  className="border-b border-slate-100 last:border-0 hover:bg-slate-50 cursor-pointer transition-colors">
                  <td className="px-4 py-3">
                    <div className="font-medium">{l.name}</div>
                    <div className="text-xs text-slate-500">{l.email}</div>
                  </td>
                  <td className="px-4 py-3">
                    <div>{l.company}</div>
                    <div className="text-xs text-slate-500">{l.job_title || "—"}</div>
                  </td>
                  <td className="px-4 py-3 text-slate-700">{q_.industry || "—"}</td>
                  <td className="px-4 py-3 text-slate-700">{q_.buying_intent || "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`score-badge border ${scoreColor(q_.score)}`}>{q_.score ?? "—"}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium border ${statusColor(l.status)}`}>{l.status}</span>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">{timeAgo(l.created_at)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <NewLeadDialog open={open} onOpenChange={setOpen} onCreated={load} />
      <LeadDrawer leadId={selected} onClose={() => setSelected(null)} onChanged={load} />
    </div>
  );
}
