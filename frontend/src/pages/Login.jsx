import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import { Sparkles, Loader2 } from "lucide-react";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await login(email, password);
      toast.success("Welcome back");
      nav("/app");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen grid md:grid-cols-2 bg-white" data-testid="login-page">
      <div className="hidden md:block relative bg-[#050505] text-white grain">
        <div className="absolute inset-0 dot-grid opacity-30" />
        <div className="relative p-12 flex flex-col justify-between h-full">
          <Link to="/" className="flex items-center gap-2" data-testid="login-logo">
            <div className="h-8 w-8 rounded-md bg-[#3366FF] grid place-items-center"><Sparkles className="h-4 w-4" /></div>
            <span className="font-display font-bold text-lg">SDR Agent</span>
          </Link>
          <div>
            <div className="overline mb-3 text-white/50">Welcome back</div>
            <h1 className="font-display text-4xl lg:text-5xl tracking-tighter font-bold leading-[1.05]">
              Your inbound pipeline<br/>
              <span className="text-white/40">already qualified.</span>
            </h1>
            <p className="mt-4 text-white/60 max-w-md">Sign in to see what your AI SDR shipped overnight.</p>
          </div>
          <div className="text-xs text-white/40 font-mono">v1.0 • gpt-5.2</div>
        </div>
      </div>

      <div className="flex items-center justify-center p-8">
        <form onSubmit={submit} className="w-full max-w-sm space-y-5" data-testid="login-form">
          <div>
            <h2 className="font-display text-2xl font-semibold tracking-tight">Sign in</h2>
            <p className="text-sm text-slate-500 mt-1">to your SDR Agent workspace</p>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Email</label>
            <input
              data-testid="login-email"
              type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
              className="w-full h-10 px-3 rounded-md border border-slate-300 focus:border-[#0044FF] focus:ring-2 focus:ring-[#0044FF]/20 outline-none transition-colors"
              placeholder="you@company.com"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Password</label>
            <input
              data-testid="login-password"
              type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)}
              className="w-full h-10 px-3 rounded-md border border-slate-300 focus:border-[#0044FF] focus:ring-2 focus:ring-[#0044FF]/20 outline-none transition-colors"
              placeholder="••••••••"
            />
          </div>
          <button
            data-testid="login-submit"
            disabled={busy}
            className="w-full h-10 rounded-md bg-[#0044FF] text-white font-medium hover:bg-[#0033CC] disabled:opacity-60 transition-colors flex items-center justify-center gap-2"
          >
            {busy && <Loader2 className="h-4 w-4 animate-spin" />} Sign in
          </button>
          <div className="text-sm text-slate-500 text-center">
            No account? <Link to="/signup" className="text-[#0044FF] font-medium">Sign up →</Link>
          </div>
        </form>
      </div>
    </div>
  );
}
