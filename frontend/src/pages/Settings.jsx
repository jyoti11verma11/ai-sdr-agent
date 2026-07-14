import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Loader2, Save, Copy, Link as LinkIcon, Zap, MessageSquare, Webhook, CheckCircle2, XCircle, Circle, PlugZap, RefreshCw } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { SkeletonBlock } from "@/components/app/Skeletons";
import { timeAgo } from "@/lib/utils";

const PROVIDER_ICONS = {
  hubspot: Zap,
  slack: MessageSquare,
  n8n: Webhook,
};

export default function Settings() {
  const { user } = useAuth();
  const [s, setS] = useState(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState({ hubspot: {}, slack: {}, n8n: {} });
  const [testing, setTesting] = useState({});

  const loadAll = async () => {
    const [set, stat] = await Promise.all([api.get("/settings"), api.get("/integrations/status")]);
    setS(set.data);
    setStatus(stat.data);
    setLoading(false);
  };
  useEffect(() => { loadAll(); }, []);

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
      const { data: st } = await api.get("/integrations/status");
      setStatus(st);
      toast.success("Settings saved");
    } catch (e) { toast.error("Save failed"); }
    finally { setBusy(false); }
  };

  const test = async (provider) => {
    setTesting((p) => ({ ...p, [provider]: true }));
    try {
      const { data } = await api.post(`/integrations/${provider}/test`);
      if (data.status === "success") toast.success(`${provider}: ${data.message}`);
      else if (data.status === "mocked") toast(`${provider}: ${data.message}`, { icon: "🧪" });
      else toast.error(`${provider}: ${data.message}`);
      const { data: st } = await api.get("/integrations/status");
      setStatus(st);
    } catch (e) {
      toast.error(`${provider}: test failed`);
    } finally {
      setTesting((p) => ({ ...p, [provider]: false }));
    }
  };

  const set = (k, v) => setS({ ...s, [k]: v });
  const captureUrl = `${window.location.origin}/capture/${user?.email}`;
  const copy = (text) => { navigator.clipboard.writeText(text); toast.success("Copied"); };

  return (
    <div className="px-4 sm:px-6 lg:px-8 py-6 lg:py-8 max-w-3xl mx-auto" data-testid="settings-page">
      <div className="mb-6 lg:mb-8">
        <div className="overline mb-2">Configuration</div>
        <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tighter">Settings</h1>
        <p className="text-sm text-muted-foreground mt-1.5">Wire up your integrations. Leave a token blank to keep the provider in Mock Mode.</p>
      </div>

      {/* Capture link */}
      <div className="rounded-xl border border-border bg-card p-6 mb-6">
        <div className="flex items-center gap-2 mb-2">
          <LinkIcon className="h-4 w-4 text-primary" />
          <div className="overline">Public capture link</div>
        </div>
        <div className="text-sm text-muted-foreground mb-3">Anyone can submit a lead via this URL — embed it on your site or share it directly.</div>
        <div className="flex items-center gap-2">
          <code className="flex-1 font-mono text-xs bg-muted rounded-md p-3 break-all border border-border" data-testid="public-capture-link">{captureUrl}</code>
          <button onClick={() => copy(captureUrl)} data-testid="copy-capture-link"
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
          <IntegrationSection
            provider="hubspot"
            icon={<Zap className="h-4 w-4" />}
            title="HubSpot"
            desc="Push qualified contacts, companies and deals into your CRM. Uses a HubSpot Private App token."
            status={status.hubspot}
            testing={!!testing.hubspot}
            onTest={() => test("hubspot")}
          >
            <Toggle label="Auto sync contacts, companies & deals" checked={s.auto_sync_hubspot}
              onChange={(v) => set("auto_sync_hubspot", v)} tid="toggle-hubspot" />
            <Field label="HubSpot Private App token" value={s.hubspot_token || ""}
              onChange={(v) => set("hubspot_token", v)} placeholder="pat-na1-xxxxxxxx"
              tid="hubspot-token" mono type="password" />
            <Hint href="https://developers.hubspot.com/docs/api/private-apps">How to create a Private App token →</Hint>
          </IntegrationSection>

          <IntegrationSection
            provider="slack"
            icon={<MessageSquare className="h-4 w-4" />}
            title="Slack"
            desc="Notifies on new qualified leads, hot (85+) leads and qualification failures."
            status={status.slack}
            testing={!!testing.slack}
            onTest={() => test("slack")}
          >
            <Toggle label="Auto notify Slack" checked={s.auto_notify_slack}
              onChange={(v) => set("auto_notify_slack", v)} tid="toggle-slack" />
            <Field label="Slack Webhook URL" value={s.slack_webhook_url || ""}
              onChange={(v) => set("slack_webhook_url", v)} placeholder="https://hooks.slack.com/services/..."
              tid="slack-webhook" mono />
            <Hint href="https://api.slack.com/messaging/webhooks">Create an incoming webhook →</Hint>
          </IntegrationSection>

          <IntegrationSection
            provider="n8n"
            icon={<Webhook className="h-4 w-4" />}
            title="n8n"
            desc="Fires an outbound webhook after qualification (with 3-retry backoff)."
            status={status.n8n}
            testing={!!testing.n8n}
            onTest={() => test("n8n")}
          >
            <Toggle label="Auto trigger n8n webhook" checked={s.auto_trigger_n8n}
              onChange={(v) => set("auto_trigger_n8n", v)} tid="toggle-n8n" />
            <Field label="n8n Webhook URL" value={s.n8n_webhook_url || ""}
              onChange={(v) => set("n8n_webhook_url", v)} placeholder="https://your-n8n.host/webhook/..."
              tid="n8n-webhook" mono />
          </IntegrationSection>

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

function IntegrationSection({ provider, icon, title, desc, status, testing, onTest, children }) {
  return (
    <div className="rounded-xl border border-border bg-card p-6 mb-6" data-testid={`integration-${provider}`}>
      <div className="mb-5 flex items-start gap-3">
        <div className="h-9 w-9 shrink-0 rounded-md bg-primary/10 text-primary grid place-items-center">{icon}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="font-display text-lg font-semibold tracking-tight">{title}</div>
            <StatusPill status={status} />
          </div>
          <div className="text-sm text-muted-foreground mt-0.5">{desc}</div>
          {status?.last_sync && (
            <div className="text-xs text-muted-foreground mt-1 font-mono">
              Last sync: {timeAgo(status.last_sync)}
              {status.last_message && <span className="text-muted-foreground/70"> · {status.last_message.slice(0, 80)}</span>}
            </div>
          )}
        </div>
        <button onClick={onTest} disabled={testing}
          data-testid={`test-${provider}`}
          className="inline-flex items-center gap-1.5 h-9 px-3 rounded-md border border-border bg-background hover:bg-accent transition-colors text-xs font-medium disabled:opacity-60 shrink-0">
          {testing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <PlugZap className="h-3.5 w-3.5" />}
          Test connection
        </button>
      </div>
      <div className="space-y-4">{children}</div>
    </div>
  );
}

function StatusPill({ status }) {
  if (!status) return null;
  const mode = status.mode;
  const map = {
    live: { icon: CheckCircle2, cls: "bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900", label: "Live" },
    mock: { icon: Circle, cls: "bg-muted text-muted-foreground border-border", label: "Mock mode" },
  };
  const errored = status.last_status === "error";
  const entry = errored
    ? { icon: XCircle, cls: "bg-rose-50 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-900", label: "Error" }
    : map[mode] || map.mock;
  const Icon = entry.icon;
  return (
    <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-semibold ${entry.cls}`}>
      <Icon className="h-3 w-3" /> {entry.label}
    </span>
  );
}

function Field({ label, value, onChange, placeholder, tid, mono, type = "text" }) {
  return (
    <div>
      <label className="text-sm font-medium">{label}</label>
      <input data-testid={tid} type={type} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
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
