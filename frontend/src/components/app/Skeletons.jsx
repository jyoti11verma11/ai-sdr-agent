import React from "react";

export function SkeletonBlock({ className = "h-4 w-full rounded-md" }) {
  return <div className={`shimmer ${className}`} />;
}

export function SkeletonKpi() {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center justify-between">
        <SkeletonBlock className="h-3 w-20 rounded" />
        <SkeletonBlock className="h-7 w-7 rounded-md" />
      </div>
      <SkeletonBlock className="mt-4 h-8 w-24 rounded" />
      <SkeletonBlock className="mt-2 h-3 w-16 rounded" />
    </div>
  );
}

export function SkeletonRow() {
  return (
    <div className="grid grid-cols-6 gap-4 px-4 py-3 border-b border-border">
      {[...Array(6)].map((_, i) => <SkeletonBlock key={i} className="h-4 rounded" />)}
    </div>
  );
}

export function SkeletonInsight() {
  return (
    <div className="rounded-lg border border-border p-4 space-y-2">
      <SkeletonBlock className="h-3 w-40 rounded" />
      <SkeletonBlock className="h-3 w-full rounded" />
      <SkeletonBlock className="h-3 w-3/4 rounded" />
    </div>
  );
}
