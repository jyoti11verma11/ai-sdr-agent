# 🚀 AI SDR Agent

> **An AI-powered Sales Development Representative (SDR) platform that automates inbound lead qualification, AI-powered lead scoring, personalized outreach, and CRM handoff.**

🌐 **Live Demo:** https://ai-sdr-agent-frontend.onrender.com

---

## 📌 Project Overview

AI SDR Agent is a full-stack SaaS application designed to automate the initial stages of the sales pipeline.

Instead of manually reviewing every lead, the platform uses **OpenAI** to analyze lead information, assign an AI qualification score, generate personalized outreach emails, and seamlessly integrate with CRM and automation platforms.

The project demonstrates how AI can streamline modern Go-To-Market (GTM) workflows by reducing manual effort and accelerating sales handoffs.

---

# ✨ Key Features

### 🤖 AI Lead Qualification

- Analyze company details using OpenAI
- Generate qualification score (0–100)
- AI-generated lead summary
- Recommended next action

---

### 📧 AI Email Generation

- Personalized outbound email drafts
- Context-aware messaging
- Sales-ready responses

---

### 📊 Analytics Dashboard

- Total Leads
- Qualified Leads
- Conversion Rate
- Average Lead Score
- AI Insights
- Live Activity Feed

---

### 🔗 CRM & Automation

- HubSpot Integration
- Slack Notifications
- n8n Workflow Automation
- Public Lead Capture Forms

---

### 🔐 Authentication

- JWT Authentication
- Secure Password Hashing
- Workspace-based Login

---

## 🛠 Tech Stack

### Frontend

- React 19
- React Router 7
- Tailwind CSS
- Framer Motion
- Shadcn/UI
- Recharts

### Backend

- FastAPI
- Python
- Motor (Async MongoDB)
- Pydantic v2
- PyJWT
- bcrypt

### AI

- OpenAI GPT API

### Database

- MongoDB

### Integrations

- HubSpot
- Slack
- n8n

---

# 🏗 System Architecture

```text
               Lead Capture Form
                      │
                      ▼
              React Frontend
                      │
                      ▼
              FastAPI Backend
                      │
      ┌───────────────┼───────────────┐
      │               │               │
      ▼               ▼               ▼
   OpenAI          MongoDB         HubSpot
      │                               │
      ▼                               ▼
 AI Qualification              CRM Synchronization
      │
      ▼
Slack Notifications / n8n Automation
```

---

# 📸 Screenshots

> *(Add screenshots after deployment)*

### 🏠 Landing Page

(Add Screenshot)

---

### 📈 Dashboard

(Add Screenshot)

---

### 🤖 AI Lead Qualification

(Add Screenshot)

---

### 📊 Analytics

(Add Screenshot)

---

# ⚙️ Local Installation

## Clone Repository

```bash
git clone https://github.com/jyoti11verma11/ai-sdr-agent.git
```

## Backend

```bash
cd backend

pip install -r requirements.txt

uvicorn server:app --reload
```

## Frontend

```bash
cd frontend

npm install

npm start
```

---

# 🔑 Environment Variables

Backend

```env
MONGO_URL=
DB_NAME=
OPENAI_API_KEY=
JWT_SECRET=
JWT_ALGORITHM=
JWT_EXPIRE_HOURS=
```

Frontend

```env
REACT_APP_BACKEND_URL=
```

---

# 📡 API Endpoints

| Method | Endpoint | Description |
|----------|-------------------------|--------------------------|
| POST | /auth/signup | Register User |
| POST | /auth/login | Login |
| POST | /leads | Create Lead |
| GET | /leads | Get Leads |
| PATCH | /leads/{id}/status | Update Lead |
| DELETE | /leads/{id} | Delete Lead |
| GET | /analytics/summary | Dashboard Analytics |

---

# 🎯 Use Cases

- AI Sales Assistant
- Lead Qualification
- CRM Automation
- GTM Engineering Portfolio
- Sales Workflow Automation
- AI-powered Prospect Management

---

# 🚀 Future Improvements

- Clay Integration
- Apollo Integration
- Gmail API
- Multi-user Workspaces
- AI Voice Agent
- Calendar Scheduling
- Email Sequencing
- Role-based Access Control

---

# 👩‍💻 Author

**Jyoti Verma**

Computer Science Graduate

GTM Engineer | AI Automation | Full-Stack Development

---

⭐ If you found this project useful, consider giving it a star.
