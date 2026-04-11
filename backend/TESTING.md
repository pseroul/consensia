# Testing Guide for Brainiac5 Backend

## Overview

The backend has two test layers with different purposes:

| Layer | Location | Framework | What it tests |
|---|---|---|---|
| Unit | `tests/` | pytest + unittest.mock | Individual functions in isolation |
| Integration | `tests/integration/` | pytest + real SQLite | Full HTTP request → DB → response cycle |

Both layers enforce an **80% coverage threshold** and run together with `pytest`.

---

## Running Tests

```bash
cd backend && source venv/bin/activate

pytest                                # all tests (unit + integration)
pytest tests/                         # all tests explicitly
pytest tests/integration/            # integration tests only
pytest tests/test_main.py            # single unit test file
pytest -k "test_health"              # by keyword
pytest --cov=. --cov-report=html     # coverage with HTML report
make audit                           # ruff + vulture + pytest (CI gate)
```

---

## Test Structure

```
backend/
├── tests/
│   ├── __init__.py
│   ├── test_main.py              # API endpoint unit tests (mocked DB + ML)
│   ├── test_data_handler.py      # SQLite CRUD unit tests
│   ├── test_data_similarity.py   # ML pipeline unit tests
│   ├── test_authenticator.py     # TOTP + JWT unit tests
│   ├── test_chroma_client.py     # ChromaDB wrapper unit tests
│   ├── test_admin.py             # admin endpoint unit tests
│   ├── test_utils.py             # text format/unformat unit tests
│   └── integration/
│       ├── __init__.py
│       ├── conftest.py           # fixtures: real SQLite, FakeChromaClient, JWT helpers
│       ├── test_auth.py          # OTP → JWT → protected endpoint chain
│       ├── test_idea_lifecycle.py# full CRUD: create/read/update/delete + Chroma sync
│       ├── test_tag_cascades.py  # tag management, relation operations, filter by tag
│       ├── test_multi_user.py    # per-user idea isolation
│       ├── test_toc_pipeline.py  # TOC cache load/generate/invalidate
│       ├── test_books.py         # book CRUD + author management
│       ├── test_voting.py        # vote/unvote lifecycle
│       └── test_impact_comments.py # impact comment lifecycle and access control
```

---

## Unit Tests

Unit tests live in `tests/` alongside the source files they cover. Heavy ML
dependencies (chromadb, sentence-transformers, umap, hdbscan) are mocked at
`sys.modules` level at the top of each file that needs them so the import chain
does not fail and tests stay fast.

```python
# Pattern used in test_main.py, test_data_handler.py, test_chroma_client.py
import sys
from unittest import mock as _mock

_ml_modules = ["chromadb", "chromadb.utils", "sentence_transformers", ...]
for _mod in _ml_modules:
    if _mod not in sys.modules:
        sys.modules[_mod] = _mock.MagicMock()
```

**Important:** `test_data_similarity.py::TestEmbeddingAnalyzer` does NOT mock
umap or hdbscan — it exercises the real UMAP → HDBSCAN pipeline with small
synthetic embeddings. Do not add sys.modules patches that would affect it.

---

## Integration Tests

Integration tests live in `tests/integration/` and use **real infrastructure**:

- **Real SQLite** — a fresh temp database per test (`tmp_path` fixture)
- **Real JWT** — tokens created and decoded with the app's own `create_access_token`
- **Real pyotp** — TOTP secrets generated and verified without any mocking
- **FakeChromaClient** — an in-memory dict that mirrors ChromaDB's interface

### Why FakeChromaClient instead of real ChromaDB?

The real `ChromaClient.__init__` downloads a sentence-transformer model on first
use. The fake is a stateful in-memory dict that makes `insert_idea`, `update_idea`,
`remove_idea`, and `get_similar_idea` consistent within a single test — exactly
matching persistent ChromaDB behaviour, without the download cost.

### conftest.py fixtures

| Fixture | Scope | Purpose |
|---|---|---|
| `chroma_store` | function | fresh `{}` dict per test |
| `patch_chroma` | function, autouse | replaces `data_handler.ChromaClient` and `data_similarity.ChromaClient` with `FakeChromaClient` |
| `db_path` | function | temp SQLite path; sets `NAME_DB` and `TOC_CACHE_PATH` env vars |
| `client` | function | `TestClient(app)` wired to the test DB |
| `alice` | function | test user with real TOTP secret + pre-built auth headers |
| `bob` | function | second test user for isolation tests |

Helper functions (importable in test files):

```python
from tests.integration.conftest import create_db_user, make_token, auth_headers
```

### Writing an integration test

```python
def test_create_idea_inserts_into_chroma(self, client, alice, chroma_store):
    client.post(
        "/ideas",
        json={"title": "My Idea", "content": "Content"},
        headers=alice["headers"],
    )
    assert "My Idea" in chroma_store

def test_valid_otp_returns_access_token(self, client, db_path):
    import pyotp
    from tests.integration.conftest import create_db_user
    email = "login@example.com"
    secret = create_db_user(db_path, email)
    code = pyotp.TOTP(secret).now()      # real TOTP, no mock

    response = client.post("/verify-otp", json={"email": email, "otp_code": code})
    assert response.status_code == 200
    assert "access_token" in response.json()
```

### DELETE endpoints need `client.request()`

The `DELETE /ideas/{id}` and `DELETE /relations` endpoints require a JSON request
body. `httpx.Client.delete()` does not accept `json=`; use the generic method:

```python
client.request("DELETE", f"/ideas/{id}", json={"title": "...", "content": "..."}, headers=headers)
client.request("DELETE", "/relations", json={"idea_id": id, "tag_name": "t"}, headers=headers)
```

### Known behaviours pinned by integration tests

These tests document the **current** behaviour. Update them if the refactor
intentionally changes the contract.

| Behaviour | Test | Notes |
|---|---|---|
| `DELETE /ideas/{id}` does NOT cascade relations | `test_delete_removes_relations_via_sqlite_cascade` | `PRAGMA foreign_keys = ON` not set |
| `DELETE /tags/{name}` does NOT cascade relations | `test_delete_tag_does_not_cascade_to_relations` | Same root cause |
| Non-existent user email → `{"id": -1}` (not 4xx) | `test_create_idea_for_nonexistent_user_returns_200_but_id_is_negative` | `add_idea` returns -1 on owner-not-found |
| Empty TOC list `[]` is falsy → re-generated every request | `test_toc_cache_is_not_used_when_content_is_empty_list` | `if toc:` in main.py |
| Non-book-author → HTTP 403 on POST impact comment | `test_non_book_author_gets_403` | Checked via `is_book_author()` before insert |
| Non-owner → HTTP 403 on PUT/DELETE impact comment | `test_non_owner_gets_403` / `test_non_owner_non_admin_gets_403` | `UPDATE/DELETE … WHERE user_id = ?` returns rowcount 0 |
| Admin can DELETE any impact comment | `test_admin_can_delete_any` | `is_admin` read from JWT payload, not from DB at request time |

---

## Coverage

The project requires **≥ 80%** total coverage (configured in `pyproject.toml`):

```toml
[tool.pytest.ini_options]
addopts = "--cov=. --cov-report=term-missing --cov-fail-under=80"
```

Running the full suite (`pytest tests/`) achieves ~97% coverage. Running only a
subset (e.g., `pytest tests/integration/`) will report below the threshold because
uncovered unit test files count against the total — this is expected.

---

## Quality Gate

Before committing, run the full audit:

```bash
make audit   # ruff check --fix + vulture + pytest
```

All three must pass. Vulture flags dead code; delete it rather than suppress it.
