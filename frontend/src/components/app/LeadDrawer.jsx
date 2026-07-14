import React, { useEffect, useState } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import api from "@/lib/api";
import { toast } from "sonner";
import { Loader2, Copy, RefreshCw, Trash2, Mail, Sparkles, CheckCircle2 } from "lucide-react";
import { scoreColor, statusColor, timeAgo } from "@/lib/utils";

const STATUSES = ["new", "qualifying", "qualified", "disqualified", "contacted", "converted"];

export default function LeadDrawer({ leadId, onClose, onChanged }) {
  const [lead, setLead] = useState(null);
  const [loading, setLoading] = useState(false);
  const [regen, setRegen] = useState(false);
  const open = !!leadId;

  useEffect(() => {
    if (!leadId) { setLead(null); return; }
    setLoading(true);
    api.get(`/leads/${leadId}`).then((r) => setLead(r.data)).finally(() => setLoading(false));
  }, [leadId]);

  const setStatus = async (status) => {
    const { data } = await api.patch(`/leads/${leadId}/status`, { status });
    setLead(data); onChanged?.();
    toast.success(`Status: ${status}`);
  };

  const regenerate = async () => {
    setRegen(true);
    try {
      const { data } = await api.post(`/leads/${leadId}/regenerate-email`);
      setLead(data); onChanged?.();
      toast.success("Email regenerated");
    } catch (e) { toast.error("Failed to regenerate"); }
    finally { setRegen(false); }
  };

  const del = async () => {
    if (!window.confirm("Delete this lead?")) return;
    await api.delete(`/leads/${leadId}`);
    onChanged?.(); onClose();
    toast.success("Lead deleted");
  };

  const copy = (text) => {
    navigator.clipboard.writeText(text || "");
    toast.success("Copied");
  };

  return (
    <Sheet open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <SheetContent side="right" className="w-full sm:max-w-2xl overflow-y-auto" data-testid="lead-drawer">
        {loading || !lead ? (
          <div className="grid place-items-center h-64 text-slate-400"><Loader2 className="h-5 w-5 animate-spin" /></div>
        ) : (
          <div>
            <SheetHeader className="text-left">
              <SheetTitle className="font-display text-2xl tracking-tight">{lead.name}</SheetTitle>
              <SheetDescription className="text-slate-500">{lead.job_title ? `${lead.job_title} · ` : ""}{lead.company} · {lead.email}</SheetDescription>
            </SheetHeader>

            <div className="flex flex-wrap items-center gap-2 mt-4">
              <span className={`score-badge border ${scoreColor(lead.qualification?.score)}`}>Score {lead.qualification?.score ?? "—"}</span>
              <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium border ${statusColor(lead.status)}`}>{lead.status}</span>
              <span className="text-xs text-slate-500 ml-auto">Created {timeAgo(lead.created_at)}</span>
            </div>

            <div className="mt-6 rounded-lg border border-slate-200 bg-slate-50/50 p-4">
              <div className="flex items-center gap-2 text-[#0044FF] mb-2">
                <Sparkles className="h-4 w-4" />
                <div className="text-xs uppercase tracking-widest font-bold">AI Qualification</div>
              </div>
              <p className="text-sm text-slate-800 leading-relaxed" data-testid="qualification-summary">{lead.qualification?.qualification_summary || "Not yet qualified."}</p>
              {lead.qualification?.key_signals?.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {lead.qualification.key_signals.map((s, i) => (
                    <li key={i} className="text-xs text-slate-600 flex items-start gap-2"><CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 mt-0.5 shrink-0" /> {s}</li>
                  ))}
                </ul>
              )}
              <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                <Meta label="Industry" value={lead.qualification?.industry} />
                <Meta label="Company size" value={lead.qualification?.company_size} />
                <Meta label="Intent" value={lead.qualification?.buying_intent} />
              </div>
              {lead.qualification?.recommended_action && (
                <div className="mt-3 text-xs">
                  <span className="text-slate-500">Recommended action:</span>{" "}
                  <span className="font-semibold text-slate-900">{lead.qualification.recommended_action}</span>
                  {lead.qualification.next_step_reason && <span className="text-slate-500"> — {lead.qualification.next_step_reason}</span>}
                </div>
              )}
            </div>

            <div className="mt-6">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2 text-[#0044FF]">
                  <Mail className="h-4 w-4" />
                  <div className="text-xs uppercase tracking-widest font-bold">AI Drafted Email</div>
                </div>
                <div className="flex items-center gap-2">
                  <button data-testid="copy-email-btn" onClick={() => copy(`Subject: ${lead.generated_email?.subject}\n\n${lead.generated_email?.body}`)} className="text-xs inline-flex items-center gap-1 text-slate-600 hover:text-slate-900 transition-colors"><Copy className="h-3 w-3" /> Copy</button>
                  <button data-testid="regen-email-btn" onClick={regenerate} disabled={regen} className="text-xs inline-flex items-center gap-1 text-slate-600 hover:text-slate-900 disabled:opacity-50 transition-colors">
                    {regen ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />} Regenerate
                  </button>
                </div>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-4">
                {lead.generated_email?.subject ? (
                  <>
                    <div className="text-sm font-semibold" data-testid="email-subject">{lead.generated_email.subject}</div>
                    <div className="mt-2 text-sm text-slate-700 whitespace-pre-wrap leading-relaxed" data-testid="email-body">{lead.generated_email.body}</div>
                  </>
                ) : <div className="text-sm text-slate-500">No email drafted yet.</div>}
              </div>
            </div>

            <div className="mt-6">
              <div className="text-xs uppercase tracking-widest font-bold text-slate-500 mb-2">Update status</div>
              <div className="flex flex-wrap gap-2">
                {STATUSES.map((s) => (
                  <button key={s} data-testid={`status-btn-${s}`} onClick={() => setStatus(s)}
                    className={`text-xs px-3 py-1 rounded-md border transition-colors ${lead.status === s ? "bg-[#0044FF] border-[#0044FF] text-white" : "border-slate-300 text-slate-700 hover:bg-slate-50"}`}>
                    {s}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-6">
              <div className="text-xs uppercase tracking-widest font-bold text-slate-500 mb-2">Activity Timeline</div>
              <ol className="space-y-3">
                {[...(lead.activities || [])].reverse().map((a) => (
                  <li key={a.id} className="grid grid-cols-[80px_1fr] gap-3 text-sm border-l-2 border-slate-200 pl-3">
                    <div className="text-xs text-slate-500 pt-0.5">{timeAgo(a.at)}</div>
                    <div>
                      <div className="text-slate-800">{a.message}</div>
                      <div className="text-xs text-slate-500 mt-0.5 font-mono">{a.type}</div>
                    </div>
                  </li>
                ))}
              </ol>
            </div>

            <div className="mt-8 flex justify-end pb-6">
              <button data-testid="delete-lead-btn" onClick={del} className="text-sm text-rose-600 hover:bg-rose-50 px-3 py-1.5 rounded-md inline-flex items-center gap-1 transition-colors">
                <Trash2 className="h-4 w-4" /> Delete lead
              </button>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}

function Meta({ label, value }) {
  return (
    <div className="rounded-md bg-white border border-slate-200 px-2 py-1.5">
      <div className="text-[10px] uppercase tracking-widest text-slate-500">{label}</div>
      <div className="text-xs font-semibold text-slate-900">{value || "—"}</div>
    </div>
  );
}
