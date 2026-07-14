import React, { useEffect, useState } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import api from "@/lib/api";
import { toast } from "sonner";
import { Loader2, Copy, RefreshCw, Trash2, Mail, Sparkles, CheckCircle2, ExternalLink, PlugZap } from "lucide-react";
import { scoreColor, statusColor, timeAgo } from "@/lib/utils";

const STATUSES = ["new", "qualifying", "qualified", "disqualified", "contacted", "converted"];

export default function LeadDrawer({ leadId, onClose, onChanged }) {
  const [lead, setLead] = useState(null);
  const [loading, setLoading] = useState(false);
  const [regen, setRegen] = useState(false);
  const [retrying, setRetrying] = useState(false);
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

  const retrySync = async () => {
    setRetrying(true);
    try {
      const { data } = await api.post(`/leads/${leadId}/retry-sync`);
      setLead(data); onChanged?.();
      toast.success("Integrations re-run");
    } catch (e) { toast.error(e?.response?.data?.detail || "Retry failed"); }
    finally { setRetrying(false); }
  };

  const del = async () => {
    if (!window.confirm("Delete this lead?")) return;
    await api.delete(`/leads/${leadId}`);
    onChanged?.(); onClose();
    toast.success("Lead deleted");
  };

  const copy = (text) => { navigator.clipboard.writeText(text || ""); toast.success("Copied"); };

  return (
    <Sheet open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <SheetContent side="right" className="w-full sm:max-w-2xl overflow-y-auto p-0 bg-background" data-testid="lead-drawer">
        {loading || !lead ? (
          <div className="grid place-items-center h-64 text-muted-foreground"><Loader2 className="h-5 w-5 animate-spin" /></div>
        ) : (
          <div className="p-6 sm:p-8">
            <SheetHeader className="text-left">
              <SheetTitle className="font-display text-2xl tracking-tight">{lead.name}</SheetTitle>
              <SheetDescription className="text-muted-foreground">
                {lead.job_title ? `${lead.job_title} · ` : ""}{lead.company} · {lead.email}
              </SheetDescription>
            </SheetHeader>

            <div className="flex flex-wrap items-center gap-2 mt-4">
              <span className={`score-badge border ${scoreColor(lead.qualification?.score)}`}>Score {lead.qualification?.score ?? "—"}</span>
              <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium border ${statusColor(lead.status)}`}>{lead.status}</span>
              {lead.website && (
                <a href={lead.website.startsWith("http") ? lead.website : `https://${lead.website}`} target="_blank" rel="noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors">
                  <ExternalLink className="h-3 w-3" /> {lead.website}
                </a>
              )}
              <span className="text-xs text-muted-foreground ml-auto">Created {timeAgo(lead.created_at)}</span>
            </div>

            {/* AI Qualification */}
            <div className="mt-6 rounded-lg border border-primary/20 bg-primary/[0.03] p-5">
              <div className="flex items-center gap-2 text-primary mb-3">
                <Sparkles className="h-4 w-4" />
                <div className="text-xs uppercase tracking-widest font-bold">AI Qualification</div>
              </div>
              <p className="text-sm leading-relaxed" data-testid="qualification-summary">
                {lead.qualification?.qualification_summary || "Not yet qualified."}
              </p>
              {lead.qualification?.key_signals?.length > 0 && (
                <ul className="mt-3 space-y-1.5">
                  {lead.qualification.key_signals.map((s, i) => (
                    <li key={i} className="text-xs flex items-start gap-2">
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 dark:text-emerald-400 mt-0.5 shrink-0" />
                      <span className="text-foreground/90">{s}</span>
                    </li>
                  ))}
                </ul>
              )}
              <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
                <Meta label="Industry" value={lead.qualification?.industry} />
                <Meta label="Company size" value={lead.qualification?.company_size} />
                <Meta label="Intent" value={lead.qualification?.buying_intent} />
              </div>
              {lead.qualification?.recommended_action && (
                <div className="mt-4 text-xs">
                  <span className="text-muted-foreground">Recommended action:</span>{" "}
                  <span className="font-semibold">{lead.qualification.recommended_action}</span>
                  {lead.qualification.next_step_reason && <span className="text-muted-foreground"> — {lead.qualification.next_step_reason}</span>}
                </div>
              )}
            </div>

            {/* Email */}
            <div className="mt-6">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2 text-primary">
                  <Mail className="h-4 w-4" />
                  <div className="text-xs uppercase tracking-widest font-bold">AI Drafted Email</div>
                </div>
                <div className="flex items-center gap-1">
                  <button data-testid="copy-email-btn" onClick={() => copy(`Subject: ${lead.generated_email?.subject}\n\n${lead.generated_email?.body}`)}
                    className="text-xs inline-flex items-center gap-1 h-8 px-2 rounded-md hover:bg-accent transition-colors">
                    <Copy className="h-3 w-3" /> Copy
                  </button>
                  <button data-testid="regen-email-btn" onClick={regenerate} disabled={regen}
                    className="text-xs inline-flex items-center gap-1 h-8 px-2 rounded-md hover:bg-accent disabled:opacity-50 transition-colors">
                    {regen ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />} Regenerate
                  </button>
                </div>
              </div>
              <div className="rounded-lg border border-border bg-card p-4">
                {lead.generated_email?.subject ? (
                  <>
                    <div className="text-sm font-semibold" data-testid="email-subject">{lead.generated_email.subject}</div>
                    <div className="mt-2 text-sm text-foreground/90 whitespace-pre-wrap leading-relaxed" data-testid="email-body">
                      {lead.generated_email.body}
                    </div>
                  </>
                ) : <div className="text-sm text-muted-foreground">No email drafted yet.</div>}
              </div>
            </div>

            {/* Status */}
            <div className="mt-6">
              <div className="overline mb-2">Update status</div>
              <div className="flex flex-wrap gap-2">
                {STATUSES.map((st) => (
                  <button key={st} data-testid={`status-btn-${st}`} onClick={() => setStatus(st)}
                    className={`text-xs px-3 py-1.5 rounded-md border transition-colors ${lead.status === st ? "bg-primary border-primary text-primary-foreground" : "border-border hover:bg-accent"}`}>
                    {st}
                  </button>
                ))}
              </div>
            </div>

            {/* Timeline */}
            <div className="mt-6">
              <div className="flex items-center justify-between mb-2">
                <div className="overline">Activity timeline</div>
                <button onClick={retrySync} disabled={retrying}
                  data-testid="retry-sync-btn"
                  className="inline-flex items-center gap-1 h-8 px-3 text-xs rounded-md border border-border bg-background hover:bg-accent transition-colors disabled:opacity-60">
                  {retrying ? <Loader2 className="h-3 w-3 animate-spin" /> : <PlugZap className="h-3 w-3" />} Retry integrations
                </button>
              </div>
              <ol className="space-y-3 border-l-2 border-border pl-4">
                {[...(lead.activities || [])].reverse().map((a) => {
                  const md = a.metadata || {};
                  const isError = md.status === "error";
                  const isMocked = md.status === "mocked";
                  const isSuccess = md.status === "success";
                  return (
                    <li key={a.id} className="text-sm relative">
                      <span className={`absolute -left-[22px] top-1.5 h-2.5 w-2.5 rounded-full ring-2 ring-background ${
                        isError ? "bg-destructive" : isSuccess ? "bg-emerald-500" : isMocked ? "bg-amber-500" : "bg-primary/60"
                      }`} />
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="text-foreground line-clamp-2">{a.message}</div>
                          <div className="text-xs text-muted-foreground mt-0.5 font-mono flex items-center gap-2">
                            <span>{a.type}</span>
                            {isError && <span className="text-destructive">· error</span>}
                            {isMocked && <span className="text-amber-600 dark:text-amber-400">· mock</span>}
                            {md.attempts > 1 && <span>· {md.attempts} attempts</span>}
                          </div>
                        </div>
                        <div className="text-xs text-muted-foreground shrink-0">{timeAgo(a.at)}</div>
                      </div>
                    </li>
                  );
                })}
              </ol>
            </div>

            <div className="mt-8 flex justify-end pb-4">
              <button data-testid="delete-lead-btn" onClick={del}
                className="text-sm text-destructive hover:bg-destructive/10 px-3 py-1.5 rounded-md inline-flex items-center gap-1 transition-colors">
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
    <div className="rounded-md bg-background border border-border px-2.5 py-1.5">
      <div className="text-[10px] uppercase tracking-widest text-muted-foreground">{label}</div>
      <div className="text-xs font-semibold mt-0.5">{value || "—"}</div>
    </div>
  );
}
