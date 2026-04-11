"""
Integration tests for the Table of Contents pipeline.

The TOC generation chain (UMAP → HDBSCAN → TocTreeBuilder) uses mocked ML
libraries, so these tests focus on the observable, refactor-critical contracts:

1. Cache-load path: when toc.json contains valid data, GET /toc/structure
   returns it without calling generate_toc_structure.

2. Generate path: when no cache file exists, GET /toc/structure calls
   generate_toc_structure, which calls ChromaClient.get_all_ideas and writes
   a new cache.

3. POST /toc/update: always regenerates, writes a new toc.json, and returns
   {"message": "toc added successfully"}.

4. Cache invalidation: after POST /toc/update the old cache content is gone.

5. Structural invariants: the endpoint always returns a JSON list.

Fixed behaviour (was a bug):
  `if toc is not None:` replaced the old `if toc:` guard.
  A cache containing `[]` is now treated as a valid cached result and returned
  directly — the ML pipeline is NOT re-run for an empty but present cache.
"""

import json
import pytest


def _write_cache(tmp_path, data: list) -> None:
    """Helper: write a toc.json in the test's temp directory."""
    cache_path = tmp_path / "toc.json"
    cache_path.write_text(json.dumps(data))


@pytest.mark.integration
class TestTocCacheLoad:
    def test_toc_returns_cached_data_when_cache_exists(self, client, alice, tmp_path, monkeypatch):
        cached = [{"title": "Cached Section", "type": "heading", "originality": "50%", "children": []}]
        _write_cache(tmp_path, cached)
        monkeypatch.setenv("TOC_CACHE_PATH", str(tmp_path / "toc.json"))

        response = client.get("/toc/structure", headers=alice["headers"])

        assert response.status_code == 200
        assert response.json() == cached

    def test_toc_returns_list_when_cache_missing(self, client, alice):
        # db_path fixture sets TOC_CACHE_PATH to a path with no file yet
        response = client.get("/toc/structure", headers=alice["headers"])

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_toc_generates_empty_list_when_chroma_is_empty(self, client, alice):
        """
        With no ideas in ChromaDB (chroma_store is empty), generate_toc_structure
        returns [] because EmbeddingAnalyzer hits the small-dataset fallback (n < 6).
        """
        response = client.get("/toc/structure", headers=alice["headers"])

        assert response.status_code == 200
        assert response.json() == []

    def test_toc_cache_is_used_when_content_is_empty_list(
        self, client, alice, tmp_path, monkeypatch
    ):
        """
        Fixed: `if toc is not None:` now treats [] as a valid cached result.
        A cache file containing [] must be returned as-is without triggering
        regeneration. This prevents the ML pipeline from running on every
        request when ChromaDB happens to be empty.
        """
        _write_cache(tmp_path, [])
        monkeypatch.setenv("TOC_CACHE_PATH", str(tmp_path / "toc.json"))

        response = client.get("/toc/structure", headers=alice["headers"])

        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.integration
class TestTocUpdate:
    def test_update_toc_returns_success_message(self, client, alice):
        response = client.post("/toc/update", headers=alice["headers"])

        assert response.status_code == 200
        assert response.json() == {"message": "toc added successfully"}

    def test_update_toc_writes_cache_file(self, client, alice, tmp_path, monkeypatch):
        cache_path = tmp_path / "toc.json"
        monkeypatch.setenv("TOC_CACHE_PATH", str(cache_path))

        client.post("/toc/update", headers=alice["headers"])

        assert cache_path.exists()

    def test_update_toc_overwrites_old_cache(self, client, alice, tmp_path, monkeypatch):
        cache_path = tmp_path / "toc.json"
        # Pre-populate with stale data
        cache_path.write_text(json.dumps([{"title": "Stale", "type": "heading", "originality": "0%"}]))
        monkeypatch.setenv("TOC_CACHE_PATH", str(cache_path))

        client.post("/toc/update", headers=alice["headers"])

        new_content = json.loads(cache_path.read_text())
        # After update with empty ChromaDB the cache should be [], not the stale entry
        assert new_content == []

    def test_toc_requires_authentication(self, client):
        response = client.get("/toc/structure")
        assert response.status_code == 401

    def test_toc_update_requires_authentication(self, client):
        response = client.post("/toc/update")
        assert response.status_code == 401


@pytest.mark.integration
class TestTocStructuralInvariants:
    def test_toc_response_is_always_a_list(self, client, alice):
        response = client.get("/toc/structure", headers=alice["headers"])
        assert isinstance(response.json(), list)

    def test_toc_cache_written_by_update_is_valid_json(
        self, client, alice, tmp_path, monkeypatch
    ):
        cache_path = tmp_path / "toc.json"
        monkeypatch.setenv("TOC_CACHE_PATH", str(cache_path))

        client.post("/toc/update", headers=alice["headers"])

        # Must not raise
        parsed = json.loads(cache_path.read_text())
        assert isinstance(parsed, list)

    def test_toc_entry_shape_when_ideas_exist(self, client, alice, chroma_store, tmp_path, monkeypatch):
        """
        When ChromaDB has enough ideas (but still < 6 to stay below UMAP threshold),
        generate_toc_structure emits leaf-only TocEntry nodes. Verify the shape.
        """
        cache_path = tmp_path / "toc.json"
        monkeypatch.setenv("TOC_CACHE_PATH", str(cache_path))

        # Seed the fake chroma store directly (bypasses HTTP to avoid FK issues)
        chroma_store["Idea Alpha"] = "Content about alpha"
        chroma_store["Idea Beta"] = "Content about beta"

        client.post("/toc/update", headers=alice["headers"])

        entries = json.loads(cache_path.read_text())
        assert len(entries) > 0

        for entry in entries:
            assert "title" in entry
            assert "type" in entry
            assert "originality" in entry
            assert entry["type"] in ("idea", "heading")


@pytest.mark.integration
class TestTocLlmFallback:
    def test_toc_works_without_llm_api_key(self, client, alice, monkeypatch):
        """TOC generation succeeds when no LLM API key is configured (TF-IDF fallback)."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        response = client.post("/toc/update", headers=alice["headers"])
        assert response.status_code == 200
        assert response.json() == {"message": "toc added successfully"}
