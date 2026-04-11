# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Consensia is a full-stack idea management app with semantic clustering. Backend: FastAPI + SQLite + ChromaDB + LLM-assisted TOC generation. Frontend: React + Vite + Tailwind. Authentication: Google Authenticator (TOTP) + JWT. Deployed on Raspberry Pi with nginx + Gunicorn.

## Commands

### Backend

```bash
cd backend && source venv/bin/activate

python main.py                        # Dev server (localhost:8000)
pytest                                # All tests (unit + integration)
pytest tests/                         # All tests explicitly
pytest tests/integration/            # Integration tests only
pytest tests/test_main.py            # Specific file
pytest -k "test_health"              # By keyword
pytest --cov=. --cov-report=html     # Coverage with HTML report
make audit                           # ruff check --fix + vulture + pytest (CI gate)
```

### Frontend

```bash
cd frontend

npm run dev                          # Dev server (localhost:5173)
npm test                             # Run all unit tests (Vitest)
npm run test:watch                   # Watch mode
npm run test:coverage                # With coverage (80% threshold required)
npm run test:ci                      # Vitest with coverage (CI gate)
npm run test:e2e                     # Playwright E2E tests (headless Chromium)
npm run test:e2e:ui                  # Playwright interactive UI
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
1. **TDD** for backend: write tests first, then logic
2. Run `make audit-backend` — must be green before touching frontend
3. Write Vitest tests for frontend, then code the UI
4. Run `make audit-frontend` — must be green
5. Run `make audit-all` as final validation

**Rules:**
- Dead code: if `vulture` (Python) or `knip` (JS) flags something, delete it — no exceptions
- Validation: Pydantic (backend) and Zod (frontend) for all external data
- SOLID: refactor violations in any file you touch before adding features
- Documentation: update `CLAUDE.md` whenever a feature is added — new endpoints, schema changes, frontend pages/components, env variables, and architectural decisions must be reflected immediately; also update the relevant files in the `docs/` directory

## Architecture

### Auth Flow
1. User submits email + TOTP code → `POST /verify-otp`
2. Server verifies TOTP against `users.hashed_password` (OTP secret) in SQLite
3. Returns **two tokens**: `access_token` (HS256, 30 min, claim `type: "access"`) and `refresh_token` (HS256, 7 days, claim `type: "refresh"`)
4. Frontend stores both in `localStorage` (`access_token`, `refresh_token`)
5. Axios request interceptor adds `Authorization: Bearer <access_token>` to every request
6. Axios response interceptor handles 401 transparently:
   - If the failing request was `/auth/refresh` itself → clear both tokens + redirect `/` (anti-loop guard)
   - If no `refresh_token` in localStorage → clear `access_token` + redirect `/`
   - Otherwise → call `POST /auth/refresh` silently; concurrent 401s are queued and replayed with the new token; on success the session continues without user interaction
   - If refresh call fails → clear both tokens + redirect `/`
7. `AuthContext` exposes `isAuthenticated`, `user` (includes `is_admin`), `login(accessToken, refreshToken)`, `logout()`
8. TOTP re-auth is only needed once per week at most (refresh token TTL)

### Role-Based Access
- `ProtectedRoute` — checks `isAuthenticated` from `AuthContext`
- `AdminRoute` — checks `isAuthenticated && user.is_admin`
- Admin-only routes: `/admin` → `AdminPage`

### Backend Key Modules
- `main.py` — FastAPI app, all REST endpoints, dependency injection via `Depends()`
- `data_handler.py` — All SQLite CRUD (ideas, tags, books, users, votes, relations, impact comments); uses pandas for query results; all idea writes sync to ChromaDB
- `data_similarity.py` — Semantic pipeline: UMAP → AgglomerativeClustering → LLM title generation → narrative ordering → TOC generation; caches to `data/toc.json`
- `llm_client.py` — LLM abstraction (`LlmPort` Protocol) with 3 backends: `ClaudeLlmClient` (Anthropic API), `OllamaLlmClient` (local), `TfidfFallbackClient`; factory `create_llm_client()` auto-selects the best available backend
- `chroma_client.py` — ChromaDB wrapper for vector similarity search (model: `all-MiniLM-L6-v2`)
- `authenticator.py` — pyotp TOTP; to add a user: `python authenticator.py [email]`
- `config.py` — All paths from environment (`CHROMA_DB`, `NAME_DB`, `TOC_CACHE_PATH`, `ALLOWED_ORIGINS`, `ANTHROPIC_API_KEY`, `LLM_MODEL`, `OLLAMA_URL`, `OLLAMA_MODEL`)
- `utils.py` — `format_text(name, description, tags)` and `unformat_text()` for embedding text construction

### Database Schema (SQLite: `data/knowledge.db`)
- `users(id, username, email, hashed_password, is_admin)` — `hashed_password` stores the TOTP secret (not a hash)
- `books(id, title)` — grouping containers for ideas
- `ideas(id, title, content, owner_id→users.id, book_id→books.id)` — `book_id` is required (NOT NULL)
- `tags(name PK)`
- `relations(idea_id, tag_name)` — composite PK, many-to-many between ideas and tags
- `book_authors(book_id, user_id)` — composite PK, many-to-many between books and users
- `idea_votes(id, idea_id, user_id, value, created_at)` — ON DELETE CASCADE; UNIQUE (idea_id, user_id)
- `impact_comments(id, idea_id, user_id, content, created_at)` — ON DELETE CASCADE; multiple comments per user per idea allowed; creation restricted to book authors (HTTP 403 otherwise)

**Cascade behaviour:** `idea_votes` and `impact_comments` use `ON DELETE CASCADE`. Other tables have no cascade — foreign key enforcement requires `PRAGMA foreign_keys = ON` per connection (not set by default), which is a known quirk pinned by integration tests.

### ChromaDB (vector store)
- Collection path: `CHROMA_DB` env var (default: `backend/data/embeddings`)
- Model: `all-MiniLM-L6-v2`
- Document key: idea `title`
- Every SQLite idea write (insert/update/delete) has a corresponding ChromaDB write in `data_handler.py`

### Frontend Key Files
- `src/App.jsx` — Routes + `ProtectedRoute` / `AdminRoute` wrappers
- `src/services/api.js` — Axios instance with JWT interceptors; `baseURL` from `VITE_API_URL` env var (default: `http://localhost:8000`); module-level queue (`isRefreshing`, `failedQueue`) prevents multiple concurrent refresh calls
- `src/contexts/AuthContext.jsx` — `useAuth()` hook; exposes `isAuthenticated`, `user`, `login(accessToken, refreshToken)`, `logout()` (logout clears both tokens)
- `src/contexts/BookContext.jsx` — `useBook()` hook; selected book state shared across pages
- `src/pages/` — Login, Dashboard, TableOfContents, TagsIdeasPage, BooksPage, AdminPage
- `src/components/` — Navbar, IdeaModal, VoteButtons, BookSelector, ImpactComments

