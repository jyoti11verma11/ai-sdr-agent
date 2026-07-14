import React, { useEffect, useState } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import api from "@/lib/api";
import { toast } from "sonner";
import {
  Loader2, Copy, RefreshCw, Trash2, Mail, Sparkles, CheckCircle2, ExternalLink,
  PlugZap, Linkedin, Send, Clock, LoaderPinwheel, AlertTriangle, Brain
} from "lucide-react";
import { scoreColor, statusColor, timeAgo } from "@/lib/utils";

const STATUSES = ["new", "qualifying", "qualified", "disqualified", "contacted", "converted"];

export default function LeadDrawer({ leadId, onClose, onChanged }) {
  const [lead, setLead] = useState(null);
  const [decisions, setDecisions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [regenLoading, setRegenLoading] = useState("");
  const [retrying, setRetrying] = useState(false);
  const open = !!leadId;

  const load = async () => {
    setLoading(true);
    try {
      const [{ data }, { data: dec }] = await Promise.all([
        api.get(`/leads/${leadId}`),
        api.get(`/leads/${leadId}/decisions`),
      ]);
      setLead(data); setDecisions(dec);
    } finally { setLoading(false); }
  };

  useEffect(() => {
    if (!leadId) { setLead(null); setDecisions([]); return; }
    load();
    // Poll while still processing
    const t = setInterval(async () => {
      try {
        const { data } = await api.get(`/leads/${leadId}`);
        setLead(data);
        if (data.processing_status === "qualified" || data.processing_status === "failed") {
          const { data: dec } = await api.get(`/leads/${leadId}/decisions`);
          setDecisions(dec);
          clearInterval(t);
        }
      } catch {}
    }, 3000);
    return () => clearInterval(t);
    // eslint-disable-next-line
  }, [leadId]);

  const setStatus = async (status) => {
    const { data } = await api.patch(`/leads/${leadId}/status`, { status });
    setLead(data); onChanged?.();
    toast.success(`Status: ${status}`);
  };

  const regenerate = async (type) => {
    setRegenLoading(type);
    try {
      const { data } = await api.post(`/leads/${leadId}/regenerate?type=${type}`);
      setLead(data); onChanged?.();
      const { data: dec } = await api.get(`/leads/${leadId}/decisions`);
      setDecisions(dec);
      toast.success(`Regenerated ${type.replace("_", " ")}`);
    } catch (e) { toast.error("Failed to regenerate"); }
    finally { setRegenLoading(""); }
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
    onChanged?.(); onClose(); toast.success("Lead deleted");
  };

  const copy = (text) => { navigator.clipboard.writeText(text || ""); toast.success("Copied"); };

  const proc = lead?.processing_status;
  const isProcessing = proc === "pending" || proc === "analyzing";

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
              <ProcPill status={proc} />
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

            {isProcessing && (
              <div className="mt-6 rounded-lg border border-primary/30 bg-primary/5 p-4 flex items-center gap-3" data-testid="processing-banner">
                <LoaderPinwheel className="h-4 w-4 text-primary animate-spin shrink-0" />
                <div className="text-sm">
                  <div className="font-medium">AI is qualifying this lead…</div>
                  <div className="text-xs text-muted-foreground">This usually takes 5–15 seconds. This panel will update automatically.</div>
                </div>
              </div>
            )}

            {/* AI Qualification */}
            {lead.qualification?.qualification_summary && (
              <div className="mt-6 rounded-lg border border-primary/20 bg-primary/[0.03] p-5">
                <div className="flex items-center gap-2 text-primary mb-3">
                  <Sparkles className="h-4 w-4" />
                  <div className="text-xs uppercase tracking-widest font-bold">AI Qualification</div>
                </div>
                <p className="text-sm leading-relaxed" data-testid="qualification-summary">{lead.qualification.qualification_summary}</p>
                {lead.qualification.key_signals?.length > 0 && (
                  <ul className="mt-3 space-y-1.5">
                    {lead.qualification.key_signals.map((s, i) => (
                      <li key={i} className="text-xs flex items-start gap-2">
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 dark:text-emerald-400 mt-0.5 shrink-0" />
                        <span className="text-foreground/90">{s}</span>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                  <Meta label="Industry" value={lead.qualification.industry} />
                  <Meta label="Company size" value={lead.qualification.company_size} />
                  <Meta label="Business type" value={lead.qualification.business_type} />
                  <Meta label="Intent" value={lead.qualification.buying_intent} />
                  <Meta label="Urgency" value={lead.qualification.urgency} />
                  <Meta label="DM probability"
                    value={lead.qualification.decision_maker_probability != null
                      ? `${lead.qualification.decision_maker_probability}%` : "—"} />
                </div>
                {lead.qualification.icp_match !== null && lead.qualification.icp_match !== undefined && (
                  <div className="mt-3 flex items-start gap-2 rounded-md border border-border bg-background/60 p-2.5">
                    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-semibold border shrink-0 ${
                      lead.qualification.icp_match
                        ? "bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900"
                        : "bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-900"
                    }`}>
                      {lead.qualification.icp_match ? "ICP MATCH" : "NOT ICP"}
                    </span>
                    <div className="text-xs text-foreground/90 leading-relaxed">{lead.qualification.icp_match_reasoning}</div>
                  </div>
                )}
                {lead.qualification.score_explanation && (
                  <div className="mt-3">
                    <div className="text-[10px] uppercase tracking-widest text-muted-foreground font-bold mb-1">Why this score</div>
                    <p className="text-xs text-foreground/90 leading-relaxed">{lead.qualification.score_explanation}</p>
                  </div>
                )}
              </div>
            )}

            {/* Next Best Action */}
            {lead.qualification?.recommended_action && (
              <div className="mt-5 rounded-lg border border-border bg-card p-4">
                <div className="flex items-center gap-2 text-primary mb-2">
                  <Brain className="h-4 w-4" />
                  <div className="text-xs uppercase tracking-widest font-bold">Next Best Action</div>
                </div>
                <div className="text-lg font-semibold" data-testid="next-best-action">{lead.qualification.recommended_action}</div>
                {(lead.qualification.action_reasoning || lead.qualification.next_step_reason) && (
                  <p className="mt-1 text-sm text-muted-foreground leading-relaxed">
                    {lead.qualification.action_reasoning || lead.qualification.next_step_reason}
                  </p>
                )}
              </div>
            )}

            {/* Outreach kit — 3 blocks */}
            {lead.outreach && (
              <div className="mt-6">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2 text-primary">
                    <Mail className="h-4 w-4" />
                    <div className="text-xs uppercase tracking-widest font-bold">Personalized Outreach</div>
                  </div>
                  <button onClick={() => regenerate("all")} disabled={!!regenLoading}
                    data-testid="regen-all-btn"
                    className="text-xs inline-flex items-center gap-1 h-8 px-2 rounded-md hover:bg-accent transition-colors disabled:opacity-60">
                    {regenLoading === "all" ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />} Regen all
                  </button>
                </div>

                <OutreachBlock
                  icon={<Mail className="h-3.5 w-3.5" />} label="First email"
                  content={lead.outreach.subject ? `Subject: ${lead.outreach.subject}\n\n${lead.outreach.first_email}` : lead.outreach.first_email}
                  onCopy={() => copy(`Subject: ${lead.outreach.subject}\n\n${lead.outreach.first_email}`)}
                  onRegen={() => regenerate("first_email")}
                  regening={regenLoading === "first_email"} tid="outreach-first-email"
                >
                  {lead.outreach.subject && <div className="text-sm font-semibold mb-2" data-testid="email-subject">{lead.outreach.subject}</div>}
                  <div className="text-sm text-foreground/90 whitespace-pre-wrap leading-relaxed" data-testid="email-body">{lead.outreach.first_email}</div>
                </OutreachBlock>

                <OutreachBlock
                  icon={<Linkedin className="h-3.5 w-3.5" />} label="LinkedIn message"
                  onCopy={() => copy(lead.outreach.linkedin_message)}
                  onRegen={() => regenerate("linkedin_message")}
                  regening={regenLoading === "linkedin_message"} tid="outreach-linkedin"
                >
                  <div className="text-sm text-foreground/90 whitespace-pre-wrap leading-relaxed" data-testid="linkedin-body">
                    {lead.outreach.linkedin_message || <span className="text-muted-foreground">Not generated yet.</span>}
                  </div>
                </OutreachBlock>

                <OutreachBlock
                  icon={<Send className="h-3.5 w-3.5" />} label="Follow-up email (send in 3 days)"
                  onCopy={() => copy(lead.outreach.followup_email)}
                  onRegen={() => regenerate("followup_email")}
                  regening={regenLoading === "followup_email"} tid="outreach-followup"
                >
                  <div className="text-sm text-foreground/90 whitespace-pre-wrap leading-relaxed" data-testid="followup-body">
                    {lead.outreach.followup_email || <span className="text-muted-foreground">Not generated yet.</span>}
                  </div>
                </OutreachBlock>
              </div>
            )}

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

            {/* AI Decisions timeline */}
            {decisions.length > 0 && (
              <div className="mt-6">
                <div className="flex items-center gap-2 text-primary mb-2">
                  <Brain className="h-4 w-4" />
                  <div className="text-xs uppercase tracking-widest font-bold">AI Decisions</div>
                </div>
                <div className="rounded-lg border border-border bg-card">
                  <ol className="divide-y divide-border">
                    {decisions.map((d) => (
                      <li key={d.id} className="p-3 text-xs" data-testid={`ai-decision-${d.id}`}>
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="font-semibold">{d.decision_type}</span>
                            <span className="text-muted-foreground font-mono">{d.model} · v{d.prompt_version}</span>
                            {d.status !== "success" && (
                              <span className={`px-1.5 py-0.5 rounded-md text-[10px] font-semibold ${d.status === "fallback" ? "bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300" : "bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300"}`}>
                                {d.status}
                              </span>
                            )}
                          </div>
                          <span className="text-muted-foreground shrink-0">
                            {d.latency_ms ? `${d.latency_ms}ms · ` : ""}{timeAgo(d.at)}
                          </span>
                        </div>
                        {d.reasoning && <p className="text-muted-foreground leading-relaxed mt-1">{d.reasoning}</p>}
                        {(d.score != null || d.action) && (
                          <div className="mt-1 flex items-center gap-2 text-muted-foreground">
                            {d.score != null && <span>Score: <span className="font-semibold text-foreground">{d.score}</span></span>}
                            {d.action && <span>· Action: <span className="font-semibold text-foreground">{d.action}</span></span>}
                          </div>
                        )}
                      </li>
                    ))}
                  </ol>
                </div>
              </div>
            )}

            {/* Activity Timeline */}
            <div className="mt-6">
              <div className="flex items-center justify-between mb-2">
                <div className="overline">Activity timeline</div>
                <button onClick={retrySync} disabled={retrying} data-testid="retry-sync-btn"
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

function ProcPill({ status }) {
  if (!status || status === "qualified") return null;
  const map = {
    pending: { Icon: Clock, label: "Pending", cls: "bg-muted text-muted-foreground border-border" },
    analyzing: { Icon: LoaderPinwheel, label: "Analyzing", cls: "bg-primary/10 text-primary border-primary/20", spin: true },
    failed: { Icon: AlertTriangle, label: "Failed", cls: "bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-900" },
  }[status];
  if (!map) return null;
  const { Icon, label, cls, spin } = map;
  return (
    <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-semibold ${cls}`}>
      <Icon className={`h-3 w-3 ${spin ? "animate-spin" : ""}`} /> {label}
    </span>
  );
}

function OutreachBlock({ icon, label, onCopy, onRegen, regening, tid, children }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 mb-3" data-testid={tid}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest font-bold text-muted-foreground">
          {icon} {label}
        </div>
        <div className="flex items-center gap-1">
          <button onClick={onCopy} className="text-xs inline-flex items-center gap-1 h-7 px-2 rounded-md hover:bg-accent transition-colors">
            <Copy className="h-3 w-3" /> Copy
          </button>
          <button onClick={onRegen} disabled={regening} className="text-xs inline-flex items-center gap-1 h-7 px-2 rounded-md hover:bg-accent disabled:opacity-50 transition-colors">
            {regening ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />} Regen
          </button>
        </div>
      </div>
      {children}
    </div>
  );
}
