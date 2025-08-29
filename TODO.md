# TODO

This is the prioritized worklist for TalkToDB. Use this as the single source of truth for open tasks.

## Backend (API & Logic)
- [ ] Auth/JWT + role-based access (protect `settings` and sensitive routes)
- [ ] API Keys (`keys.py`): real CRUD, encryption at rest (Fernet/AES‑GCM), key rotation
- [ ] Connections (`connections.py`): add update/delete; encrypt connection strings
- [ ] Query history (`history.py`): persist logs, rerun, audit trail (user, SQL, decision)
- [ ] Multi‑DB support: extend schema discovery beyond Postgres (SQLite/MySQL/SQL Server)
- [ ] Schema caching with TTL/invalidation per `connection_id`
- [ ] Guardrails+: per‑role table/column allowlist, row/time limits by config
- [ ] NL→SQL provider adapters in `services/llm/*` (Anthropic/Gemini/Groq), config model mapping
- [ ] Pagination/streaming for large result sets; configurable row/column limits
- [ ] Export results (CSV/Parquet) endpoint
- [ ] Observability: structured logging, request IDs, metrics
- [ ] Rate limiting + standardized error responses

## Visualization (AI Chart)
- [x] Allow user override (type/x/y) and save presets per query
- [x] Support multi‑series (yKeys) and better time‑series detection/resampling
- [x] Add “generate-and-suggest-chart” endpoint that: generate SQL → execute → suggest chart in one step

## Frontend (UX)
- [ ] SQL editor (Monaco), copy/format SQL, “Approve & Execute” button
- [ ] Schema Explorer+: PK/FK/Indexes, search/filter
- [ ] History page: table view, rerun, pin favorites
- [ ] Export CSV/Copy table; page size selector
- [ ] Consolidated data hooks (loading/error), consistent toasts/spinners
- [ ] Dark mode

## Data/Model
- [ ] Metadata DB migrations (Alembic) for Keys/Connections/History/SchemaSnapshots
- [ ] Indexes/constraints for metadata tables; minimal demo seeds

## Security
- [ ] Encrypt at rest (keys/connection strings); `.env` hygiene
- [ ] CSP/secure headers; CSRF if cookie auth; password policy
- [ ] Secrets scanning in CI

## Infra/DevOps
- [ ] Dockerfile (FE/BE) + docker-compose for full stack
- [ ] CI: lint/test (frontend + backend) + build + security scan + preview deploy
- [ ] Cross‑platform shell scripts (Bash) mirroring `scripts/start-all.ps1`

## Testing & QA
- [ ] Unit tests: guardrails, sql_chain (sanitize/ILIKE), schema discovery
- [ ] Integration tests: generate → execute → suggest‑chart (with demo DB fixtures)
- [ ] E2E (Playwright): Studio and Settings core flows

## Docs
- [ ] Provider setup guide (keys, base_url, model names) for Anthropic/Gemini/Groq
- [ ] Document `SchemaSnapshot` JSON format with examples
- [ ] Expanded troubleshooting (Windows/Docker/IPv6/ports)

## Nice‑to‑have
- [ ] Multiple connections concurrently + tabbed results
- [ ] Domain prompt templates (multi‑lingual VI/EN)
- [ ] “Refine query” loop (ask‑back clarifications) and SQL explain

---
Last updated: 2025-08-27
