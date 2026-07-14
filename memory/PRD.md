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
