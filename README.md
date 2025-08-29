# TalkToDBAgent

## Tech stack
- **Frontend**: Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, react-chartjs-2, Chart.js, React Hook Form, React Query
- **Backend**: FastAPI, Pydantic v2, SQLAlchemy, Uvicorn, HTTPX
- **AI/LLM**: LangChain with OpenAI (pluggable providers available), Tenacity for retries
- **Database**: PostgreSQL (Dockerized for demo), SQLAlchemy engines (supports Postgres/MySQL drivers in deps)
- **Tooling**: ESLint + Prettier (frontend), Black/Isort/Mypy/PyTest (backend)
- **Scripts**: PowerShell orchestrator in `scripts/`
- **Languages**: TypeScript (FE), Python 3.10+ (BE)

## Structure
```
.
├─ frontend/                      # Next.js UI (App Router)
│  ├─ app/                        # Pages: studio, history, settings
│  ├─ components/                 # Reusable UI components
│  └─ lib/                        # API client, hooks, utilities
├─ server/                        # FastAPI backend
│  ├─ app/main.py                 # App entrypoint (routers, CORS)
│  ├─ app/api/routes/             # REST endpoints (auth, query, schema, etc.)
│  ├─ app/services/               # LLM + SQL execution/guardrails
│  └─ app/db/models/              # Metadata models and schema snapshots
├─ infra/docker/                  # Docker compose and DB seed
└─ scripts/                       # Start-all PowerShell scripts
```
