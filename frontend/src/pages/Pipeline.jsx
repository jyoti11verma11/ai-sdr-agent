import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { Loader2, Plus } from "lucide-react";
import { scoreColor } from "@/lib/utils";
import LeadDrawer from "@/components/app/LeadDrawer";
import EmptyState from "@/components/app/EmptyState";

const STAGE_META = {
  new: { label: "New", color: "border-slate-300" },
  qualified: { label: "Qualified", color: "border-emerald-400" },
  demo_scheduled: { label: "Demo Scheduled", color: "border-blue-400" },
  proposal_sent: { label: "Proposal Sent", color: "border-violet-400" },
  negotiation: { label: "Negotiation", color: "border-amber-400" },
  closed_won: { label: "Closed Won", color: "border-emerald-600" },
  closed_lost: { label: "Closed Lost", color: "border-rose-400" },
};

export default function Pipeline() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [dragging, setDragging] = useState(null);

  const load = async () => {
    setLoading(true);
    try { const { data } = await api.get("/leads/pipeline"); setData(data); }
    catch (e) { toast.error("Failed to load pipeline"); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const onDrop = async (stage) => {
    if (!dragging || dragging.stage === stage) { setDragging(null); return; }
    setDragging(null);
    try {
      await api.patch(`/leads/${dragging.id}/stage`, { pipeline_stage: stage });
      toast.success(`${dragging.name} → ${STAGE_META[stage].label}`);
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Move failed"); }
  };

  return (
    <div className="px-4 sm:px-6 lg:px-8 py-6 lg:py-8" data-testid="pipeline-page">
      <div className="mb-6">
        <div className="overline mb-2">Sales</div>
        <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tighter">Pipeline</h1>
        <p className="text-sm text-muted-foreground mt-1.5">Drag leads across stages. Stage history is auto-tracked.</p>
      </div>

      {loading ? (
        <div className="grid place-items-center h-64 text-muted-foreground"><Loader2 className="h-5 w-5 animate-spin" /></div>
      ) : !data || Object.values(data.by_stage).every((v) => v.length === 0) ? (
        <EmptyState icon={<Plus className="h-5 w-5" />} title="No leads in pipeline" description="Capture a lead to start filling the board." />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-7 gap-3 overflow-x-auto">
          {data.stages.map((stage) => (
            <div key={stage}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => onDrop(stage)}
              className="min-w-[220px] flex flex-col"
              data-testid={`pipeline-col-${stage}`}>
              <div className={`rounded-t-lg border-t-2 ${STAGE_META[stage].color} bg-card border-x border-border px-3 py-2 flex items-center justify-between`}>
                <div className="text-[10px] uppercase tracking-widest font-bold">{STAGE_META[stage].label}</div>
                <div className="text-xs text-muted-foreground font-mono">{data.by_stage[stage].length}</div>
              </div>
              <div className="flex-1 space-y-2 border-x border-b border-border rounded-b-lg bg-muted/30 p-2 min-h-[100px]">
                {data.by_stage[stage].map((l) => {
                  const q = l.qualification || {};
                  return (
                    <motion.div key={l.id}
                      layout draggable
                      onDragStart={() => setDragging({ id: l.id, stage, name: l.name })}
                      onClick={() => setSelected(l.id)}
                      data-testid={`pipeline-card-${l.id}`}
                      className="rounded-md border border-border bg-card p-2.5 cursor-grab active:cursor-grabbing hover:border-primary/40 transition-colors">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="text-sm font-semibold truncate">{l.name}</div>
                          <div className="text-xs text-muted-foreground truncate">{l.company}</div>
                        </div>
                        {q.score != null && <span className={`score-badge border shrink-0 ${scoreColor(q.score)}`}>{q.score}</span>}
                      </div>
                      {q.buying_intent && <div className="text-[10px] text-muted-foreground mt-1">{q.industry} · {q.buying_intent}</div>}
                    </motion.div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      <LeadDrawer leadId={selected} onClose={() => setSelected(null)} onChanged={load} />
    </div>
  );
}
