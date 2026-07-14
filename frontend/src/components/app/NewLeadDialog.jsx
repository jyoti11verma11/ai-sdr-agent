import React, { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import api from "@/lib/api";
import { toast } from "sonner";
import { Loader2, Sparkles } from "lucide-react";

export default function NewLeadDialog({ open, onOpenChange, onCreated }) {
  const [form, setForm] = useState({ name: "", email: "", company: "", job_title: "", website: "", company_size_hint: "", message: "" });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/leads", form);
      toast.success("Lead captured & qualified");
      onCreated?.();
      onOpenChange(false);
      setForm({ name: "", email: "", company: "", job_title: "", website: "", company_size_hint: "", message: "" });
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to capture lead");
    } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg bg-background border-border" data-testid="new-lead-dialog">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl tracking-tight">Capture new lead</DialogTitle>
          <DialogDescription className="text-muted-foreground">The AI will qualify, score and draft an email within a few seconds.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <F label="Full name" required value={form.name} onChange={set("name")} tid="nl-name" />
            <F label="Email" type="email" required value={form.email} onChange={set("email")} tid="nl-email" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <F label="Company" required value={form.company} onChange={set("company")} tid="nl-company" />
            <F label="Job title" value={form.job_title} onChange={set("job_title")} tid="nl-title" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <F label="Website" value={form.website} onChange={set("website")} placeholder="acme.com" tid="nl-website" />
            <F label="Company size (hint)" value={form.company_size_hint} onChange={set("company_size_hint")} placeholder="e.g., 200 employees" tid="nl-size" />
          </div>
          <div>
            <label className="text-sm font-medium">Message / inbound query</label>
            <textarea data-testid="nl-message" rows={4} value={form.message} onChange={set("message")}
              placeholder="Paste what they said or wrote…"
              className="mt-1.5 w-full px-3 py-2 rounded-md border border-border bg-background field-focus text-sm resize-y" />
          </div>
          <button disabled={busy} data-testid="nl-submit"
            className="w-full h-10 rounded-md bg-primary hover:bg-primary/90 text-primary-foreground font-medium transition-colors flex items-center justify-center gap-2 disabled:opacity-60 shadow-sm shadow-primary/20">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {busy ? "AI is qualifying…" : "Qualify with AI"}
          </button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function F({ label, required, tid, ...rest }) {
  return (
    <div>
      <label className="text-sm font-medium">{label}{required && <span className="text-destructive">*</span>}</label>
      <input data-testid={tid} required={required} {...rest}
        className="mt-1.5 w-full h-10 px-3 rounded-md border border-border bg-background field-focus text-sm" />
    </div>
  );
}
