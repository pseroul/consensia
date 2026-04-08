# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Consensia is a full-stack idea management app with semantic clustering. Backend: FastAPI + SQLite + ChromaDB. Frontend: React + Vite + Tailwind. Authentication: Google Authenticator (TOTP) + JWT. Deployed on Raspberry Pi with nginx + Gunicorn.

## Commands

### Backend

```bash
cd backend && source venv/bin/activate

python main.py                        # Dev server (localhost:8000)
pytest                                # All tests
pytest tests/test_main.py            # Specific file
pytest -k "test_health"              # By keyword
pytest --cov=.                       # With coverage (80% threshold required)
make audit                           # ruff check + vulture + pytest (must pass before moving on)
```

### Frontend

```bash
cd frontend

npm run dev                          # Dev server (localhost:5173)
npm test                             # Run all tests (Vitest)
npm run test:watch                   # Watch mode
npm run test:coverage                # With coverage (80% threshold required)
npm run lint                         # ESLint
npm run validate                     # Lint + knip (dead code detection)
VITE_API_URL=https://... npm run build  # Production build → dist/
```

### Root

```bash
make audit-backend    # cd backend && make audit
make audit-frontend   # cd frontend && npm run validate
make audit-all        # Both
```

## Quality Protocol

Before submitting any change:
1. Read `.cline/architecture.md` before coding
2. **TDD** for backend: write tests first, then logic
3. Run `make audit-backend` — must be green before touching frontend
4. Write Vitest tests for frontend, then code the UI
5. Run `make audit-frontend` — must be green
6. Run `make audit-all` as final validation

**Rules:**
- Dead code: if `vulture` (Python) or `knip` (JS) flags something, delete it — no exceptions
- Validation: Pydantic (backend) and Zod (frontend) for all external data
- SOLID: refactor violations in any file you touch before adding features

## Architecture

### Auth Flow
1. User submits email + TOTP code → `POST /verify-otp`
2. Server verifies TOTP against `users.hashed_password` (OTP secret) in SQLite
3. Returns JWT (HS256, 30 min expiry)
4. Frontend stores in `localStorage.access_token`
5. Axios interceptor adds `Authorization: Bearer <token>` to all requests; 401 clears token and redirects to `/`

### Backend Key Modules
- `main.py` — FastAPI app, all REST endpoints, dependency injection via `Depends()`
- `data_handler.py` — All SQLite CRUD (ideas, tags, relations, users); uses pandas for query results
- `data_similarity.py` — Semantic pipeline: Sentence Transformers → UMAP → HDBSCAN clustering → TOC generation; caches to `data/toc.json`
- `chroma_client.py` — ChromaDB wrapper for vector similarity search (model: `all-distilroberta-v1`)
- `authenticator.py` — pyotp TOTP; to add a user: `python authenticator.py [email]`
- `config.py` — All paths from environment (`CHROMA_DB`, `NAME_DB`, `TOC_CACHE_PATH`)

### Database Schema (SQLite: `data/knowledge.db`)
- `users(id, username, email, hashed_password)` — `hashed_password` stores the OTP secret
- `ideas(id, title, content, owner_id→users.id)`
- `tags(name PK)`
- `relations(idea_id, tag_name)` — many-to-many between ideas and tags

### Frontend Key Files
- `src/App.jsx` — Routes + `ProtectedRoute` wrapper (checks `localStorage.access_token`)
- `src/services/api.js` — Axios instance with JWT interceptors
- `src/pages/` — Login, Dashboard, TableOfContents, TagsIdeasPage
- `src/components/` — Navbar, IdeaModal

### API Structure
All non-auth endpoints require Bearer token. Key routes:
- `GET/POST /ideas`, `PUT/DELETE /ideas/{id}` — idea CRUD
- `GET /user/ideas` — ideas owned by current user
- `GET /ideas/similar/{idea}` — semantic similarity via ChromaDB
- `GET /toc/structure`, `POST /toc/update` — hierarchical TOC (expensive: triggers re-clustering)
- `GET/POST/DELETE /tags`, `POST/DELETE /relations` — tag management

### Test Organization
- Backend: `backend/tests/` (unit) + `backend/tests/integration/` (full lifecycle tests)
- Frontend: tests co-located as `Component.test.jsx` next to source files
- Both enforce 80% coverage threshold

## Deployment Notes
- nginx serves frontend from `/var/www/html/consensia/`, proxies `/api/` → `127.0.0.1:8000`
- Gunicorn: `gunicorn -w 1 -k uvicorn.workers.UvicornWorker main:app --bind 127.0.0.1:8000`
- On Raspberry Pi 4 (aarch64), PyTorch may require `torch==2.6.0+cpu` to avoid "Illegal Instruction" errors
