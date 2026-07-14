import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Loader2, Save, Copy, Link as LinkIcon, Zap, MessageSquare, Webhook } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { SkeletonBlock } from "@/components/app/Skeletons";

export default function Settings() {
  const { user } = useAuth();
  const [s, setS] = useState(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/settings").then((r) => setS(r.data)).finally(() => setLoading(false));
  }, []);

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

  const captureUrl = `${window.location.origin}/capture/${user?.email}`;
  const copy = (text) => { navigator.clipboard.writeText(text); toast.success("Copied"); };

  return (
    <div className="px-4 sm:px-6 lg:px-8 py-6 lg:py-8 max-w-3xl mx-auto" data-testid="settings-page">
      <div className="mb-6 lg:mb-8">
        <div className="overline mb-2">Configuration</div>
        <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tighter">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1.5">Wire up your integrations. Leave a token blank to keep the provider mocked.</p>
      </div>

      <div className="rounded-xl border border-border bg-card p-6 mb-6">
        <div className="flex items-center gap-2 mb-2">
          <LinkIcon className="h-4 w-4 text-primary" />
          <div className="overline">Public capture link</div>
        </div>
        <div className="text-sm text-muted-foreground mb-3">Anyone can submit a lead through this URL — embed it on your site or share it directly.</div>
        <div className="flex items-center gap-2">
          <code className="flex-1 font-mono text-xs bg-muted rounded-md p-3 break-all border border-border" data-testid="public-capture-link">
            {captureUrl}
          </code>
          <button
            onClick={() => copy(captureUrl)}
            data-testid="copy-capture-link"
            className="inline-flex items-center gap-1.5 h-10 px-3 rounded-md border border-border bg-card hover:bg-accent transition-colors text-sm">
            <Copy className="h-3.5 w-3.5" /> Copy
          </button>
        </div>
      </div>

      {loading ? (
        <div className="space-y-4">
          <SkeletonBlock className="h-56 w-full rounded-xl" />
          <SkeletonBlock className="h-56 w-full rounded-xl" />
        </div>
      ) : !s ? null : (
        <>
          <Section icon={<Zap className="h-4 w-4" />} title="HubSpot" desc="Push qualified contacts into your CRM. Uses a HubSpot Private App token.">
            <Toggle label="Auto sync to HubSpot" checked={s.auto_sync_hubspot} onChange={(v) => set("auto_sync_hubspot", v)} tid="toggle-hubspot" />
            <Field label="HubSpot Private App token" value={s.hubspot_token || ""} onChange={(v) => set("hubspot_token", v)} placeholder="pat-na1-xxxxxxxx" tid="hubspot-token" mono />
            <Hint href="https://developers.hubspot.com/docs/api/private-apps">How to create a Private App token →</Hint>
          </Section>

          <Section icon={<MessageSquare className="h-4 w-4" />} title="Slack" desc="Ping your team the moment a hot lead lands. Uses an Incoming Webhook URL.">
            <Toggle label="Auto notify Slack" checked={s.auto_notify_slack} onChange={(v) => set("auto_notify_slack", v)} tid="toggle-slack" />
            <Field label="Slack Webhook URL" value={s.slack_webhook_url || ""} onChange={(v) => set("slack_webhook_url", v)} placeholder="https://hooks.slack.com/services/..." tid="slack-webhook" mono />
            <Hint href="https://api.slack.com/messaging/webhooks">Create an incoming webhook →</Hint>
          </Section>

          <Section icon={<Webhook className="h-4 w-4" />} title="n8n" desc="Trigger any downstream workflow on lead creation.">
            <Toggle label="Auto trigger n8n webhook" checked={s.auto_trigger_n8n} onChange={(v) => set("auto_trigger_n8n", v)} tid="toggle-n8n" />
            <Field label="n8n Webhook URL" value={s.n8n_webhook_url || ""} onChange={(v) => set("n8n_webhook_url", v)} placeholder="https://your-n8n.host/webhook/..." tid="n8n-webhook" mono />
          </Section>

          <div className="flex justify-end">
            <button data-testid="save-settings" onClick={save} disabled={busy}
              className="inline-flex items-center gap-2 bg-primary hover:bg-primary/90 text-primary-foreground px-5 h-10 rounded-md text-sm font-medium transition-colors disabled:opacity-60 shadow-sm shadow-primary/20">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save changes
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function Section({ icon, title, desc, children }) {
  return (
    <div className="rounded-xl border border-border bg-card p-6 mb-6">
      <div className="mb-4 flex items-start gap-3">
        <div className="h-9 w-9 shrink-0 rounded-md bg-primary/10 text-primary grid place-items-center">{icon}</div>
        <div>
          <div className="font-display text-lg font-semibold tracking-tight">{title}</div>
          <div className="text-sm text-muted-foreground mt-0.5">{desc}</div>
        </div>
      </div>
      <div className="space-y-4">{children}</div>
    </div>
  );
}

function Field({ label, value, onChange, placeholder, tid, mono }) {
  return (
    <div>
      <label className="text-sm font-medium">{label}</label>
      <input data-testid={tid} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
        className={`mt-1.5 w-full h-10 px-3 rounded-md border border-border bg-background field-focus text-sm ${mono ? "font-mono" : ""}`} />
    </div>
  );
}

function Toggle({ label, checked, onChange, tid }) {
  return (
    <label className="flex items-center justify-between py-1 cursor-pointer">
      <span className="text-sm font-medium">{label}</span>
      <button type="button" data-testid={tid} onClick={() => onChange(!checked)}
        className={`relative h-6 w-11 rounded-full transition-colors ${checked ? "bg-primary" : "bg-muted"}`}>
        <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${checked ? "translate-x-5" : "translate-x-0.5"}`} />
      </button>
    </label>
  );
}

function Hint({ href, children }) {
  return (
    <a href={href} target="_blank" rel="noreferrer"
      className="inline-block text-xs text-primary hover:underline mt-1">{children}</a>
  );
}
