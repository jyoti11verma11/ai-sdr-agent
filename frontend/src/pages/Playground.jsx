import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Loader2, Save, RotateCcw, PlayCircle, Sparkles, ChevronDown } from "lucide-react";
import { SkeletonBlock } from "@/components/app/Skeletons";
import { timeAgo } from "@/lib/utils";

const PROMPT_TABS = [
  { name: "qualification", label: "Qualification", desc: "How the AI reads and scores each inbound lead." },
  { name: "outreach", label: "Outreach kit", desc: "How the AI drafts the email + LinkedIn + follow-up." },
];

const DEFAULT_TEST_LEAD = {
  name: "Sarah Chen",
  email: "sarah@fintechco.com",
  company: "FinTech Co",
  job_title: "VP Engineering",
  website: "fintechco.com",
  company_size_hint: "~500 employees",
  message: "We need SOC2 compliance and are evaluating vendors for Q3. Budget approved. Need to move fast.",
  source: "website",
};

export default function Playground() {
  const [prompts, setPrompts] = useState([]);
  const [active, setActive] = useState("qualification");
  const [template, setTemplate] = useState("");
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  // Test panel
  const [testLead, setTestLead] = useState(DEFAULT_TEST_LEAD);
  const [testQual, setTestQual] = useState(null);
  const [testRes, setTestRes] = useState(null);
  const [testing, setTesting] = useState(false);

  const load = async () => {
    const { data } = await api.get("/prompts");
    setPrompts(data);
    const found = data.find((p) => p.name === active) || data[0];
    setTemplate(found.template); setActive(found.name); setDirty(false);
    setLoading(false);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const switchTab = (name) => {
    if (dirty && !window.confirm("Discard unsaved changes?")) return;
    setActive(name);
    const found = prompts.find((p) => p.name === name);
    setTemplate(found?.template || "");
    setDirty(false); setTestRes(null);
  };

  const save = async () => {
    setBusy(true);
    try {
      const { data } = await api.put(`/prompts/${active}`, { template });
      setPrompts(prompts.map((p) => (p.name === active ? data : p)));
      setDirty(false);
      toast.success(`Prompt saved (v${data.version})`);
    } catch (e) { toast.error("Save failed"); }
    finally { setBusy(false); }
  };

  const reset = async () => {
    if (!window.confirm("Reset to the default template?")) return;
    setBusy(true);
    try {
      const { data } = await api.post(`/prompts/${active}/reset`);
      setPrompts(prompts.map((p) => (p.name === active ? data : p)));
      setTemplate(data.template); setDirty(false);
      toast.success("Reset to default");
    } finally { setBusy(false); }
  };

  const runTest = async () => {
    setTesting(true); setTestRes(null);
    try {
      const body = { lead: testLead };
      if (active === "outreach") {
        // Need a qualification. If none, run qualification first.
        let q = testQual;
        if (!q) {
          const { data } = await api.post(`/prompts/qualification/test`, { lead: testLead });
          q = data; setTestQual(data);
        }
        body.qualification = q;
      }
      const { data } = await api.post(`/prompts/${active}/test`, body);
      setTestRes(data);
      if (active === "qualification") setTestQual(data);
      toast.success("Test complete");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Test failed");
    } finally { setTesting(false); }
  };

  const current = prompts.find((p) => p.name === active);

  return (
    <div className="px-4 sm:px-6 lg:px-8 py-6 lg:py-8 max-w-6xl mx-auto" data-testid="playground-page">
      <div className="mb-6 lg:mb-8 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <div className="overline mb-2">Admin</div>
          <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tighter">AI Playground</h1>
          <p className="text-sm text-muted-foreground mt-1.5">Edit and test prompt templates without touching code. Saved versions are used on the next lead.</p>
        </div>
        {current && (
          <div className="text-xs text-muted-foreground font-mono flex items-center gap-3">
            <span>{current.name}</span>
            <span className="rounded-md border border-border px-2 py-0.5">v{current.version}</span>
            <span>Updated {timeAgo(current.updated_at)}</span>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="mb-4 flex items-center gap-1 border-b border-border" role="tablist">
        {PROMPT_TABS.map((t) => (
          <button key={t.name} onClick={() => switchTab(t.name)}
            data-testid={`tab-${t.name}`}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
              active === t.name ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground"
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      <p className="text-sm text-muted-foreground mb-4">{PROMPT_TABS.find((t) => t.name === active)?.desc}</p>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Editor */}
        <div className="lg:col-span-3 rounded-xl border border-border bg-card p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="overline">Prompt template</div>
            <div className="flex items-center gap-1">
              <button onClick={reset} disabled={busy}
                className="text-xs inline-flex items-center gap-1 h-8 px-2 rounded-md hover:bg-accent transition-colors">
                <RotateCcw className="h-3 w-3" /> Reset
              </button>
              <button onClick={save} disabled={busy || !dirty} data-testid="save-prompt"
                className="text-xs inline-flex items-center gap-1 h-8 px-3 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors">
                {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />} Save
              </button>
            </div>
          </div>
          {loading ? (
            <SkeletonBlock className="h-96 w-full rounded-md" />
          ) : (
            <textarea
              data-testid="prompt-editor"
              value={template}
              onChange={(e) => { setTemplate(e.target.value); setDirty(true); }}
              rows={20}
              className="w-full font-mono text-xs bg-muted/40 rounded-md border border-border p-3 field-focus resize-y" />
          )}
          <div className="mt-2 text-xs text-muted-foreground">
            {dirty ? <span className="text-amber-600 dark:text-amber-400">Unsaved changes</span> : "Up to date"}
          </div>
        </div>

        {/* Test panel */}
        <div className="lg:col-span-2 rounded-xl border border-border bg-card p-5">
          <div className="overline mb-3">Test with sample lead</div>
          <div className="space-y-2 text-sm">
            <TextField label="Name" value={testLead.name} onChange={(v) => setTestLead({ ...testLead, name: v })} />
            <TextField label="Email" value={testLead.email} onChange={(v) => setTestLead({ ...testLead, email: v })} />
            <TextField label="Company" value={testLead.company} onChange={(v) => setTestLead({ ...testLead, company: v })} />
            <TextField label="Job title" value={testLead.job_title} onChange={(v) => setTestLead({ ...testLead, job_title: v })} />
            <div>
              <label className="text-xs font-medium text-muted-foreground">Message</label>
              <textarea value={testLead.message} onChange={(e) => setTestLead({ ...testLead, message: e.target.value })}
                rows={3} className="mt-1 w-full px-2.5 py-1.5 rounded-md border border-border bg-background field-focus text-xs" />
            </div>
          </div>
          <button onClick={runTest} disabled={testing} data-testid="run-test-btn"
            className="w-full mt-4 h-10 inline-flex items-center justify-center gap-2 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 font-medium text-sm disabled:opacity-60 transition-colors">
            {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlayCircle className="h-4 w-4" />}
            {testing ? "Running…" : "Run test"}
          </button>

          {testRes && (
            <div className="mt-4">
              <div className="flex items-center gap-2 text-primary mb-2">
                <Sparkles className="h-3.5 w-3.5" />
                <div className="text-[10px] uppercase tracking-widest font-bold">Output</div>
              </div>
              <pre className="font-mono text-[11px] bg-muted/40 rounded-md border border-border p-3 max-h-96 overflow-auto whitespace-pre-wrap" data-testid="test-output">
                {JSON.stringify(testRes, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function TextField({ label, value, onChange }) {
  return (
    <div>
      <label className="text-xs font-medium text-muted-foreground">{label}</label>
      <input value={value || ""} onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full h-9 px-2.5 rounded-md border border-border bg-background field-focus text-xs" />
    </div>
  );
}
