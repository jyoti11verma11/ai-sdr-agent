import React from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { LayoutDashboard, Users, BarChart3, Settings as Cog, LogOut, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

const nav = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, testId: "nav-dashboard" },
  { to: "/app/leads", label: "Leads", icon: Users, testId: "nav-leads" },
  { to: "/app/analytics", label: "Analytics", icon: BarChart3, testId: "nav-analytics" },
  { to: "/app/settings", label: "Settings", icon: Cog, testId: "nav-settings" },
];

export default function AppShell({ children }) {
  const { user, logout } = useAuth();
  const nav_ = useNavigate();
  const loc = useLocation();
  const isActive = (to) => (to === "/app" ? loc.pathname === "/app" : loc.pathname.startsWith(to));

  return (
    <div className="min-h-screen bg-[#F7F7F9] text-slate-900 flex" data-testid="app-shell">
      <aside className="w-64 shrink-0 border-r border-slate-200/80 bg-white flex flex-col">
        <div className="px-6 py-6 border-b border-slate-100">
          <Link to="/app" className="flex items-center gap-2" data-testid="sidebar-logo">
            <div className="h-8 w-8 rounded-md bg-[#0044FF] grid place-items-center text-white">
              <Sparkles className="h-4 w-4" />
            </div>
            <div>
              <div className="font-display font-bold text-lg leading-tight tracking-tight">SDR Agent</div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">AI • Inbound</div>
            </div>
          </Link>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {nav.map((n) => {
            const Icon = n.icon;
            const active = isActive(n.to);
            return (
              <Link
                key={n.to}
                to={n.to}
                data-testid={n.testId}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  active ? "bg-[#0044FF] text-white" : "text-slate-700 hover:bg-slate-100"
                )}
              >
                <Icon className="h-4 w-4" />
                <span>{n.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-slate-100">
          <div className="flex items-center gap-3 px-2 py-2 rounded-md">
            <div className="h-9 w-9 rounded-full bg-slate-900 text-white grid place-items-center font-semibold text-sm">
              {(user?.full_name || user?.email || "U").slice(0,1).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate" data-testid="user-name">{user?.full_name}</div>
              <div className="text-xs text-slate-500 truncate">{user?.email}</div>
            </div>
            <button
              onClick={() => { logout(); nav_("/"); }}
              className="p-2 rounded-md text-slate-500 hover:text-rose-600 hover:bg-rose-50 transition-colors"
              title="Sign out"
              data-testid="logout-btn"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      <main className="flex-1 min-w-0">
        {children}
      </main>
    </div>
  );
}
