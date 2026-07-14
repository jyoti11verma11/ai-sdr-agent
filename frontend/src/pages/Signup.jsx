import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import { Sparkles, Loader2, ArrowRight } from "lucide-react";

export default function Signup() {
  const { signup } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ full_name: "", email: "", password: "" });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await signup(form.email, form.password, form.full_name);
      toast.success("Workspace created");
      nav("/app");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Signup failed");
    } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen grid md:grid-cols-2 bg-background text-foreground" data-testid="signup-page">
      <div className="flex items-center justify-center p-6 sm:p-8 order-2 md:order-1">
        <form onSubmit={submit} className="w-full max-w-sm space-y-5" data-testid="signup-form">
          <div className="md:hidden flex items-center gap-2.5 mb-2">
            <div className="h-9 w-9 rounded-lg bg-primary grid place-items-center text-primary-foreground"><Sparkles className="h-4 w-4" /></div>
            <span className="font-display font-bold text-lg">SDR Agent</span>
          </div>
          <div>
            <h2 className="font-display text-2xl font-semibold tracking-tight">Create your workspace</h2>
            <p className="text-sm text-muted-foreground mt-1">50 free lead qualifications, no card.</p>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Full name</label>
            <input data-testid="signup-name" required value={form.full_name} onChange={set("full_name")}
              className="w-full h-10 px-3 rounded-md border border-border bg-background field-focus text-sm" />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Work email</label>
            <input data-testid="signup-email" required type="email" value={form.email} onChange={set("email")}
              className="w-full h-10 px-3 rounded-md border border-border bg-background field-focus text-sm" />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Password</label>
            <input data-testid="signup-password" required type="password" minLength={6} value={form.password} onChange={set("password")}
              className="w-full h-10 px-3 rounded-md border border-border bg-background field-focus text-sm" />
            <div className="text-xs text-muted-foreground">At least 6 characters.</div>
          </div>
          <button data-testid="signup-submit" disabled={busy}
            className="w-full h-10 rounded-md bg-primary text-primary-foreground font-medium hover:bg-primary/90 disabled:opacity-60 transition-colors flex items-center justify-center gap-2 shadow-sm shadow-primary/20">
            {busy && <Loader2 className="h-4 w-4 animate-spin" />} Create workspace <ArrowRight className="h-4 w-4" />
          </button>
          <div className="text-sm text-muted-foreground text-center">
            Already have an account? <Link to="/login" className="text-primary font-medium">Sign in →</Link>
          </div>
        </form>
      </div>

      <div className="hidden md:block relative bg-[#050505] text-white grain order-1 md:order-2">
        <div className="absolute inset-0 dot-grid opacity-30" />
        <div className="relative p-10 lg:p-12 flex flex-col justify-between h-full">
          <Link to="/" className="flex items-center gap-2.5 self-end">
            <div className="h-9 w-9 rounded-lg bg-[#3366FF] grid place-items-center"><Sparkles className="h-4 w-4" /></div>
            <span className="font-display font-bold text-lg">SDR Agent</span>
          </Link>
          <div>
            <div className="text-xs uppercase tracking-[0.2em] font-bold text-white/50 mb-3">Join 400+ teams</div>
            <h1 className="font-display text-4xl lg:text-5xl tracking-tighter font-bold leading-[1.05]">
              Every inbound<br />gets a reply<br />
              <span className="text-white/40">in 60 seconds.</span>
            </h1>
          </div>
          <div className="text-xs text-white/40 font-mono">v1.0 · gpt-5.2</div>
        </div>
      </div>
    </div>
  );
}
