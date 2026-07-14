import React from "react";
import { cn } from "@/lib/utils";

export default function EmptyState({ icon, title, description, action, className = "", testId = "empty-state" }) {
  return (
    <div
      data-testid={testId}
      className={cn(
        "rounded-xl border border-dashed border-border bg-card/50 p-10 flex flex-col items-center justify-center text-center",
        className
      )}
    >
      {icon && (
        <div className="h-11 w-11 rounded-lg bg-primary/10 text-primary grid place-items-center mb-4">
          {icon}
        </div>
      )}
      <div className="font-display text-lg font-semibold tracking-tight">{title}</div>
      {description && <p className="text-sm text-muted-foreground mt-1.5 max-w-md">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
