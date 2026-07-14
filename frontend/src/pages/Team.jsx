import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Loader2, UserPlus, Trash2, Copy } from "lucide-react";
import { useAuth } from "@/lib/auth";

const ROLES = ["admin", "sales_manager", "sdr", "viewer"];

export default function Team() {
  const { user } = useAuth();
  const [members, setMembers] = useState([]);
  const [invites, setInvites] = useState([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("sdr");
  const [busy, setBusy] = useState(false);
  const canManage = user?.role === "admin" || user?.role === "sales_manager";

  const load = async () => {
    const calls = [api.get("/workspace/members")];
    if (canManage) calls.push(api.get("/workspace/invites"));
    const results = await Promise.all(calls);
    setMembers(results[0].data);
    if (canManage) setInvites(results[1].data);
  };
  useEffect(() => { load(); }, [canManage]);

  const invite = async (e) => {
    e.preventDefault(); setBusy(true);
    try {
      await api.post("/workspace/invites", { email, role });
      toast.success("Invite created");
      setEmail(""); load();
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  const revoke = async (id) => {
    if (!window.confirm("Revoke this invite?")) return;
    await api.delete(`/workspace/invites/${id}`); load(); toast.success("Revoked");
  };

  const changeRole = async (uid, newRole) => {
    await api.patch(`/workspace/members/${uid}`, { role: newRole });
    toast.success("Role updated"); load();
  };

  const inviteLink = (t) => `${window.location.origin}/signup?invite=${t}`;
  const copy = (t) => { navigator.clipboard.writeText(t); toast.success("Copied"); };

  return (
    <div className="px-4 sm:px-6 lg:px-8 py-6 lg:py-8 max-w-4xl mx-auto" data-testid="team-page">
      <div className="mb-6">
        <div className="overline mb-2">Team</div>
        <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tighter">Workspace members</h1>
        <p className="text-sm text-muted-foreground mt-1.5">Manage teammates and their roles.</p>
      </div>

      {canManage && (
        <form onSubmit={invite} className="rounded-xl border border-border bg-card p-5 mb-6 flex flex-col sm:flex-row gap-3">
          <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required
            placeholder="teammate@company.com" data-testid="invite-email"
            className="flex-1 h-10 px-3 rounded-md border border-border bg-background field-focus text-sm" />
          <select value={role} onChange={(e) => setRole(e.target.value)} data-testid="invite-role"
            className="h-10 px-3 rounded-md border border-border bg-background text-sm">
            {ROLES.map((r) => <option key={r} value={r}>{r.replace("_", " ")}</option>)}
          </select>
          <button disabled={busy} data-testid="invite-submit"
            className="inline-flex items-center gap-2 h-10 px-4 rounded-md bg-primary text-primary-foreground font-medium hover:bg-primary/90 disabled:opacity-60 transition-colors">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />} Invite
          </button>
        </form>
      )}

      <div className="rounded-xl border border-border bg-card overflow-hidden mb-6" data-testid="members-table">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground border-b border-border">
            <tr><th className="text-left px-4 py-3 font-semibold">Member</th><th className="text-left px-4 py-3 font-semibold">Role</th></tr>
          </thead>
          <tbody>
            {members.map((m) => (
              <tr key={m.user_id} className="border-b border-border last:border-0">
                <td className="px-4 py-3">
                  <div className="font-medium">{m.full_name}</div>
                  <div className="text-xs text-muted-foreground">{m.email}</div>
                </td>
                <td className="px-4 py-3">
                  {user?.role === "admin" && m.user_id !== user.id ? (
                    <select value={m.role} onChange={(e) => changeRole(m.user_id, e.target.value)}
                      data-testid={`role-${m.user_id}`}
                      className="h-8 px-2 rounded-md border border-border bg-background text-xs">
                      {ROLES.map((r) => <option key={r} value={r}>{r.replace("_", " ")}</option>)}
                    </select>
                  ) : (
                    <span className="inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium border border-border bg-muted">{m.role}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {canManage && invites.length > 0 && (
        <div className="rounded-xl border border-border bg-card overflow-hidden" data-testid="invites-table">
          <div className="px-4 py-3 border-b border-border overline">Pending invites</div>
          <table className="w-full text-sm">
            <tbody>
              {invites.map((i) => (
                <tr key={i.id} className="border-b border-border last:border-0">
                  <td className="px-4 py-3">
                    <div className="text-sm">{i.email}</div>
                    <div className="text-xs text-muted-foreground">{i.role}</div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => copy(inviteLink(i.token))}
                      className="inline-flex items-center gap-1 text-xs h-8 px-2 rounded-md hover:bg-accent transition-colors">
                      <Copy className="h-3 w-3" /> Copy link
                    </button>
                    <button onClick={() => revoke(i.id)}
                      className="ml-2 inline-flex items-center gap-1 text-xs h-8 px-2 rounded-md text-destructive hover:bg-destructive/10 transition-colors">
                      <Trash2 className="h-3 w-3" /> Revoke
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
