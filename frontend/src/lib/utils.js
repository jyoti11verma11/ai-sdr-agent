import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) { return twMerge(clsx(inputs)); }

export function scoreColor(score) {
  if (score == null) return "bg-slate-100 text-slate-600 border-slate-200";
  if (score >= 85) return "bg-emerald-50 text-emerald-700 border-emerald-200";
  if (score >= 65) return "bg-blue-50 text-blue-700 border-blue-200";
  if (score >= 40) return "bg-amber-50 text-amber-700 border-amber-200";
  return "bg-rose-50 text-rose-700 border-rose-200";
}

export function statusColor(s) {
  const map = {
    new: "bg-slate-100 text-slate-700 border-slate-200",
    qualifying: "bg-violet-50 text-violet-700 border-violet-200",
    qualified: "bg-emerald-50 text-emerald-700 border-emerald-200",
    disqualified: "bg-rose-50 text-rose-700 border-rose-200",
    contacted: "bg-blue-50 text-blue-700 border-blue-200",
    converted: "bg-black text-white border-black",
  };
  return map[s] || map.new;
}

export function timeAgo(iso) {
  if (!iso) return "—";
  const d = typeof iso === "string" ? new Date(iso) : iso;
  const s = Math.floor((Date.now() - d.getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s/60)}m ago`;
  if (s < 86400) return `${Math.floor(s/3600)}h ago`;
  return `${Math.floor(s/86400)}d ago`;
}
