import React from "react";
import { useTheme } from "@/lib/theme";
import { Sun, Moon } from "lucide-react";

export default function ThemeToggle({ className = "" }) {
  const { theme, toggle } = useTheme();
  const isDark = theme === "dark";
  return (
    <button
      onClick={toggle}
      data-testid="theme-toggle"
      title={isDark ? "Switch to light" : "Switch to dark"}
      className={`inline-flex items-center justify-center h-9 w-9 rounded-md border border-border bg-card hover:bg-accent transition-colors ${className}`}
    >
      {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}
