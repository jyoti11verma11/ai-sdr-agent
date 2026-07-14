# AI SDR Agent — Product Requirements Document

## Original Problem Statement
Build a production-ready SaaS "AI SDR Agent" that automates inbound lead qualification and sales handoff using AI. Tech stack: React + FastAPI + MongoDB + JWT + GPT-5.2 + HubSpot + Slack + n8n. Enterprise-grade UI, clean architecture, deployable.

## User Choices Selected (defaults, user assumed defaults)
- **Database**: MongoDB (instead of Postgres) — already provisioned locally
- **LLM**: OpenAI GPT-5.2 via Emergent Universal Key
- **HubSpot / Slack**: Mocked with real API fallbacks (activate by adding tokens in Settings)
- **Auth**: JWT email/password (bcrypt)
- **n8n**: Configurable webhook

## Architecture
```
/app
├── backend/
│   ├── server.py            # FastAPI, /api routes
│   ├── models.py            # Pydantic v2 models
│   ├── auth.py              # JWT + bcrypt
│   └── services/
│       ├── ai_service.py    # GPT-5.2 qualify + email (heuristic fallback)
│       └── integrations.py  # HubSpot, Slack, n8n
├── frontend/src/
│   ├── App.js               # Router + AuthProvider + Toaster
│   ├── lib/
│   │   ├── api.js           # Axios instance with token interceptor
│   │   ├── auth.jsx         # Auth context
│   │   └── utils.js         # cn, scoreColor, statusColor, timeAgo
│   ├── pages/
│   │   ├── Landing.jsx      # Dark marketing page (Manrope + bento grid)
│   │   ├── Login.jsx, Signup.jsx
│   │   ├── Dashboard.jsx    # KPIs + AI Insights + Activity
│   │   ├── Leads.jsx        # Searchable + filterable table
│   │   ├── Analytics.jsx    # Recharts (line/bar/pie/funnel)
│   │   ├── Settings.jsx     # Integration toggles + tokens
│   │   └── CaptureLead.jsx  # Public inbound form
│   └── components/app/
│       ├── AppShell.jsx     # Left nav + user card
│       ├── NewLeadDialog.jsx
│       └── LeadDrawer.jsx   # Full lead detail (Shadcn Sheet)
```

## What's implemented (2026-07-14)
- Auth: signup / login / JWT bearer / /auth/me
- Lead CRUD: create (auth), create public, list (search + status filter), get, patch status, regenerate email, delete
- AI qualification pipeline (GPT-5.2, ~5-15s per lead): industry, company size, buying intent, 0-100 score, summary, key signals, recommended action + reason
- AI personalized email generator (subject + body)
- Deterministic heuristic fallback (if LLM budget/timeouts)
- HubSpot / Slack / n8n integrations (real HTTP if tokens set, MOCKED activity otherwise)
- Activity timeline (created, qualified, email_generated, hubspot_sync, slack_notified, n8n_triggered, status_change)
- Settings page for tokens + auto-run toggles
- Dashboard: 4 KPIs, AI Insights panel, Recent Activity, public capture link
- Leads table with score badges (green ≥85, blue 65-84, amber 40-64, rose <40) and status pills
- Analytics: leads-over-time line, score distribution bar, industry pie, conversion funnel
- Public lead capture form `/capture/{ownerEmail}` (no auth)
- Swiss/high-contrast dashboard + dark bento landing (Manrope + IBM Plex Sans)
- All 27 backend tests pass (see `/app/test_reports/iteration_1.json`)

## User Personas
- **Sales AE**: sees dashboard, filters qualified leads, opens drawer, copies AI email.
- **RevOps admin**: configures HubSpot/Slack/n8n in Settings, embeds public capture link.
- **Prospect (public)**: fills `/capture/{ownerEmail}` form; gets auto-routed.

## Prioritized Backlog
- **P1**: Async LLM pipeline (background task + SSE polling) so `POST /api/leads` returns immediately
- **P1**: HubSpot & Slack real OAuth (currently token-only)
- **P2**: Pagination on `/api/leads`
- **P2**: MongoDB aggregation for `/api/analytics/summary` (currently in-memory)
- **P2**: Email send integration (Resend / SendGrid) — currently only drafts
- **P3**: Team seats + roles
- **P3**: Vercel + Render deployment configs, Dockerfile, CI

