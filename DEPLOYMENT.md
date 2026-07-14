# Deployment guide

## 1. Docker Compose (all-in-one)
```bash
cp .env.example .env
# edit .env — set JWT_SECRET, EMERGENT_LLM_KEY, REACT_APP_BACKEND_URL
docker compose up -d --build
```
- Backend: `http://localhost:8001` (API base: `/api`)
- Frontend: `http://localhost:3000`
- MongoDB: `localhost:27017` (volume persisted)

## 2. Split (recommended for production)

### Backend → Render / Railway / Fly.io
- Runtime: Python 3.11
- Start command: `uvicorn server:app --host 0.0.0.0 --port $PORT`
- Env vars: see `.env.example`. `CORS_ORIGINS` must list your frontend URL.

### Frontend → Vercel / Netlify
- Build command: `yarn build`
- Output dir: `build`
- Env: `REACT_APP_BACKEND_URL` = your backend URL

### Database → MongoDB Atlas
- Free tier is fine for < 1000 leads. Use SRV connection string.

## 3. API documentation
FastAPI auto-generates OpenAPI + Swagger UI:
- **Swagger**: `${BACKEND_URL}/docs`
- **ReDoc**: `${BACKEND_URL}/redoc`
- **OpenAPI JSON**: `${BACKEND_URL}/openapi.json`

## 4. Resend webhook (email delivery tracking)
Point Resend to `POST ${BACKEND_URL}/api/webhooks/resend` (no auth). Events tracked:
`email.sent`, `email.delivered`, `email.opened`, `email.clicked`, `email.bounced`, `email.complained`.

## 5. Post-deploy checklist
- [ ] `POST /api/auth/signup` creates first admin
- [ ] Add teammates via **Team** page (auto invite token URL)
- [ ] Configure integrations under **Settings** (Resend, HubSpot, Slack, n8n, Google Calendar organizer email)
- [ ] Verify email delivery — test with your own inbox
- [ ] Review `/app/audit` after any admin action
