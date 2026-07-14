import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Loader2, Save } from "lucide-react";
import { useAuth } from "@/lib/auth";

export default function Settings() {
  const { user } = useAuth();
  const [s, setS] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.get("/settings").then((r) => setS(r.data)); }, []);

  if (!s) return <div className="p-8 text-slate-400">Loading…</div>;

  const save = async () => {
    setBusy(true);
    try {
      const { data } = await api.put("/settings", {
        hubspot_token: s.hubspot_token || null,
        slack_webhook_url: s.slack_webhook_url || null,
        n8n_webhook_url: s.n8n_webhook_url || null,
        auto_sync_hubspot: !!s.auto_sync_hubspot,
        auto_notify_slack: !!s.auto_notify_slack,
        auto_trigger_n8n: !!s.auto_trigger_n8n,
      });
      setS(data);
      toast.success("Settings saved");
    } catch (e) { toast.error("Save failed"); }
    finally { setBusy(false); }
  };

  const set = (k, v) => setS({ ...s, [k]: v });

  return (
    <div className="p-8 max-w-3xl mx-auto" data-testid="settings-page">
      <div className="mb-8">
        <div className="overline mb-2">Configuration</div>
        <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tight">Settings</h1>
        <p className="text-slate-500 mt-1 text-sm">Configure your integrations. Leave a field blank to keep it mocked.</p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6 mb-6">
        <div className="overline mb-1">Public capture link</div>
        <div className="text-sm text-slate-500 mb-2">Anyone can submit a lead using this URL. Embed it on your site.</div>
        <code className="block font-mono text-xs bg-slate-50 border border-slate-100 rounded-md p-3 break-all" data-testid="public-capture-link">
          {window.location.origin}/capture/{user?.email}
        </code>
      </div>

      <Section title="HubSpot" desc="Push qualified contacts into your CRM. Uses HubSpot Private App token.">
        <Toggle label="Auto sync to HubSpot" checked={s.auto_sync_hubspot} onChange={(v) => set("auto_sync_hubspot", v)} tid="toggle-hubspot" />
        <Field label="HubSpot Private App token" value={s.hubspot_token || ""} onChange={(v) => set("hubspot_token", v)} placeholder="pat-na1-xxxxxxxx" tid="hubspot-token" />
      </Section>

      <Section title="Slack" desc="Ping your team when a hot lead lands. Use an Incoming Webhook URL.">
        <Toggle label="Auto notify Slack" checked={s.auto_notify_slack} onChange={(v) => set("auto_notify_slack", v)} tid="toggle-slack" />
        <Field label="Slack Webhook URL" value={s.slack_webhook_url || ""} onChange={(v) => set("slack_webhook_url", v)} placeholder="https://hooks.slack.com/services/..." tid="slack-webhook" />
      </Section>

      <Section title="n8n" desc="Trigger any downstream workflow on lead creation.">
        <Toggle label="Auto trigger n8n webhook" checked={s.auto_trigger_n8n} onChange={(v) => set("auto_trigger_n8n", v)} tid="toggle-n8n" />
        <Field label="n8n Webhook URL" value={s.n8n_webhook_url || ""} onChange={(v) => set("n8n_webhook_url", v)} placeholder="https://your-n8n.host/webhook/..." tid="n8n-webhook" />
      </Section>

      <div className="flex justify-end">
        <button data-testid="save-settings" onClick={save} disabled={busy}
          className="inline-flex items-center gap-2 bg-[#0044FF] hover:bg-[#0033CC] text-white px-5 h-10 rounded-md text-sm font-medium transition-colors disabled:opacity-60">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save changes
        </button>
      </div>
    </div>
  );
}

function Section({ title, desc, children }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 mb-6">
      <div className="mb-4">
        <div className="font-display text-lg font-semibold">{title}</div>
        <div className="text-sm text-slate-500 mt-0.5">{desc}</div>
      </div>
      <div className="space-y-4">{children}</div>
    </div>
  );
}

function Field({ label, value, onChange, placeholder, tid }) {
  return (
    <div>
      <label className="text-sm font-medium text-slate-700">{label}</label>
      <input data-testid={tid} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
        className="mt-1.5 w-full h-10 px-3 rounded-md border border-slate-300 focus:border-[#0044FF] focus:ring-2 focus:ring-[#0044FF]/20 outline-none transition-colors font-mono text-sm" />
    </div>
  );
}

function Toggle({ label, checked, onChange, tid }) {
  return (
    <label className="flex items-center justify-between py-2 cursor-pointer">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <button type="button" data-testid={tid} onClick={() => onChange(!checked)}
        className={`relative h-6 w-11 rounded-full transition-colors ${checked ? "bg-[#0044FF]" : "bg-slate-300"}`}>
        <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${checked ? "translate-x-5" : "translate-x-0.5"}`} />
      </button>
    </label>
  );
}