## Deferred (in first finish)
- Docker files / README (mentioned in problem but non-blocking for functional demo)
- TypeScript conversion (frontend is .jsx; backend is Python)

## Phase 2 delivered (2026-07-14)
- **Service-class architecture**: `HubSpotService`, `SlackService`, `N8nService`, `IntegrationOrchestrator` — each with `is_configured`, `test_connection`, and consistent `{provider, action, status, message, data, at}` result shape.
- **HubSpot real API**: contact + company + deal + association endpoints; auto Mock Mode fallback when no token.
- **Slack real API**: 3 notification types — qualified, high-priority (score ≥ 85 → HIGH_PRIORITY_SCORE env), qualification-failed.
- **n8n**: outbound webhook with 3-attempt exponential backoff (BASE_BACKOFF=1s, MAX_ATTEMPTS=3); test-connection uses 1 attempt.
- **Integration logs**: new `integration_logs` collection persists every attempt (owner_id, provider, action, status, message, lead_id, attempts, data, created_at).
- **New endpoints**:
  - `GET /api/integrations/status` — per-provider {configured, mode, last_sync, last_status, last_message}
  - `POST /api/integrations/{provider}/test` — real Test Connection
  - `GET /api/integrations/logs?provider=&limit=` — history
  - `POST /api/leads/{id}/retry-sync` — re-run all enabled integrations
  - `PATCH /api/leads/{id}/status` — now also calls HubSpot sync_status if contact_id known
- **DI**: `get_orchestrator` FastAPI dependency injects a per-request orchestrator wired to that user's settings.
- **Frontend**:
  - Dashboard: **Integrations** health strip with live/mock/error chips + last-sync per provider.
  - Settings: per-integration Mock/Live/Error pill + **Test connection** button + last-sync line.
  - LeadDrawer: activity dots colored by status (green=success, amber=mock, red=error, blue=info), attempt counters, **Retry integrations** button.
