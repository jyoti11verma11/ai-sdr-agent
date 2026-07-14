import React, { useEffect, useState, useRef } from "react";
import api from "@/lib/api";
import { Bell, CheckCheck, Circle } from "lucide-react";
import { timeAgo } from "@/lib/utils";

export default function NotificationsPopover() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const ref = useRef(null);

  const load = async () => {
    try {
      const { data } = await api.get("/notifications");
      setItems(data.items); setUnread(data.unread);
    } catch {}
  };
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, []);

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const markAll = async () => {
    await api.post("/notifications/read-all"); load();
  };
  const markOne = async (id) => { await api.post(`/notifications/${id}/read`); load(); };

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(!open)} data-testid="notifications-toggle"
        className="relative inline-flex items-center justify-center h-9 w-9 rounded-md border border-border bg-card hover:bg-accent transition-colors">
        <Bell className="h-4 w-4" />
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 h-4 w-4 rounded-full bg-primary text-primary-foreground text-[10px] font-bold grid place-items-center">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-80 rounded-lg border border-border bg-popover shadow-lg z-50" data-testid="notifications-panel">
          <div className="p-3 border-b border-border flex items-center justify-between">
            <div className="text-sm font-semibold">Notifications</div>
            {unread > 0 && (
              <button onClick={markAll} className="text-xs inline-flex items-center gap-1 text-primary hover:underline">
                <CheckCheck className="h-3 w-3" /> Mark all read
              </button>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {items.length === 0 ? (
              <div className="p-6 text-sm text-muted-foreground text-center">Nothing yet — you're all caught up.</div>
            ) : (
              <ul className="divide-y divide-border">
                {items.map((n) => (
                  <li key={n.id} className={`p-3 text-sm ${n.read ? "" : "bg-accent/40"}`} onClick={() => !n.read && markOne(n.id)}>
                    <div className="flex items-start gap-2">
                      {!n.read && <Circle className="h-2 w-2 fill-primary text-primary mt-1.5 shrink-0" />}
                      <div className="min-w-0 flex-1">
                        <div className="text-xs uppercase tracking-widest font-bold text-muted-foreground">{n.kind.replace("_", " ")}</div>
                        <div className="font-medium mt-0.5 line-clamp-1">{n.title}</div>
                        {n.body && <div className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{n.body}</div>}
                        <div className="text-[10px] text-muted-foreground mt-1">{timeAgo(n.created_at)}</div>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
