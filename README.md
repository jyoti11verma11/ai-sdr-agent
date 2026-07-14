# AI SDR Agent

Production-ready SaaS that automates inbound lead qualification & sales handoff using GPT-5.2.

## Features
- **AI Qualification Engine** — GPT-5.2 analyses company, industry, size, buying intent → 0-100 score + summary + recommended action.
- **AI Email Generator** — hyper-personalised outbound draft per lead.
- **Dashboard** — total leads, qualified count, conversion %, avg score, AI insights, live activity.
- **Analytics** — leads-over-time, score distribution, industry mix, funnel.
- **Integrations** — HubSpot, Slack, n8n (mocked out-of-the-box; drop in tokens in Settings to go live).
- **Public capture form** at `/capture/{owner_email}` — embed anywhere.
- **JWT auth** — bcrypt password hashing, 7-day tokens.

## Stack
- Frontend: React 19, React Router 7, Tailwind, Framer Motion, Recharts, Shadcn/UI
- Backend: FastAPI, Motor (async MongoDB), Pydantic v2, PyJWT, bcrypt
- LLM: OpenAI GPT-5.2 via **Emergent Universal Key**
- DB: MongoDB

## Local development
```bash
# backend
cd backend
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# frontend
cd frontend
yarn install
yarn start
```

## Environment
Backend `/app/backend/.env`:
```
MONGO_URL="mongodb://localhost:27017"
DB_NAME="test_database"
CORS_ORIGINS="*"
EMERGENT_LLM_KEY=sk-emergent-...
JWT_SECRET=change-me-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=168
```

Frontend `/app/frontend/.env`:
```
REACT_APP_BACKEND_URL=https://your-backend-url
```

## API (all prefixed with `/api`)
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/` | — | Health |
| POST | `/auth/signup` | — | Create workspace |
| POST | `/auth/login` | — | Get JWT |
| GET | `/auth/me` | ✓ | Current user |
| GET | `/settings` | ✓ | Integration settings |
| PUT | `/settings` | ✓ | Update settings |
| POST | `/leads` | ✓ | Create + qualify lead |
| POST | `/leads/public?owner_email=` | — | Public capture |
| GET | `/leads?q=&status=` | ✓ | List (search + filter) |
| GET | `/leads/{id}` | ✓ | Single lead |
| PATCH | `/leads/{id}/status` | ✓ | Update status |
| POST | `/leads/{id}/regenerate-email` | ✓ | Regenerate AI email |
| DELETE | `/leads/{id}` | ✓ | Delete |
| GET | `/analytics/summary` | ✓ | Dashboard KPIs |
| GET | `/analytics/activity` | ✓ | Activity feed |

## Deployment
- **Frontend → Vercel**: build with `yarn build`, output `build/`, set `REACT_APP_BACKEND_URL`.
- **Backend → Render/Railway**: run `uvicorn server:app --host 0.0.0.0 --port $PORT`, set all env vars.
- **MongoDB**: MongoDB Atlas or your provider — set `MONGO_URL`.

## Testing
```
cd backend && python -m pytest tests/backend_test.py -v
```
Latest run: **27/27 passing**.
