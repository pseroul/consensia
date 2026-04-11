# Architecture

This document describes the full system architecture of Consensia, intended for developers joining the project. It covers system structure (C4 diagrams), the database schema, authentication flow, request lifecycle, and key design decisions.

---

## System Overview (C4 Level 1 — Context)

```mermaid
graph TB
    User["👤 User\n(Browser)"]
    Admin["👤 Admin\n(Browser)"]
    GA["📱 Google Authenticator\n(TOTP App)"]

    Consensia["🖥️ Consensia\nIdea management app with\nsemantic clustering\n(nginx + FastAPI + React)"]

    User -->|"HTTPS — browse ideas,\ncreate/search/vote"| Consensia
    Admin -->|"HTTPS — manage users,\nview admin panel"| Consensia
    User -->|"reads 6-digit OTP"| GA
    Admin -->|"reads 6-digit OTP"| GA
```

Consensia is a self-hosted, single-tenant web application. There are no external service dependencies beyond the TOTP app on the user's phone.

---

## Container Diagram (C4 Level 2)

```mermaid
graph TB
    Browser["🌐 Browser\nReact 19 SPA\nVite build\nTailwindCSS"]

    subgraph Pi["Raspberry Pi 4 (aarch64)"]
        nginx["nginx\nReverse proxy\nServes static files\nPort 80 / 443"]
        FastAPI["FastAPI app\nGunicorn + Uvicorn worker\nPort 8000 (internal only)"]
        SQLite["SQLite\nbackend/data/knowledge.db\nPrimary data store"]
        ChromaDB["ChromaDB\nbackend/data/embeddings/\nVector store for embeddings"]
    end

    Browser -- "HTTPS /api/*" --> nginx
    Browser -- "HTTPS /* (static)" --> nginx
    nginx -- "proxy_pass 127.0.0.1:8000" --> FastAPI
    nginx -- "serves /var/www/html/consensia" --> Browser
    FastAPI -- "reads/writes" --> SQLite
    FastAPI -- "reads/writes embeddings" --> ChromaDB
```

**Key points:**
- nginx is the single entry point; the FastAPI port is never exposed publicly
- ChromaDB runs in-process (embedded, no separate daemon)
- SQLite is the source of truth; ChromaDB holds only the vector index

---

## Component Diagram (C4 Level 3 — Backend)

```mermaid
graph TB
    subgraph FastAPI["FastAPI Application (main.py)"]
        Routes["REST Routes\n26 endpoints\nPydantic validation"]
        AuthDep["Auth Dependencies\nget_current_user()\nrequire_admin()"]
        Routes --> AuthDep
    end

    subgraph DataLayer["Data Layer"]
        DH["data_handler.py\nSQLite CRUD\npandas DataFrames\nChromaDB sync"]
        DS["data_similarity.py\nTOC generation\nClustering pipeline\nCaching"]
        CC["chroma_client.py\nChromaDB wrapper\nEmbedding model\n(all-MiniLM-L6-v2)"]
        LC["llm_client.py\nLLM abstraction\nClaude API / Ollama / TF-IDF\nTitle generation & ordering"]
    end

    subgraph Auth["Authentication"]
        Authn["authenticator.py\npyotp TOTP\nJWT generation"]
    end

    subgraph Config["Configuration"]
        Cfg["config.py\nEnvironment variables\nsite.json loading"]
    end

    Routes --> DH
    Routes --> DS
    Routes --> Authn
    DH --> CC
    DS --> CC
    DS --> LC
    FastAPI --> Cfg
```

---

## Component Diagram (C4 Level 3 — Frontend)

```mermaid
graph TB
    subgraph App["React App (src/App.jsx)"]
        Router["React Router v7\nClient-side routing"]
        ProtectedRoute["ProtectedRoute\nchecks isAuthenticated"]
        AdminRoute["AdminRoute\nchecks isAuthenticated\n&& user.is_admin"]
    end

    subgraph Contexts["Context Providers"]
        AuthCtx["AuthContext\nJWT decode\nlocalStorage persistence\nlogin() / logout()"]
        BookCtx["BookContext\nSelected book state\nauto-fetches books on mount"]
    end

    subgraph Pages["Pages (src/pages/)"]
        Login["Login\n/"]
        Dashboard["Dashboard\n/dashboard"]
        TOC["TableOfContents\n/table-of-contents"]
        Tags["TagsIdeasPage\n/tags-ideas"]
        Books["BooksPage\n/books"]
        Admin["AdminPage\n/admin"]
    end

    subgraph Services["Services (src/services/)"]
        API["api.js\nAxios instance\nBASE_URL = VITE_API_URL\nRequest interceptor: add Bearer token\nResponse interceptor: 401 → silent refresh\nor clear tokens + redirect /"]
    end

    Router --> ProtectedRoute
    Router --> AdminRoute
    ProtectedRoute --> Dashboard & TOC & Tags & Books
    AdminRoute --> Admin
    Pages --> AuthCtx
    Pages --> BookCtx
    Pages --> API
```