### API Structure
All non-auth endpoints require Bearer token. Key routes:
- `POST /verify-otp` — OTP authentication → `access_token` (30 min) + `refresh_token` (7 days)
- `POST /auth/refresh` — exchange a valid `refresh_token` for new `access_token` + rotated `refresh_token` (no auth header needed)
- `GET/POST /ideas`, `PUT/DELETE /ideas/{id}` — idea CRUD; `book_id` required on POST
- `GET /user/ideas` — ideas owned by current user
- `GET /ideas/similar/{idea}` — semantic similarity via ChromaDB
- `GET /ideas/{id}/votes`, `POST/DELETE /ideas/{id}/vote` — get votes / upvote / remove vote
- `GET /ideas/{id}/impact-comments` — list impact comments for an idea
- `POST /ideas/{id}/impact-comments` — create impact comment (403 if not book author)
- `PUT /impact-comments/{id}` — update own comment (403 if not owner)
- `DELETE /impact-comments/{id}` — delete own comment or any (admin); 403 otherwise
- `GET /books/{id}/impact-comments` — all impact comments for a book (used by TOC export)
- `GET /toc/structure`, `POST /toc/update` — hierarchical TOC (POST is expensive: triggers re-clustering)
- `GET/POST/DELETE /tags`, `POST/DELETE /relations` — tag management
- `GET/POST /books`, `DELETE /books/{id}` — book CRUD
- `GET /books/{id}/authors`, `POST/DELETE /book-authors` — book authorship management
- `GET /users` — list all users (authenticated)
- `GET /admin/users`, `POST /admin/users`, `PUT /admin/users/{id}`, `DELETE /admin/users/{id}` — admin-only user management

### DELETE Endpoints Require `client.request()`
`DELETE /ideas/{id}` and `DELETE /relations` require a JSON body. `httpx.Client.delete()` does not accept `json=`; use the generic method in tests:
```python
client.request("DELETE", f"/ideas/{id}", json={"title": "...", "content": "..."}, headers=headers)
client.request("DELETE", "/relations", json={"idea_id": id, "tag_name": "t"}, headers=headers)
```

## Test Organization

### Backend Tests (`backend/tests/`)
```
tests/
├── test_main.py              # API endpoint unit tests (mocked DB + ML)
├── test_data_handler.py      # SQLite CRUD unit tests
├── test_data_similarity.py   # ML pipeline unit tests
├── test_authenticator.py     # TOTP + JWT unit tests
├── test_chroma_client.py     # ChromaDB wrapper unit tests
├── test_llm_client.py        # LLM client unit tests (Claude, Ollama, TF-IDF fallback)
├── test_utils.py             # text format/unformat unit tests
├── test_admin.py             # admin endpoint unit tests
└── integration/
    ├── conftest.py              # fixtures: real SQLite, FakeChromaClient, JWT helpers
    ├── test_auth.py             # OTP → JWT → protected endpoint chain
    ├── test_idea_lifecycle.py   # full CRUD: create/read/update/delete + Chroma sync
    ├── test_tag_cascades.py     # tag management, relation operations
    ├── test_multi_user.py       # per-user idea isolation
    ├── test_toc_pipeline.py     # TOC cache load/generate/invalidate
    ├── test_books.py            # book CRUD + author management
    ├── test_voting.py           # vote/unvote lifecycle
    └── test_impact_comments.py  # impact comment lifecycle and access control
```

