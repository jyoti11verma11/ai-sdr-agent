import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { LayoutDashboard, Users, BarChart3, Settings as Cog, LogOut, Sparkles, Menu, X, ExternalLink, Beaker, Kanban, UserCog, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import ThemeToggle from "@/components/app/ThemeToggle";
import NotificationsPopover from "@/components/app/NotificationsPopover";

// nav filtered by role
const ALL_NAV = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, testId: "nav-dashboard", roles: ["admin", "sales_manager", "sdr", "viewer"] },
  { to: "/app/leads", label: "Leads", icon: Users, testId: "nav-leads", roles: ["admin", "sales_manager", "sdr", "viewer"] },
  { to: "/app/pipeline", label: "Pipeline", icon: Kanban, testId: "nav-pipeline", roles: ["admin", "sales_manager", "sdr", "viewer"] },
  { to: "/app/analytics", label: "Analytics", icon: BarChart3, testId: "nav-analytics", roles: ["admin", "sales_manager", "sdr", "viewer"] },
  { to: "/app/playground", label: "AI Playground", icon: Beaker, testId: "nav-playground", roles: ["admin", "sales_manager"] },
  { to: "/app/team", label: "Team", icon: UserCog, testId: "nav-team", roles: ["admin", "sales_manager", "sdr", "viewer"] },
  { to: "/app/audit", label: "Audit logs", icon: ShieldCheck, testId: "nav-audit", roles: ["admin", "sales_manager"] },
  { to: "/app/settings", label: "Settings", icon: Cog, testId: "nav-settings", roles: ["admin", "sales_manager"] },
];

export default function AppShell({ children }) {
  const { user, logout } = useAuth();
  const nav_ = useNavigate();
  const loc = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const isActive = (to) => (to === "/app" ? loc.pathname === "/app" : loc.pathname.startsWith(to));
  const role = user?.role || "admin";
  const nav = ALL_NAV.filter((n) => n.roles.includes(role));
  const currentPage = nav.find((n) => isActive(n.to))?.label || "";

  const SidebarInner = (
    <>
      <div className="px-5 py-5 border-b border-border">
        <Link to="/app" className="flex items-center gap-2.5" data-testid="sidebar-logo">
          <div className="h-9 w-9 rounded-lg bg-primary grid place-items-center text-primary-foreground shadow-sm shadow-primary/25">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <div className="font-display font-bold text-[15px] leading-tight tracking-tight">SDR Agent</div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground mt-0.5">AI · Inbound</div>
          </div>
        </Link>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-0.5">
        <div className="px-3 pt-1 pb-2 text-[10px] uppercase tracking-widest text-muted-foreground/70">Workspace</div>
        {nav.map((n) => {
          const Icon = n.icon;
          const active = isActive(n.to);
          return (
            <Link
              key={n.to}
              to={n.to}
              data-testid={n.testId}
              onClick={() => setMobileOpen(false)}
              className={cn(
                "group flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-foreground/70 hover:text-foreground hover:bg-accent"
              )}
            >
              <Icon className={cn("h-4 w-4 shrink-0", active ? "" : "text-muted-foreground group-hover:text-foreground")} />
              <span>{n.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="px-3 pb-3">
        <a
          href={`/capture/${user?.email}`}
          target="_blank"
          rel="noreferrer"
          className="flex items-center justify-between gap-2 rounded-md border border-dashed border-border px-3 py-2 text-xs text-muted-foreground hover:border-primary/50 hover:text-foreground transition-colors"
          data-testid="sidebar-capture-link"
        >
          <div className="min-w-0">
            <div className="font-medium truncate text-foreground">Public capture link</div>
            <div className="truncate">/capture/{user?.email}</div>
          </div>
          <ExternalLink className="h-3.5 w-3.5 shrink-0" />
        </a>
      </div>

      <div className="p-3 border-t border-border">
        <div className="flex items-center gap-3 px-2 py-1.5 rounded-md">
          <div className="h-9 w-9 rounded-full bg-foreground text-background grid place-items-center font-semibold text-sm">
            {(user?.full_name || user?.email || "U").slice(0, 1).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate" data-testid="user-name">{user?.full_name}</div>
            <div className="text-xs text-muted-foreground truncate">{user?.email}</div>
          </div>
          <button
            onClick={() => { logout(); nav_("/"); }}
            className="p-2 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
            title="Sign out"
            data-testid="logout-btn"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-[hsl(var(--shell-bg))] text-foreground flex" data-testid="app-shell">
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex w-64 shrink-0 border-r border-border bg-[hsl(var(--shell-sidebar))] flex-col sticky top-0 h-screen">
        {SidebarInner}
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex" data-testid="mobile-nav-drawer">
          <div className="fixed inset-0 bg-background/60 backdrop-blur-sm" onClick={() => setMobileOpen(false)} />
          <aside className="relative w-72 max-w-[85%] bg-[hsl(var(--shell-sidebar))] border-r border-border flex flex-col">
            {SidebarInner}
          </aside>
        </div>
      )}

      <div className="flex-1 min-w-0 flex flex-col">
        {/* Top bar */}
        <header className="sticky top-0 z-30 h-14 border-b border-border bg-background/80 glass flex items-center justify-between px-4 lg:px-8">
          <div className="flex items-center gap-3">
            <button
              className="lg:hidden inline-flex items-center justify-center h-9 w-9 rounded-md border border-border bg-card hover:bg-accent transition-colors"
              onClick={() => setMobileOpen(true)}
              data-testid="mobile-menu-toggle"
              aria-label="Open menu"
            >
              <Menu className="h-4 w-4" />
            </button>
            <div className="text-sm text-muted-foreground hidden sm:block">
              Workspace · <span className="text-foreground font-medium">{currentPage}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a href={`/capture/${user?.email}`} target="_blank" rel="noreferrer"
              className="hidden sm:inline-flex items-center gap-1.5 text-xs h-9 px-3 rounded-md border border-border bg-card hover:bg-accent transition-colors">
              <ExternalLink className="h-3.5 w-3.5" /> Capture URL
            </a>
            <NotificationsPopover />
            <ThemeToggle />
          </div>
        </header>

        <main className="flex-1 min-w-0">{children}</main>
      </div>
    </div>
  );
}