---

## Database Schema

```mermaid
erDiagram
    users {
        INTEGER id PK
        TEXT username UK
        TEXT email UK
        TEXT hashed_password "stores TOTP secret (not a hash)"
        INTEGER is_admin "0 or 1"
    }

    books {
        INTEGER id PK
        TEXT title
    }

    ideas {
        INTEGER id PK
        TEXT title
        TEXT content
        INTEGER owner_id FK
        INTEGER book_id FK
    }

    tags {
        TEXT name PK
    }

    relations {
        INTEGER idea_id FK
        TEXT tag_name FK
    }

    book_authors {
        INTEGER book_id FK
        INTEGER user_id FK
    }

    idea_votes {
        INTEGER id PK
        INTEGER idea_id FK
        INTEGER user_id FK
        INTEGER value "1 or -1"
        DATETIME created_at
    }

    users ||--o{ ideas : "owns"
    books ||--o{ ideas : "contains"
    ideas ||--o{ relations : "has"
    tags ||--o{ relations : "labels"
    books ||--o{ book_authors : "has"
    users ||--o{ book_authors : "authors"
    ideas ||--o{ idea_votes : "receives"
    users ||--o{ idea_votes : "casts"
```

**Constraints:**
- `ideas.book_id` is `NOT NULL` — every idea must belong to a book
- `idea_votes` has a `UNIQUE(idea_id, user_id)` constraint — one vote per user per idea
- `relations` has a composite primary key `(idea_id, tag_name)`
- `book_authors` has a composite primary key `(book_id, user_id)`
- **No `ON DELETE CASCADE`** is defined anywhere (see [Key Design Decisions](#key-design-decisions))

**Important naming quirk:** The `hashed_password` column in `users` stores the raw TOTP secret — it is not a hash. The column name is a historical artefact.

---

## Authentication Flow

```mermaid
sequenceDiagram
    actor User
    participant Browser
    participant FastAPI
    participant SQLite

    User->>Browser: Enter email + 6-digit OTP
    Browser->>FastAPI: POST /verify-otp {email, otp_code}
    FastAPI->>SQLite: SELECT hashed_password WHERE email=?
    SQLite-->>FastAPI: TOTP secret
    FastAPI->>FastAPI: pyotp.TOTP(secret).verify(otp_code)
    alt OTP valid
        FastAPI-->>Browser: {access_token (30 min), refresh_token (7 days)}
        Browser->>Browser: localStorage.setItem("access_token", ...)<br/>localStorage.setItem("refresh_token", ...)
        Browser->>Browser: Redirect to /dashboard
    else OTP invalid / expired
        FastAPI-->>Browser: 401 Unauthorized
    end

    Note over Browser,FastAPI: Subsequent authenticated requests
    Browser->>FastAPI: GET /ideas (Authorization: Bearer <access_token>)
    FastAPI->>FastAPI: JWT.decode(token) — verify type == "access"
    FastAPI->>SQLite: SELECT is_admin WHERE email=?
    FastAPI-->>Browser: 200 OK [ideas array]

    Note over Browser,FastAPI: Silent token refresh (access token expired)
    FastAPI-->>Browser: 401 Unauthorized
    Browser->>Browser: axios interceptor — queue concurrent requests
    Browser->>FastAPI: POST /auth/refresh {refresh_token}
    FastAPI->>FastAPI: JWT.decode(refresh_token) — verify type == "refresh"
    alt Refresh token valid
        FastAPI-->>Browser: new {access_token, refresh_token} (rotated)
        Browser->>Browser: update localStorage with new tokens
        Browser->>FastAPI: retry original request with new access_token
        FastAPI-->>Browser: 200 OK — user session continues uninterrupted
    else Refresh token invalid / expired
        FastAPI-->>Browser: 401 Unauthorized
        Browser->>Browser: clear both tokens → redirect to /
    end
```

**JWT claims:**

| Claim | Access token | Refresh token |
|---|---|---|
| `sub` | user email | user email |
| `exp` | now + 30 minutes | now + 7 days |
| `type` | `"access"` | `"refresh"` |
| `is_admin` | boolean | boolean |
| Algorithm | HS256 | HS256 |

The `type` claim prevents cross-use: `get_current_user()` rejects any token where `type != "access"`, and `POST /auth/refresh` rejects tokens where `type != "refresh"`. Tokens without a `type` claim (issued before this feature) default to `"access"` for backwards compatibility.

The frontend decodes the JWT payload client-side (without signature verification) solely to read `is_admin` for UI decisions. All authorisation is enforced server-side on every request.

---

## Request Lifecycle

A typical authenticated request (e.g. `GET /ideas?book_id=1`) flows as follows:

```mermaid
sequenceDiagram
    participant Browser
    participant nginx
    participant Gunicorn
    participant FastAPI
    participant SQLite
    participant ChromaDB

    Browser->>nginx: GET /api/ideas?book_id=1\nAuthorization: Bearer <token>
    nginx->>Gunicorn: proxy_pass /ideas?book_id=1
    Gunicorn->>FastAPI: ASGI request
    FastAPI->>FastAPI: Depends(get_current_user)\ndecode JWT → email
    FastAPI->>SQLite: SELECT is_admin WHERE email=?
    FastAPI->>SQLite: SELECT ideas + tags + votes WHERE book_id=1
    SQLite-->>FastAPI: rows (pandas DataFrame)
    FastAPI-->>Gunicorn: JSON response
    Gunicorn-->>nginx: response
    nginx-->>Browser: 200 OK [{ideas}]
```

**ChromaDB** is only involved in two cases:
1. Idea writes (insert/update/delete) — triggered asynchronously via `ThreadPoolExecutor`
2. `GET /ideas/similar/{idea}` — synchronous vector similarity query
3. `GET /toc/structure` or `POST /toc/update` — fetches all embeddings for clustering

---

## Environment Variables

| Variable | Default | Required | Description |
|---|---|---|---|
| `JWT_SECRET_KEY` | `your-secret-key-here-change-in-production` | **Yes** | JWT signing secret — change before deployment |
| `NAME_DB` | `backend/data/knowledge.db` | No | SQLite database file path |
| `CHROMA_DB` | `backend/data/embeddings` | No | ChromaDB persistent storage directory |
| `TOC_CACHE_PATH` | `backend/data/toc.json` | No | TOC JSON cache file path |
| `ALLOWED_ORIGINS` | loaded from `backend/data/site.json` | No | CORS allowed origins (set via `site.json`) |
| `ANTHROPIC_API_KEY` | (empty) | No | Claude API key for LLM-powered TOC titles and ordering |
| `LLM_MODEL` | `claude-haiku-4-5-20251001` | No | Claude model to use for TOC generation |
| `OLLAMA_URL` | `http://localhost:11434` | No | Ollama server URL for local LLM fallback |
| `OLLAMA_MODEL` | `phi3:mini` | No | Ollama model for local LLM fallback |
| `VITE_API_URL` | `http://localhost:8000` | No (prod: yes) | Backend base URL — set at frontend build time |

---

## Key Design Decisions

### No `ON DELETE CASCADE`

SQLite foreign keys are not enforced by default — `PRAGMA foreign_keys = ON` must be issued per connection, and the application does not do this. As a result:

- Deleting an idea does **not** remove its `relations` rows
- Deleting a tag does **not** remove its `relations` rows

This is a known quirk, deliberately pinned by integration tests. It means you may have orphan rows in the `relations` table.

### Asynchronous ChromaDB writes

Idea mutations (create, update, delete) write to SQLite synchronously, then submit a ChromaDB write to a `ThreadPoolExecutor` pool. This keeps API response times low at the cost of a brief window where SQLite and ChromaDB are slightly out of sync.

### JWT decoded client-side for UI only

The frontend reads `is_admin` from the JWT payload to show/hide the Admin link in the navbar. This does **not** bypass server-side authorisation — every admin endpoint calls `require_admin()` which re-reads `is_admin` from the database.

### Single Gunicorn worker

The systemd service uses `-w 1` (one worker). This is intentional: ChromaDB and SQLite do not handle concurrent writes gracefully in the current setup. Do not increase the worker count without adding proper locking.

### TOC caching

`GET /toc/structure` serves from a JSON cache (`data/toc.json`). The cache is only invalidated when `POST /toc/update` is called explicitly. This avoids re-running the expensive ML pipeline on every page load. The known side effect is that stale TOC structures are served after adding new ideas — users must manually trigger an update.

### `hashed_password` stores the TOTP secret

The `users.hashed_password` column stores the raw base32 TOTP secret. The misleading name is a historical artefact from an earlier design. It is not a hash.
