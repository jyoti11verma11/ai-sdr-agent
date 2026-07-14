import React, { useEffect, useState } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import api from "@/lib/api";
import { toast } from "sonner";
import {
  Loader2, Copy, RefreshCw, Trash2, Mail, Sparkles, CheckCircle2, ExternalLink,
  PlugZap, Linkedin, Send, Clock, LoaderPinwheel, AlertTriangle, Brain,
  MessageSquare, Calendar, UserCheck
} from "lucide-react";
import { scoreColor, statusColor, timeAgo } from "@/lib/utils";
import { useAuth } from "@/lib/auth";

const STATUSES = ["new", "qualifying", "qualified", "disqualified", "contacted", "converted"];

export default function LeadDrawer({ leadId, onClose, onChanged }) {
  const { user } = useAuth() || {};
  const [lead, setLead] = useState(null);
  const [decisions, setDecisions] = useState([]);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [regenLoading, setRegenLoading] = useState("");
  const [retrying, setRetrying] = useState(false);
  const [noteText, setNoteText] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  const [showMeeting, setShowMeeting] = useState(false);
  const [meetingSlots, setMeetingSlots] = useState(null);
  const [meetingBusy, setMeetingBusy] = useState(false);
  const [showEmail, setShowEmail] = useState(false);
  const [emailDraft, setEmailDraft] = useState({ subject: "", body: "" });
  const [emailBusy, setEmailBusy] = useState(false);
  const open = !!leadId;

  const load = async () => {
    setLoading(true);
    try {
      const [{ data }, { data: dec }, { data: mem }] = await Promise.all([
        api.get(`/leads/${leadId}`),
        api.get(`/leads/${leadId}/decisions`),
        api.get("/workspace/members"),
      ]);
      setLead(data); setDecisions(dec); setMembers(mem);
      setEmailDraft({ subject: data.outreach?.subject || "", body: data.outreach?.first_email || "" });
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

  const addNote = async (e) => {
    e.preventDefault();
    if (!noteText.trim()) return;
    setSavingNote(true);
    try {
      const { data } = await api.post(`/leads/${leadId}/notes`, { body: noteText });
      setLead(data); setNoteText(""); toast.success("Note added");
    } catch { toast.error("Failed to save note"); }
    finally { setSavingNote(false); }
  };

  const assignTo = async (userId) => {
    const { data } = await api.patch(`/leads/${leadId}/assign`, {
      assigned_to: userId || null,
      reason: userId ? "Manual assignment" : "Manually unassigned",
    });
    setLead(data); onChanged?.(); toast.success("Assignment updated");
  };

  const sendEmail = async (mode) => {
    setEmailBusy(true);
    try {
      const payload = {
        to: lead.email, subject: emailDraft.subject, body: emailDraft.body,
        save_as_draft: mode === "draft",
      };
      const { data } = await api.post(`/leads/${leadId}/emails`, payload);
      setLead(data); onChanged?.();
      toast.success(mode === "draft" ? "Draft saved" : "Email sent");
      setShowEmail(false);
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
    finally { setEmailBusy(false); }
  };

  const proposeMeeting = async () => {
    setMeetingBusy(true);
    try {
      const { data } = await api.post(`/leads/${leadId}/meetings/propose`, { duration_min: 30 });
      setMeetingSlots(data); setShowMeeting(true);
    } catch { toast.error("Failed to propose"); }
    finally { setMeetingBusy(false); }
  };

  const confirmMeeting = async (slot) => {
    setMeetingBusy(true);
    try {
      const { data } = await api.post(`/leads/${leadId}/meetings`, {
        title: meetingSlots.title_suggestion,
        description: meetingSlots.description_suggestion,
        start: slot.start,
        duration_min: slot.duration_min,
        attendee_emails: [lead.email],
      });
      setLead(data); onChanged?.(); setShowMeeting(false);
      toast.success("Meeting scheduled");
    } catch { toast.error("Failed to schedule"); }
    finally { setMeetingBusy(false); }
  };

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

            {/* Assignment + quick actions */}
            <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="rounded-lg border border-border bg-card p-3">
                <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                  <UserCheck className="h-3.5 w-3.5" /> ASSIGNED TO
                </div>
                <select value={lead.assigned_to || ""} onChange={(e) => assignTo(e.target.value || null)}
                  data-testid="assign-select"
                  className="w-full h-9 px-2 rounded-md border border-border bg-background text-sm">
                  <option value="">Unassigned</option>
                  {members.map((m) => <option key={m.user_id} value={m.user_id}>{m.full_name} · {m.role}</option>)}
                </select>
                {lead.assignment_reason && <div className="text-[10px] text-muted-foreground mt-1.5">{lead.assignment_reason}</div>}
              </div>
              <div className="rounded-lg border border-border bg-card p-3 flex flex-col justify-between">
                <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                  <Calendar className="h-3.5 w-3.5" /> QUICK ACTIONS
                </div>
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => setShowEmail(true)} data-testid="send-email-btn"
                    className="text-xs inline-flex items-center gap-1 h-8 px-2 rounded-md border border-border hover:bg-accent transition-colors">
                    <Mail className="h-3 w-3" /> Send email
                  </button>
                  <button onClick={proposeMeeting} disabled={meetingBusy} data-testid="book-meeting-btn"
                    className="text-xs inline-flex items-center gap-1 h-8 px-2 rounded-md border border-border hover:bg-accent transition-colors">
                    {meetingBusy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Calendar className="h-3 w-3" />} Book meeting
                  </button>
                </div>
              </div>
            </div>

            {/* Meeting slots dialog */}
            {showMeeting && meetingSlots && (
              <div className="mt-3 rounded-lg border border-primary/30 bg-primary/5 p-4" data-testid="meeting-slots">
                <div className="text-xs uppercase tracking-widest font-bold text-primary mb-2">AI-recommended slots</div>
                <div className="space-y-2">
                  {meetingSlots.slots.map((s, i) => (
                    <button key={i} onClick={() => confirmMeeting(s)} disabled={meetingBusy}
                      className="w-full text-left rounded-md border border-border bg-background p-2.5 hover:border-primary/50 transition-colors text-sm">
                      <div className="font-medium">{new Date(s.start).toLocaleString()}</div>
                      <div className="text-xs text-muted-foreground">{s.duration_min} min</div>
                    </button>
                  ))}
                </div>
                <button onClick={() => setShowMeeting(false)} className="mt-2 text-xs text-muted-foreground hover:underline">Cancel</button>
              </div>
            )}

            {/* Email compose */}
            {showEmail && (
              <div className="mt-3 rounded-lg border border-border bg-card p-4" data-testid="email-compose">
                <div className="text-xs uppercase tracking-widest font-bold text-primary mb-2">Send email · {lead.email}</div>
                <input value={emailDraft.subject} onChange={(e) => setEmailDraft({ ...emailDraft, subject: e.target.value })}
                  placeholder="Subject"
                  className="w-full h-9 px-2.5 rounded-md border border-border bg-background field-focus text-sm mb-2" />
                <textarea value={emailDraft.body} onChange={(e) => setEmailDraft({ ...emailDraft, body: e.target.value })}
                  rows={6}
                  className="w-full px-2.5 py-1.5 rounded-md border border-border bg-background field-focus text-sm resize-y" />
                <div className="mt-2 flex items-center gap-2 justify-end">
                  <button onClick={() => setShowEmail(false)} className="text-xs h-8 px-3 rounded-md hover:bg-accent transition-colors">Cancel</button>
                  <button onClick={() => sendEmail("draft")} disabled={emailBusy}
                    className="text-xs h-8 px-3 rounded-md border border-border hover:bg-accent transition-colors">Save draft</button>
                  <button onClick={() => sendEmail("send")} disabled={emailBusy} data-testid="email-send-now"
                    className="text-xs h-8 px-3 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-60 transition-colors inline-flex items-center gap-1">
                    {emailBusy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Send className="h-3 w-3" />} Send now
                  </button>
                </div>
              </div>
            )}

            {/* Email history */}
            {lead.emails && lead.emails.length > 0 && (
              <div className="mt-6" data-testid="email-history">
                <div className="overline mb-2 flex items-center gap-2"><Mail className="h-3 w-3" /> Email history</div>
                <ul className="space-y-2">
                  {lead.emails.map((em) => (
                    <li key={em.id} className="rounded-md border border-border bg-card p-3 text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium truncate">{em.subject}</span>
                        <span className={`text-[10px] uppercase tracking-widest font-semibold px-1.5 py-0.5 rounded-md border ${
                          em.status === "sent" || em.status === "delivered" ? "border-emerald-200 dark:border-emerald-900 bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300"
                          : em.status === "opened" || em.status === "clicked" ? "border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300"
                          : em.status === "draft" ? "border-border bg-muted text-muted-foreground"
                          : "border-rose-200 dark:border-rose-900 bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300"
                        }`}>{em.status}</span>
                      </div>
                      <div className="text-xs text-muted-foreground mt-0.5">To: {em.to} · {timeAgo(em.sent_at || em.created_at)}</div>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Meetings */}
            {lead.meetings && lead.meetings.length > 0 && (
              <div className="mt-6" data-testid="meeting-history">
                <div className="overline mb-2 flex items-center gap-2"><Calendar className="h-3 w-3" /> Meetings</div>
                <ul className="space-y-2">
                  {lead.meetings.map((m) => (
                    <li key={m.id} className="rounded-md border border-border bg-card p-3 text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium truncate">{m.title}</span>
                        <span className="text-[10px] uppercase tracking-widest font-semibold px-1.5 py-0.5 rounded-md border border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300">{m.status}</span>
                      </div>
                      <div className="text-xs text-muted-foreground mt-0.5">{new Date(m.start).toLocaleString()}</div>
                      {m.gcal_template_url && (
                        <a href={m.gcal_template_url} target="_blank" rel="noreferrer" className="mt-1 inline-flex items-center gap-1 text-xs text-primary hover:underline">
                          <ExternalLink className="h-3 w-3" /> Add to Google Calendar
                        </a>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Notes */}
            <div className="mt-6" data-testid="notes-section">
              <div className="overline mb-2 flex items-center gap-2"><MessageSquare className="h-3 w-3" /> Notes & comments</div>
              <form onSubmit={addNote} className="flex items-start gap-2 mb-3">
                <textarea value={noteText} onChange={(e) => setNoteText(e.target.value)}
                  placeholder="Add a note. Use @teammate@company.com to mention."
                  rows={2} data-testid="note-input"
                  className="flex-1 px-2.5 py-1.5 rounded-md border border-border bg-background field-focus text-sm resize-y" />
                <button disabled={savingNote} data-testid="note-submit"
                  className="h-9 px-3 text-xs rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-60 transition-colors">
                  {savingNote ? <Loader2 className="h-3 w-3 animate-spin" /> : "Post"}
                </button>
              </form>
              <ul className="space-y-2">
                {[...(lead.notes || [])].reverse().map((n) => (
                  <li key={n.id} className="rounded-md border border-border bg-card p-3 text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-xs">{n.author_name}</span>
                      <span className="text-[10px] text-muted-foreground">{timeAgo(n.at)}</span>
                    </div>
                    <div className="mt-1 text-foreground/90 whitespace-pre-wrap">{n.body}</div>
                  </li>
                ))}
              </ul>
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