- **Tests**: 46/46 passing (Phase 1's 27 + 19 Phase 2 tests).

## Phase 3 delivered (2026-07-14) — True AI SDR Agent

### Extended qualification schema
`business_type`, `icp_match` (bool) + `icp_match_reasoning`, `urgency` (Low/Medium/High/Immediate), `decision_maker_probability` (0-100), `score_explanation`, `action_reasoning`. Recommended action now one of `{Book Demo, Call Immediately, Send Personalized Email, Add to Nurture Campaign, Reject Lead}`.

### Personalised outreach kit
`lead.outreach = { subject, first_email, linkedin_message, followup_email }` — all 4 pieces auto-generated. Per-piece regenerate via `POST /api/leads/{id}/regenerate?type=first_email|linkedin_message|followup_email|all`.

### Background processing
`POST /api/leads` returns in <1s with `processing_status='pending'`. FastAPI BackgroundTasks runs the pipeline async: pending → analyzing → qualified/failed. Dashboard polls `/api/leads/status-counts` every 4s while any pending/analyzing leads exist.

### AI Decisions timeline
Every LLM call persisted to `ai_decisions` collection with: id, owner_id, lead_id, decision_type, prompt_name, prompt_version, model, input_summary, output, reasoning, score, action, latency_ms, status (success/fallback/error), at. Exposed at `GET /api/leads/{id}/decisions`.

### AI Playground
- `GET /api/prompts` — list versioned prompts (qualification + outreach)
- `PUT /api/prompts/{name}` — bumps version
- `POST /api/prompts/{name}/reset` — restore default
- `POST /api/prompts/{name}/test` — dry-run with sample lead
- New `/app/playground` page with tabbed editor + live test panel

### AI Analytics endpoint
`GET /api/analytics/ai` — avg_ai_score, high_intent_leads, industry_distribution, top_icp_matches, qualification_success_rate, avg_processing_ms, prompt_versions, total_ai_decisions.

### Frontend additions (existing design preserved)
- Dashboard: 4-slot processing status strip with live polling
- LeadDrawer: processing pill, full qualification metadata grid (ICP + reasoning + score explanation + DM probability + urgency), Next Best Action card with reasoning, three per-piece outreach blocks with copy+regen, AI Decisions timeline
- Analytics: AI Performance metrics strip (5 KPIs) + Top fits by AI + Industries by AI
- New AI Playground page and nav item

### Tests
79/79 backend tests passing (100%). Phase 3 added 33 new tests covering async pipeline, prompt versioning, per-piece regeneration, AIDecision persistence, analytics AI shape.

## Phase 4 delivered (2026-07-14) — Production-grade AI SDR platform

### Team & RBAC
- `Workspace` + `Invite` + user roles (`admin`, `sales_manager`, `sdr`, `viewer`). Signup creates workspace or joins via invite token.
- `require_role(*roles)` FastAPI dep gates settings, integrations, playground, audit, invites, role changes.
- JWT now carries `wid + role`.

### Lead assignment engine
- `AssignmentEngine` with priority-sorted rules (region / industry / min-max score) → user OR round-robin fallback.
- Auto-assignment happens inside the async pipeline. Manual override via `PATCH /leads/{id}/assign`. Every assignment writes an activity + notification + audit log with a human `assignment_reason`.

### Kanban pipeline
- 7 fixed stages: new → qualified → demo_scheduled → proposal_sent → negotiation → closed_won / closed_lost.
- `PATCH /leads/{id}/stage` appends `StageChange` history with by_user_id.
- `GET /leads/pipeline` returns `{stages, by_stage}` — powers frontend Kanban with HTML5 native drag-drop.

### Notes / comments / @mentions
- `POST /leads/{id}/notes` — `@user@company.com` mentions parsed → mention IDs stored + `mention` notification fired.

### Notifications (polling)
- `GET /notifications` returns `{items, unread}`. `POST /notifications/{id}/read` and `read-all`. Bell popover polls every 15s.
- Kinds: `lead_assigned`, `qualification_done`, `email_sent`, `meeting_scheduled`, `mention`, `webhook_failed`, `slack_failed`.

### Audit logs
- `AuditService` writes on every mutating action. `GET /audit` + `GET /audit/export.csv`.

### Email via Resend
- `EmailService` (Resend + mock fallback). Draft / send-now / schedule via `POST /leads/{id}/emails`.
- Delivery tracking via public `POST /webhooks/resend` — `sent → delivered → opened → clicked` transitions.

### Meetings
- `POST /leads/{id}/meetings/propose` — AI-shaped 3 slot recommendation (urgency-aware).
- `POST /leads/{id}/meetings` — one-click Google Calendar template URL + auto-transitions stage to `demo_scheduled`.
- `GET /leads/{id}/meetings/{id}/ics` — downloadable .ics file.

### Advanced analytics
`GET /analytics/advanced` — sales funnel, pipeline value USD, revenue forecast, avg cycle days, source performance, stage conversion rates, win rate, top SDRs leaderboard, AI recommendation accuracy.

### Frontend (design preserved, additive only)
- New pages: **Pipeline** (drag-drop Kanban), **Team** (invite + role manager), **Audit logs** (filterable table + CSV export).
- `NotificationsPopover` bell in top bar with unread badge.
- LeadDrawer extended: assignment picker with reason, quick-actions (send email + book meeting), AI-slot dialog, email compose (draft/send), email history with status pills, meeting list with GCal link, notes composer + comments.
- Role-based nav: SDRs don't see Settings / Playground / Audit.

### Ops
- `docker-compose.yml` (mongo + backend + frontend), backend + frontend Dockerfiles, `.env.example`, `DEPLOYMENT.md`.
- API docs auto-served at `/docs`, `/redoc`, `/openapi.json`.

### Tests
- **112/112 backend tests pass** (79 P1-P3 + 33 P4). ~200s wall clock. `pytest tests/ -v` from `/app/backend`.

### Deferred / future-hardening (from test agent report)
- Resend webhook HMAC signature verification
- Deterministic ordering of `_members()` for RR
- Reject demoting the last admin
- JSON-encode `old_value`/`new_value` columns in audit CSV
- Split `server.py` into domain routers (~1070 lines now)
