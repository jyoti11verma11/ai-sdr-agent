import React from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, Sparkles, Target, Mail, Zap, LineChart, Shield, CheckCircle2 } from "lucide-react";

const stagger = { hidden: {}, show: { transition: { staggerChildren: 0.08 } } };
const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.5 } } };

export default function Landing() {
  return (
    <div className="min-h-screen bg-[#050505] text-white overflow-x-hidden" data-testid="landing-page">
      {/* Sticky nav */}
      <header className="sticky top-0 z-50 glass bg-black/60 border-b border-white/5">
        <div className="max-w-7xl mx-auto flex items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-center gap-2" data-testid="landing-logo">
            <div className="h-8 w-8 rounded-md bg-[#3366FF] grid place-items-center">
              <Sparkles className="h-4 w-4" />
            </div>
            <span className="font-display font-bold text-lg tracking-tight">SDR Agent</span>
          </Link>
          <nav className="hidden md:flex items-center gap-8 text-sm text-white/70">
            <a href="#features" className="hover:text-white transition-colors">Features</a>
            <a href="#how" className="hover:text-white transition-colors">How it works</a>
            <a href="#pricing" className="hover:text-white transition-colors">Pricing</a>
            <a href="#faq" className="hover:text-white transition-colors">FAQ</a>
          </nav>
          <div className="flex items-center gap-3">
            <Link to="/login" data-testid="nav-login" className="text-sm text-white/80 hover:text-white transition-colors">Sign in</Link>
            <Link
              to="/signup"
              data-testid="nav-signup"
              className="text-sm font-medium bg-white text-black px-4 py-2 rounded-md hover:bg-white/90 transition-colors"
            >
              Start free
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative">
        <div className="absolute inset-0 dot-grid opacity-40" />
        <div className="max-w-7xl mx-auto px-6 pt-24 pb-32 relative">
          <motion.div initial="hidden" animate="show" variants={stagger} className="max-w-4xl">
            <motion.div variants={fadeUp} className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/70 mb-8">
              <span className="h-1.5 w-1.5 rounded-full bg-[#3366FF]" />
              GPT-5.2 powered — qualifies inbound in under 6 seconds
            </motion.div>
            <motion.h1 variants={fadeUp} className="font-display text-5xl md:text-6xl lg:text-7xl tracking-tighter font-bold leading-[0.95]">
              Your inbound pipeline,<br/>
              <span className="text-white/40">auto-qualified.</span>
            </motion.h1>
            <motion.p variants={fadeUp} className="mt-6 max-w-2xl text-lg text-white/70 leading-relaxed">
              An AI SDR that reads every inbound lead, scores fit &amp; intent, drafts a personalised email, and hands hot deals to your AEs — through HubSpot &amp; Slack — before your team refills their coffee.
            </motion.p>
            <motion.div variants={fadeUp} className="mt-10 flex flex-wrap items-center gap-4">
              <Link to="/signup" data-testid="hero-cta-signup" className="group inline-flex items-center gap-2 bg-[#3366FF] hover:bg-[#5577FF] text-white px-6 py-3 rounded-md font-medium transition-colors">
                Start qualifying <ArrowRight className="h-4 w-4 group-hover:translate-x-0.5 transition-transform" />
              </Link>
              <a href="#how" className="text-sm text-white/70 hover:text-white transition-colors">See how the agent thinks →</a>
            </motion.div>

            <motion.div variants={fadeUp} className="mt-16 grid grid-cols-2 md:grid-cols-4 gap-8 text-left">
              {[
                {k:"6s", v:"avg qualification"},
                {k:"92%", v:"AE agree with score"},
                {k:"3.4×", v:"faster follow-ups"},
                {k:"0", v:"missed hot leads"},
              ].map((s) => (
                <div key={s.k}>
                  <div className="font-display text-3xl font-bold tracking-tight">{s.k}</div>
                  <div className="text-xs uppercase tracking-[0.2em] text-white/50 mt-1">{s.v}</div>
                </div>
              ))}
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* Bento features */}
      <section id="features" className="max-w-7xl mx-auto px-6 py-24">
        <div className="mb-12 max-w-2xl">
          <div className="overline mb-3">Capabilities</div>
          <h2 className="font-display text-3xl md:text-4xl tracking-tight font-semibold">
            An SDR that never sleeps, misses, or forgets follow-up.
          </h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
          <BentoCard span="md:col-span-8" title="AI Qualification Engine" icon={<Target className="h-5 w-5" />} desc="Analyses company, size, industry and buying intent, then assigns a 0–100 score with a plain-english summary.">
            <div className="mt-6 rounded-lg border border-white/10 bg-black/40 p-5 font-mono text-xs text-white/80">
              <div className="text-white/40 mb-2">// live_qualification.json</div>
              <pre className="whitespace-pre-wrap leading-relaxed">{`{
  "score": 87,
  "buying_intent": "High",
  "recommended_action": "Assign to AE",
  "summary": "VP Eng at 500-person fintech asking about SOC2..."
}`}</pre>
            </div>
          </BentoCard>
          <BentoCard span="md:col-span-4" title="Personalised email" icon={<Mail className="h-5 w-5" />} desc="Drafts a hyper-relevant outbound email using the lead's own signals." />
          <BentoCard span="md:col-span-4" title="HubSpot sync" icon={<Zap className="h-5 w-5" />} desc="Creates the contact + activity in your CRM automatically." />
          <BentoCard span="md:col-span-4" title="Slack alerts" icon={<Sparkles className="h-5 w-5" />} desc="Hot leads land in #sales-hot with score & one-click actions." />
          <BentoCard span="md:col-span-4" title="Analytics" icon={<LineChart className="h-5 w-5" />} desc="Conversion funnel, score distribution, and AI insights on your pipeline." />
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="max-w-7xl mx-auto px-6 py-24 border-t border-white/5">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
          <div className="md:col-span-5">
            <div className="overline mb-3">Workflow</div>
            <h2 className="font-display text-3xl md:text-4xl tracking-tight font-semibold">From form-fill to first reply in under a minute.</h2>
          </div>
          <ol className="md:col-span-7 space-y-6">
            {[
              {n:"01", t:"Lead lands", d:"Any inbound form, chatbot or n8n webhook pushes the lead in."},
              {n:"02", t:"AI reads & scores", d:"GPT-5.2 analyses signals, assigns 0–100 fit + intent score."},
              {n:"03", t:"Email drafted", d:"A personalised outbound draft is ready in your dashboard."},
              {n:"04", t:"Handoff", d:"HubSpot contact created, Slack #sales-hot pinged, n8n fired."},
            ].map((s) => (
              <li key={s.n} className="grid grid-cols-[80px_1fr] gap-6 items-start">
                <div className="font-mono text-sm text-[#3366FF]">{s.n}</div>
                <div>
                  <div className="font-display text-xl font-medium">{s.t}</div>
                  <div className="text-white/60 mt-1 text-sm leading-relaxed">{s.d}</div>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="max-w-7xl mx-auto px-6 py-24 border-t border-white/5">
        <div className="max-w-2xl mb-12">
          <div className="overline mb-3">Pricing</div>
          <h2 className="font-display text-3xl md:text-4xl tracking-tight font-semibold">Priced per qualified lead. Never per seat.</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            {name:"Starter", price:"$0", desc:"For teams testing inbound.", perks:["50 leads / mo","Mock integrations","Community support"]},
            {name:"Growth", price:"$149", desc:"For growing SDR teams.", perks:["1,000 leads / mo","HubSpot + Slack","Priority email support"], highlight:true},
            {name:"Scale", price:"Custom", desc:"For revenue orgs.", perks:["Unlimited leads","SSO + audit log","Dedicated success"]},
          ].map((p) => (
            <div key={p.name} className={`rounded-xl p-6 border ${p.highlight ? "border-[#3366FF] bg-[#3366FF]/10" : "border-white/10 bg-white/[0.02]"}`}>
              <div className="flex items-baseline justify-between">
                <div className="font-display text-xl font-semibold">{p.name}</div>
                <div className="font-display text-2xl font-bold">{p.price}<span className="text-sm text-white/50 font-normal">/mo</span></div>
              </div>
              <p className="text-sm text-white/60 mt-2">{p.desc}</p>
              <ul className="mt-6 space-y-2 text-sm">
                {p.perks.map((pk) => (
                  <li key={pk} className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-[#3366FF]" /> {pk}</li>
                ))}
              </ul>
              <Link to="/signup" data-testid={`pricing-cta-${p.name.toLowerCase()}`} className={`mt-6 block text-center py-2.5 rounded-md text-sm font-medium transition-colors ${p.highlight ? "bg-white text-black hover:bg-white/90" : "bg-white/10 hover:bg-white/20"}`}>
                Get {p.name}
              </Link>
            </div>
          ))}
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-6 py-24 border-t border-white/5">
        <div className="rounded-2xl bg-gradient-to-br from-[#0033CC] via-[#0044FF] to-[#3366FF] p-12 relative overflow-hidden grain">
          <div className="max-w-2xl">
            <h3 className="font-display text-3xl md:text-4xl tracking-tight font-bold">Stop losing inbound to slow follow-up.</h3>
            <p className="mt-3 text-white/80">Sign up in 30 seconds. First 50 leads on us.</p>
            <Link to="/signup" data-testid="footer-cta-signup" className="mt-6 inline-flex items-center gap-2 bg-white text-black px-5 py-2.5 rounded-md text-sm font-semibold hover:bg-white/90 transition-colors">
              Start free <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-white/5 py-10">
        <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-white/50">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4" /> SOC2-ready • Data isolated per workspace
          </div>
          <div>© {new Date().getFullYear()} SDR Agent, Inc.</div>
        </div>
      </footer>
    </div>
  );
}

function BentoCard({ span, title, icon, desc, children }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.5 }}
      className={`${span} rounded-xl border border-white/10 bg-white/[0.02] p-6 hover:bg-white/[0.04] transition-colors`}
    >
      <div className="flex items-center gap-3 text-[#3366FF]">
        <div className="h-9 w-9 rounded-md bg-[#3366FF]/10 border border-[#3366FF]/20 grid place-items-center">
          {icon}
        </div>
        <div className="font-display font-medium text-lg text-white">{title}</div>
      </div>
      <p className="mt-3 text-sm text-white/60 leading-relaxed">{desc}</p>
      {children}
    </motion.div>
  );
}
