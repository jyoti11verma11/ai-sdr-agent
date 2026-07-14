import React, { useEffect, useState } from "react";
import api, { API } from "@/lib/api";
import { Download } from "lucide-react";
import { SkeletonBlock } from "@/components/app/Skeletons";
import { timeAgo } from "@/lib/utils";

export default function AuditLogs() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterAction, setFilterAction] = useState("");

  const load = async () => {
    setLoading(true);
    try { const { data } = await api.get("/audit", { params: filterAction ? { action: filterAction } : {} }); setRows(data); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [filterAction]);

  const downloadCsv = () => {
    const token = localStorage.getItem("sdr_token");
    // Use fetch to hit protected endpoint then blob-download
    fetch(`${API}/audit/export.csv`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.text())
      .then((csv) => {
        const blob = new Blob([csv], { type: "text/csv" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a"); a.href = url; a.download = "audit.csv"; a.click();
        URL.revokeObjectURL(url);
      });
  };

  return (
    <div className="px-4 sm:px-6 lg:px-8 py-6 lg:py-8 max-w-6xl mx-auto" data-testid="audit-page">
      <div className="mb-6 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <div className="overline mb-2">Compliance</div>
          <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tighter">Audit logs</h1>
          <p className="text-sm text-muted-foreground mt-1.5">Every mutating action across the workspace.</p>
        </div>
        <div className="flex items-center gap-2">
          <input value={filterAction} onChange={(e) => setFilterAction(e.target.value)}
            placeholder="Filter action (e.g. update.lead_stage)"
            className="h-10 px-3 rounded-md border border-border bg-background field-focus text-sm w-72" />
          <button onClick={downloadCsv} data-testid="export-csv"
            className="inline-flex items-center gap-1.5 h-10 px-3 rounded-md border border-border bg-card hover:bg-accent text-sm transition-colors">
            <Download className="h-4 w-4" /> Export CSV
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground border-b border-border">
            <tr>
              <th className="text-left px-4 py-3 font-semibold">When</th>
              <th className="text-left px-4 py-3 font-semibold">User</th>
              <th className="text-left px-4 py-3 font-semibold">Action</th>
              <th className="text-left px-4 py-3 font-semibold">Resource</th>
              <th className="text-left px-4 py-3 font-semibold">Change</th>
            </tr>
          </thead>
          <tbody>
            {loading && [...Array(6)].map((_, i) => (
              <tr key={i}><td colSpan={5} className="p-0"><SkeletonBlock className="h-10 rounded-none" /></td></tr>
            ))}
            {!loading && rows.length === 0 && (
              <tr><td colSpan={5} className="p-8 text-center text-muted-foreground">No audit events yet.</td></tr>
            )}
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-border last:border-0 hover:bg-accent/30" data-testid={`audit-row-${r.id}`}>
                <td className="px-4 py-3 text-xs text-muted-foreground">{timeAgo(r.at)}</td>
                <td className="px-4 py-3">{r.user_email}</td>
                <td className="px-4 py-3"><span className="font-mono text-xs">{r.action}</span></td>
                <td className="px-4 py-3"><span className="text-xs">{r.resource_type}{r.resource_id ? " · " + r.resource_id.slice(0, 8) : ""}</span></td>
                <td className="px-4 py-3 text-xs font-mono max-w-lg">
                  {Object.keys(r.old_value || {}).length > 0 && <span className="text-rose-600 dark:text-rose-400">− {JSON.stringify(r.old_value)}</span>}
                  {Object.keys(r.old_value || {}).length > 0 && Object.keys(r.new_value || {}).length > 0 && <br />}
                  {Object.keys(r.new_value || {}).length > 0 && <span className="text-emerald-600 dark:text-emerald-400">+ {JSON.stringify(r.new_value)}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
