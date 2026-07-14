import React, { useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { Sparkles, Loader2, CheckCircle2 } from "lucide-react";
import { API } from "@/lib/api";

export default function CaptureLead() {
  const { ownerEmail } = useParams();
  const [form, setForm] = useState({ name: "", email: "", company: "", job_title: "", message: "" });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/leads/public?owner_email=${encodeURIComponent(ownerEmail)}`, form);
      setDone(data);
      toast.success("Received — we'll be in touch shortly.");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Submission failed");
    } finally { setBusy(false); }
  };

  if (done) {
    return (
      <div className="min-h-screen bg-[#F7F7F9] grid place-items-center p-6" data-testid="capture-success">
        <div className="max-w-md w-full bg-white rounded-xl border border-slate-200 p-8 text-center">
          <CheckCircle2 className="h-10 w-10 text-emerald-500 mx-auto mb-3" />
          <h2 className="font-display text-2xl font-semibold tracking-tight">Thanks, {done.name.split(" ")[0]}!</h2>
          <p className="text-slate-500 mt-2 text-sm">Our AI has qualified your inquiry and the team has been notified. Expect a reply within the day.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F7F7F9] py-16 px-6" data-testid="capture-page">
      <div className="max-w-lg mx-auto">
        <div className="flex items-center gap-2 mb-8">
          <div className="h-8 w-8 rounded-md bg-[#0044FF] grid place-items-center text-white"><Sparkles className="h-4 w-4" /></div>
          <span className="font-display font-bold text-lg tracking-tight">Get in touch</span>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-8">
          <div className="mb-6">
            <div className="overline mb-2">Inbound</div>
            <h1 className="font-display text-2xl font-semibold tracking-tight">Tell us about your project</h1>
            <p className="text-slate-500 mt-1 text-sm">Our AI SDR reads every submission and routes you to the right person.</p>
          </div>
          <form onSubmit={submit} className="space-y-4" data-testid="capture-form">
            <Field label="Full name" value={form.name} onChange={set("name")} required tid="capture-name" />
            <Field label="Work email" type="email" value={form.email} onChange={set("email")} required tid="capture-email" />
            <Field label="Company" value={form.company} onChange={set("company")} required tid="capture-company" />
            <Field label="Job title" value={form.job_title} onChange={set("job_title")} tid="capture-title" />
            <div>
              <label className="text-sm font-medium">What are you looking for?</label>
              <textarea data-testid="capture-message" value={form.message} onChange={set("message")} rows={4}
                className="mt-1.5 w-full px-3 py-2 rounded-md border border-slate-300 focus:border-[#0044FF] focus:ring-2 focus:ring-[#0044FF]/20 outline-none transition-colors resize-y" />
            </div>
            <button disabled={busy} data-testid="capture-submit"
              className="w-full h-10 rounded-md bg-[#0044FF] hover:bg-[#0033CC] text-white font-medium transition-colors flex items-center justify-center gap-2 disabled:opacity-60">
              {busy && <Loader2 className="h-4 w-4 animate-spin" />} Submit
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, type = "text", required, tid }) {
  return (
    <div>
      <label className="text-sm font-medium">{label}{required && <span className="text-rose-500">*</span>}</label>
      <input data-testid={tid} type={type} required={required} value={value} onChange={onChange}
        className="mt-1.5 w-full h-10 px-3 rounded-md border border-slate-300 focus:border-[#0044FF] focus:ring-2 focus:ring-[#0044FF]/20 outline-none transition-colors" />
    </div>
  );
}