**Unit test pattern** — heavy ML deps (chromadb, sentence-transformers, umap, hdbscan) are mocked at `sys.modules` level at the top of each file. Exception: `test_data_similarity.py::TestEmbeddingAnalyzer` exercises the real UMAP → HDBSCAN pipeline — do not add sys.modules patches that affect it.

**Integration test fixtures** (from `tests/integration/conftest.py`):

| Fixture | Scope | Purpose |
|---|---|---|
| `chroma_store` | function | fresh `{}` dict per test |
| `patch_chroma` | function, autouse | replaces `ChromaClient` with `FakeChromaClient` |
| `db_path` | function | temp SQLite path; sets `NAME_DB` and `TOC_CACHE_PATH` env vars |
| `client` | function | `TestClient(app)` wired to the test DB |
| `alice` | function | test user with real TOTP secret + pre-built auth headers |
| `bob` | function | second test user for isolation tests |

```python
# Helper imports for integration tests
from tests.integration.conftest import create_db_user, make_token, auth_headers
```

**Known quirks pinned by integration tests:**
- `DELETE /ideas/{id}` does NOT cascade relations (no `PRAGMA foreign_keys = ON`)
- `DELETE /tags/{name}` does NOT cascade relations
- Non-existent user email on idea create → `{"id": -1}` (not 4xx)
- Empty TOC list `[]` is falsy → re-generated every request (`if toc:` in main.py)
- Non-book-author on `POST /ideas/{id}/impact-comments` → 403
- Non-owner on `PUT/DELETE /impact-comments/{id}` → 403 (admin bypasses ownership check)

Coverage threshold: **≥ 80%** (pyproject.toml). Full suite achieves ~97%. Running only a subset will report below threshold — expected.

### Frontend Tests (`frontend/src/` + `frontend/e2e/`)

**Unit tests** (Vitest + React Testing Library): co-located as `Component.test.jsx` next to source files. Global mocks in `setupTests.js` cover React Router, axios, and Lucide icons.

**E2E tests** (Playwright): real Chromium browser, all API calls intercepted with `page.route()`. Shared helpers in `e2e/fixtures.ts`.

```
e2e/
├── fixtures.ts               # setAuthToken, mock route helpers, MOCK_IDEAS, MOCK_TOC, etc.
├── auth.spec.ts              # 18 tests: login, logout, 401 interceptor, protected routes
├── ideas-crud.spec.ts        # 26 tests: create/edit/delete, search, similar ideas, tags as chips
├── toc.spec.ts               # 21 tests: rendering, collapse/expand, refresh, markdown export
└── tags-ideas.spec.ts        # 22 tests: tag rendering, orphan deletion, modal
```

**E2E setup (once):**
```bash
cd frontend && npx playwright install chromium
```

The delete flow uses `window.confirm`. Handle in Playwright:
```typescript
page.once('dialog', (dialog) => dialog.accept());   // confirm delete
page.once('dialog', (dialog) => dialog.dismiss());  // cancel delete
```

Both layers enforce **≥ 80%** coverage (vitest.config.ts). E2E tests do not contribute to Vitest coverage.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CHROMA_DB` | `backend/data/embeddings` | ChromaDB persistent storage path |
| `NAME_DB` | `backend/data/knowledge.db` | SQLite database path |
| `TOC_CACHE_PATH` | `backend/data/toc.json` | TOC cache file path |
| `ALLOWED_ORIGINS` | loaded from `backend/data/site.json` | CORS allowed origins |
| `JWT_SECRET_KEY` | — | Required for token signing |
| `ANTHROPIC_API_KEY` | (empty) | Anthropic API key for LLM-powered TOC titles and ordering |
| `LLM_MODEL` | `claude-haiku-4-5-20251001` | Claude model for TOC generation |
| `OLLAMA_URL` | `http://localhost:11434` | Local Ollama server URL (fallback LLM) |
| `OLLAMA_MODEL` | `phi3:mini` | Ollama model for TOC generation |
| `VITE_API_URL` | `http://localhost:8000` | Backend URL for frontend API calls |

## Deployment Notes
- nginx serves frontend from `/var/www/html/consensia/`, proxies `/api/` → `127.0.0.1:8000`
- Gunicorn: `gunicorn -w 1 -k uvicorn.workers.UvicornWorker main:app --bind 127.0.0.1:8000`
- systemd service: `sudo systemctl restart consensia`
- CI/CD: `.github/workflows/ci.yml` builds frontend + runs tests, then deploys via SSH to Raspberry Pi
- On Raspberry Pi 4 (aarch64), PyTorch may require `torch==2.6.0+cpu` to avoid "Illegal Instruction" errors
- Playwright `workers: 1` (sequential) is a Raspberry Pi resource constraint — do not increase
