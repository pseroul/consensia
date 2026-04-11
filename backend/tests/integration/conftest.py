"""
Integration test configuration for Consensia backend.

Design goals:
- Real SQLite database (fresh temp file per test)
- Real JWT creation/validation (using the app's own create_access_token)
- Real pyotp TOTP verification (no mocking of verify_access)
- Fake ChromaClient (stateful in-memory; isolates tests from ML model downloads
  and the real ChromaDB/sentence-transformers initialisation overhead)

All ML libraries (umap, chromadb, sentence-transformers, hdbscan) ARE installed
in the venv and do NOT need sys.modules patching here.  Patching them at module
level corrupts the sys.modules state seen by EmbeddingAnalyzer unit tests in
test_data_similarity.py, which intentionally call real umap/hdbscan.

The patch_chroma fixture (autouse) is the only hook needed: it replaces
ChromaClient with an in-memory fake so no model download or disk I/O occurs.
The fake shares state via an injected dict so that insert/query/delete calls
within one test are mutually visible, exactly like a persistent ChromaDB
collection, while remaining fully isolated across tests.
"""

import sys
import os
import sqlite3
from datetime import timedelta

# ---------------------------------------------------------------------------
# sys.path: ensure bare imports like "from authenticator import ..." resolve
# ---------------------------------------------------------------------------
_integration_dir = os.path.dirname(__file__)
_tests_dir = os.path.join(_integration_dir, "..")
_backend_dir = os.path.join(_tests_dir, "..")
_repo_root = os.path.join(_backend_dir, "..")
sys.path.insert(0, os.path.abspath(_backend_dir))
sys.path.insert(0, os.path.abspath(_repo_root))

# ---------------------------------------------------------------------------
# Bootstrap env vars so main.py's module-level init_database() has a path.
# set_env_var() (called at import time in main.py) will override NAME_DB to
# the real data/ path; each test fixture then re-overrides it to a temp path.
# All data_handler functions read os.getenv('NAME_DB') at *call* time, so
# per-test overrides are fully effective.
# ---------------------------------------------------------------------------
import tempfile as _tempfile

_bootstrap_tmp = _tempfile.mkdtemp(prefix="consensia_bootstrap_")
os.environ.setdefault("NAME_DB", os.path.join(_bootstrap_tmp, "bootstrap.db"))
os.environ.setdefault("CHROMA_DB", os.path.join(_bootstrap_tmp, "chroma"))
os.environ.setdefault("TOC_CACHE_PATH", os.path.join(_bootstrap_tmp, "toc.json"))
# Ensure integration tests never call a real LLM API
os.environ.pop("ANTHROPIC_API_KEY", None)

# ---------------------------------------------------------------------------
# Now safe to import the app (no ML module mocking needed; the import chain
# only defines classes, it does not instantiate ChromaClient or load models)
# ---------------------------------------------------------------------------
import pytest
import pyotp
from fastapi.testclient import TestClient

from backend.main import app, create_access_token
from backend.data_handler import init_database


# ---------------------------------------------------------------------------
# FakeChromaClient
# ---------------------------------------------------------------------------

class FakeChromaClient:
    """
    In-memory stand-in for ChromaClient.

    Multiple instances share the same underlying dict so that insert in
    add_idea() is visible to subsequent get_similar_idea() calls within the
    same test – exactly mirroring the behaviour of a persistent ChromaDB
    collection.

    The `tags` parameter is accepted (but not stored) to absorb the interface
    mismatch where data_handler calls insert_idea/update_idea without tags.
    """

    def __init__(self, store: dict) -> None:
        self._store = store

    def insert_idea(self, title: str, content: str, tags=None) -> None:
        self._store[title] = content

    def update_idea(self, title: str, content: str, tags=None) -> None:
        self._store[title] = content

    def remove_idea(self, title: str) -> None:
        self._store.pop(title, None)

    def get_similar_idea(self, idea: str, n_results: int = 10) -> list[str]:
        """Return all stored titles (no semantic ranking needed for contract tests)."""
        return list(self._store.keys())[:n_results]

    def get_all_ideas(self, max_items: int = 500) -> dict:
        ids = list(self._store.keys())[:max_items]
        docs = [self._store[i] for i in ids]
        # Use 6-dimensional embeddings so UMAP's n_neighbors check never fires
        # (EmbeddingAnalyzer falls back to leaf-only when n < min_cluster_size*2=6)
        return {
            "documents": docs,
            "ids": ids,
            "embeddings": [[0.1 * (j + 1) for j in range(6)] for _ in ids],
        }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def chroma_store() -> dict:
    """Fresh in-memory store per test; shared across all FakeChromaClient instances."""
    return {}


@pytest.fixture(autouse=True)
def patch_chroma(chroma_store: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Replace ChromaClient with FakeChromaClient everywhere it is instantiated.
    autouse=True means every integration test gets this patch automatically.
    """
    store = chroma_store

    def _make_fake(*_args, **_kwargs):
        return FakeChromaClient(store)

    monkeypatch.setattr("data_handler.ChromaClient", _make_fake)
    monkeypatch.setattr("data_similarity.ChromaClient", _make_fake)


@pytest.fixture(autouse=True)
def patch_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure integration tests use the TF-IDF fallback, never a real LLM."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("llm_client._ollama_reachable", lambda _url: False)


@pytest.fixture()
def db_path(tmp_path, monkeypatch: pytest.MonkeyPatch) -> str:
    """
    Create a fresh SQLite database in a per-test temp directory.
    Overrides NAME_DB and TOC_CACHE_PATH so every data_handler call uses
    the test-local file, not the real data/ directory.
    """
    path = str(tmp_path / "test.db")
    toc_path = str(tmp_path / "toc.json")
    monkeypatch.setenv("NAME_DB", path)
    monkeypatch.setenv("TOC_CACHE_PATH", toc_path)
    init_database()
    return path


@pytest.fixture()
def client(db_path: str) -> TestClient:
    """FastAPI TestClient wired to the test database."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# User helpers
# ---------------------------------------------------------------------------

def create_db_user(db_path: str, email: str) -> str:
    """Insert a TOTP user and return the raw OTP secret."""
    secret = pyotp.random_base32()
    username = email.split("@")[0]
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)",
        (username, email, secret),
    )
    conn.commit()
    conn.close()
    return secret


def make_token(email: str, expires: timedelta = timedelta(minutes=30)) -> str:
    return create_access_token(data={"sub": email}, expires_delta=expires)


def auth_headers(email: str, expires: timedelta = timedelta(minutes=30)) -> dict:
    return {"Authorization": f"Bearer {make_token(email, expires)}"}


@pytest.fixture()
def book(client: TestClient, alice: dict) -> int:
    """Create a book and return its id. Requires alice to be authenticated."""
    response = client.post("/books", json={"title": "Test Book"}, headers=alice["headers"])
    assert response.status_code == 200
    return response.json()["id"]


@pytest.fixture()
def alice(db_path: str) -> dict:
    """
    User 'alice' with a real TOTP secret and pre-built auth headers.
    Returns a dict with keys: email, secret, headers.
    """
    email = "alice@example.com"
    secret = create_db_user(db_path, email)
    return {"email": email, "secret": secret, "headers": auth_headers(email)}


@pytest.fixture()
def bob(db_path: str) -> dict:
    email = "bob@example.com"
    secret = create_db_user(db_path, email)
    return {"email": email, "secret": secret, "headers": auth_headers(email)}
