import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import numpy as np

from backend.data_similarity import (
    IdeaData,
    ClusteringResult,
    TocEntry,
    FileTocCache,
    EmbeddingAnalyzer,
    ConstrainedClusteringAnalyzer,
    TitleGenerator,
    TocTreeBuilder,
    DataSimilarity,
    SectionOrderer,
)
from backend.llm_client import LlmUnavailableError


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

def _random_embeddings(n: int, dim: int = 8, seed: int = 0) -> list[list[float]]:
    """Return reproducible random unit-normalised embeddings."""
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n, dim)).astype("float32")
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    return (X / norms).tolist()


def _make_idea_data(n: int = 10, dim: int = 8) -> IdeaData:
    return IdeaData(
        documents=[f"This is idea number {i} about topic {i % 3}" for i in range(n)],
        ids=[f"id_{i}" for i in range(n)],
        embeddings=_random_embeddings(n, dim),
    )


class FakeCache:
    """In-memory TocCachePort stub."""
    def __init__(self) -> None:
        self._store: list[dict] | None = None

    def save(self, structure: list[dict]) -> None:
        self._store = structure

    def load(self) -> list[dict] | None:
        return self._store


class FakeRepository:
    """IdeaRepository stub that returns a fixed IdeaData."""
    def __init__(self, data: IdeaData) -> None:
        self._data = data

    def get_all_ideas(self) -> dict:
        return {
            "documents": self._data.documents,
            "ids": self._data.ids,
            "embeddings": self._data.embeddings,
        }


class FakeAnalyzer:
    """
    EmbeddingAnalyzer stub that returns deterministic results.
    Splits N items into two equal clusters (first half / second half)
    and assigns linearly increasing originality scores.
    """
    def analyze(self, embeddings: list[list[float]]) -> ClusteringResult:
        n = len(embeddings)
        labels = np.array([0 if i < n // 2 else 1 for i in range(n)], dtype=int)
        if n < 4:
            # Too small to split meaningfully → single cluster
            labels = np.zeros(n, dtype=int)
        originalities = np.linspace(0.1, 0.9, n, dtype="float32")
        return ClusteringResult(labels=labels, originalities=originalities)


# ---------------------------------------------------------------------------
# TocEntry
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTocEntry:
    def test_leaf_to_dict_contains_required_fields(self):
        entry = TocEntry(
            title="my_id", type="idea", originality="55%",
            id="my_id", text="formatted text",
        )
        d = entry.to_dict()
        assert d["type"] == "idea"
        assert d["id"] == "my_id"
        assert d["text"] == "formatted text"
        assert "level" not in d
        assert "children" not in d

    def test_heading_to_dict_contains_children(self):
        child = TocEntry(title="c", type="idea", originality="10%", id="c")
        heading = TocEntry(
            title="Section", type="heading", originality="40%",
            level=1, children=[child],
        )
        d = heading.to_dict()
        assert d["level"] == 1
        assert len(d["children"]) == 1
        assert "id" not in d

    def test_empty_children_list_not_serialised(self):
        entry = TocEntry(title="h", type="heading", originality="0%", level=1)
        d = entry.to_dict()
        assert "children" not in d


# ---------------------------------------------------------------------------
# FileTocCache
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFileTocCache:
    def test_raises_when_no_path_configured(self, monkeypatch):
        monkeypatch.delenv("TOC_CACHE_PATH", raising=False)
        with pytest.raises(ValueError, match="TOC_CACHE_PATH"):
            FileTocCache()

    def test_save_and_load_roundtrip(self, tmp_path):
        path = str(tmp_path / "toc.json")
        cache = FileTocCache(cache_path=path)
        structure = [{"title": "A", "type": "heading", "originality": "50%"}]
        cache.save(structure)
        loaded = cache.load()
        assert loaded == structure

    def test_load_returns_none_when_file_missing(self, tmp_path):
        cache = FileTocCache(cache_path=str(tmp_path / "missing.json"))
        assert cache.load() is None

    def test_load_returns_none_on_corrupt_json(self, tmp_path):
        path = tmp_path / "corrupt.json"
        path.write_text("{ not valid json }")
        cache = FileTocCache(cache_path=str(path))
        assert cache.load() is None


# ---------------------------------------------------------------------------
# EmbeddingAnalyzer
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestEmbeddingAnalyzer:
    def test_small_dataset_fallback(self):
        """Fewer than 2*min_cluster_size points → all originalities == 1."""
        analyzer = EmbeddingAnalyzer(min_cluster_size=3)
        result = analyzer.analyze(_random_embeddings(4))
        assert len(result.labels) == 4
        assert len(result.originalities) == 4
        np.testing.assert_array_equal(result.originalities, np.ones(4))

    def test_output_shapes_match_input(self):
        analyzer = EmbeddingAnalyzer(min_cluster_size=3)
        n = 20
        result = analyzer.analyze(_random_embeddings(n, dim=16))
        assert result.labels.shape == (n,)
        assert result.originalities.shape == (n,)

    def test_originalities_in_unit_range(self):
        analyzer = EmbeddingAnalyzer(min_cluster_size=3)
        result = analyzer.analyze(_random_embeddings(20, dim=16))
        assert result.originalities.min() >= 0.0
        assert result.originalities.max() <= 1.0

    def test_labels_contain_integers(self):
        analyzer = EmbeddingAnalyzer(min_cluster_size=3)
        result = analyzer.analyze(_random_embeddings(20, dim=16))
        assert result.labels.dtype.kind == "i"

    def test_intermediate_dataset_does_not_raise(self):
        """n between min_cluster_size*2 (6) and UMAP n_neighbors (15) must not raise.

        Previously n_neighbors=15 was passed to UMAP with fewer than 15 samples,
        causing a ValueError that propagated as a 500 on POST /toc/update.
        """
        analyzer = EmbeddingAnalyzer(min_cluster_size=3)
        for n in (6, 8, 10, 14, 15):
            result = analyzer.analyze(_random_embeddings(n, dim=16))
            assert result.labels.shape == (n,), f"labels shape mismatch for n={n}"
            assert result.originalities.shape == (n,), f"originalities shape mismatch for n={n}"

    def test_intermediate_dataset_originalities_in_unit_range(self):
        """Originalities for intermediate-sized datasets stay within [0, 1]."""
        analyzer = EmbeddingAnalyzer(min_cluster_size=3)
        result = analyzer.analyze(_random_embeddings(10, dim=16))
        assert result.originalities.min() >= 0.0
        assert result.originalities.max() <= 1.0


# ---------------------------------------------------------------------------
# ConstrainedClusteringAnalyzer
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestConstrainedClusteringAnalyzer:
    def test_small_dataset_fallback(self):
        """Fewer than 4 points → labels=arange(n), originalities all 1."""
        analyzer = ConstrainedClusteringAnalyzer()
        result = analyzer.analyze(_random_embeddings(3))
        assert len(result.labels) == 3
        np.testing.assert_array_equal(result.originalities, np.ones(3))

    def test_no_noise_labels(self):
        """AgglomerativeClustering must never produce -1 labels."""
        analyzer = ConstrainedClusteringAnalyzer(min_clusters=2, max_clusters=5)
        result = analyzer.analyze(_random_embeddings(20, dim=16))
        assert -1 not in result.labels

    def test_output_shapes_match_input(self):
        analyzer = ConstrainedClusteringAnalyzer(min_clusters=2, max_clusters=5)
        n = 20
        result = analyzer.analyze(_random_embeddings(n, dim=16))
        assert result.labels.shape == (n,)
        assert result.originalities.shape == (n,)

    def test_originalities_in_unit_range(self):
        analyzer = ConstrainedClusteringAnalyzer(min_clusters=2, max_clusters=5)
        result = analyzer.analyze(_random_embeddings(20, dim=16))
        assert result.originalities.min() >= 0.0
        assert result.originalities.max() <= 1.0

    def test_labels_contain_integers(self):
        analyzer = ConstrainedClusteringAnalyzer(min_clusters=2, max_clusters=5)
        result = analyzer.analyze(_random_embeddings(20, dim=16))
        assert result.labels.dtype.kind == "i"

    def test_intermediate_dataset_does_not_raise(self):
        """Sizes between fallback threshold and UMAP n_neighbors must not raise."""
        analyzer = ConstrainedClusteringAnalyzer(min_clusters=2, max_clusters=4)
        for n in (4, 6, 8, 10, 14, 15):
            result = analyzer.analyze(_random_embeddings(n, dim=16))
            assert result.labels.shape == (n,), f"labels shape mismatch for n={n}"
            assert result.originalities.shape == (n,), f"originalities shape mismatch for n={n}"

    def test_cluster_count_bounded_by_min_max(self):
        """Number of clusters should respect min_clusters / max_clusters when data allows."""
        analyzer = ConstrainedClusteringAnalyzer(min_clusters=2, max_clusters=4)
        result = analyzer.analyze(_random_embeddings(30, dim=16, seed=7))
        n_clusters = len(np.unique(result.labels))
        assert 1 <= n_clusters <= 4


# ---------------------------------------------------------------------------
# TitleGenerator
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTitleGenerator:
    def test_empty_docs_returns_default(self):
        assert TitleGenerator().generate([]) == "New Section"

    def test_single_doc_truncated(self):
        title = TitleGenerator().generate(["A short idea"])
        assert len(title) <= 41  # 40 chars + possible truncation marker

    def test_multi_doc_returns_non_empty_string(self):
        docs = [
            "machine learning algorithms for image recognition",
            "deep learning neural networks and computer vision",
            "convolutional networks in image classification tasks",
        ]
        title = TitleGenerator().generate(docs)
        assert isinstance(title, str)
        assert len(title) > 0

    def test_title_is_capitalised(self):
        docs = ["alpha beta", "alpha gamma", "alpha delta"]
        title = TitleGenerator().generate(docs)
        # Every term should start with a capital letter
        for word in title.split(" & "):
            assert word[0].isupper(), f"'{word}' not capitalised in '{title}'"

    def test_no_redundant_terms(self):
        """Terms sharing a word should not both appear in the title."""
        docs = ["hardware recommendation for pc", "hardware spec", "hardware build guide"]
        title = TitleGenerator().generate(docs)
        words_seen: set[str] = set()
        for part in title.split(" & "):
            for word in part.lower().split():
                assert word not in words_seen, f"Redundant word '{word}' in '{title}'"
                words_seen.add(word)


# ---------------------------------------------------------------------------
# TocTreeBuilder
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTocTreeBuilder:
    def _make_builder(self) -> TocTreeBuilder:
        return TocTreeBuilder(FakeAnalyzer(), TitleGenerator())

    def test_small_dataset_returns_leaves(self):
        """3 items < _MIN_LEAF_SIZE=3+1 → all leaves at top level."""
        builder = self._make_builder()
        data = _make_idea_data(n=3)
        entries = builder.build(data, max_depth=3)
        assert all(e.type == "idea" for e in entries)

    def test_larger_dataset_creates_headings(self):
        """With FakeAnalyzer, 10 items split into 2 clusters → headings."""
        builder = self._make_builder()
        data = _make_idea_data(n=10)
        entries = builder.build(data, max_depth=2)
        types = {e.type for e in entries}
        assert "heading" in types

    def test_originality_is_percentage_string(self):
        builder = self._make_builder()
        data = _make_idea_data(n=6)
        entries = builder.build(data)

        def check(nodes):
            for node in nodes:
                assert node.originality.endswith("%"), (
                    f"Expected '%' suffix, got '{node.originality}'"
                )
                check(node.children)

        check(entries)

    def test_max_depth_respected(self):
        """Headings should not exceed max_depth nesting."""
        builder = self._make_builder()
        data = _make_idea_data(n=20)
        max_depth = 2

        def max_heading_level(nodes: list[TocEntry]) -> int:
            levels = [0]
            for node in nodes:
                if node.level is not None:
                    levels.append(node.level)
                levels.append(max_heading_level(node.children))
            return max(levels)

        entries = builder.build(data, max_depth=max_depth)
        assert max_heading_level(entries) <= max_depth

    def test_all_ids_present_in_tree(self):
        """No idea should be lost or duplicated during tree construction."""
        builder = self._make_builder()
        data = _make_idea_data(n=10)
        entries = builder.build(data)

        def collect_ids(nodes: list[TocEntry]) -> list[str]:
            result = []
            for node in nodes:
                if node.id is not None:
                    result.append(node.id)
                result.extend(collect_ids(node.children))
            return result

        found_ids = collect_ids(entries)
        assert sorted(found_ids) == sorted(data.ids)


# ---------------------------------------------------------------------------
# DataSimilarity (integration-level with stubs)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDataSimilarity:
    def _make_ds(self, n: int = 10) -> tuple[DataSimilarity, FakeCache, FakeRepository]:
        data = _make_idea_data(n)
        cache = FakeCache()
        repo = FakeRepository(data)
        analyzer = FakeAnalyzer()
        builder = TocTreeBuilder(analyzer, TitleGenerator())
        ds = DataSimilarity(
            repository=repo,
            cache=cache,
            tree_builder=builder,
        )
        return ds, cache, repo

    def test_generate_returns_list_of_dicts(self):
        ds, _, _ = self._make_ds()
        result = ds.generate_toc_structure()
        assert isinstance(result, list)
        assert all(isinstance(item, dict) for item in result)

    def test_result_is_persisted_in_cache(self):
        ds, cache, _ = self._make_ds()
        result = ds.generate_toc_structure()
        assert cache.load() == result

    def test_load_toc_structure_returns_cached_value(self):
        ds, cache, _ = self._make_ds()
        ds.generate_toc_structure()
        loaded = ds.load_toc_structure()
        assert loaded is not None
        assert isinstance(loaded, list)

    def test_load_returns_none_before_generate(self):
        ds, cache, _ = self._make_ds()
        assert ds.load_toc_structure() is None

    def test_result_contains_required_keys(self):
        ds, _, _ = self._make_ds()
        result = ds.generate_toc_structure()

        def check_keys(nodes: list[dict]) -> None:
            for node in nodes:
                assert "title" in node
                assert "type" in node
                assert "originality" in node
                check_keys(node.get("children", []))

        check_keys(result)


# ---------------------------------------------------------------------------
# FakeLlm – test double for LlmPort
# ---------------------------------------------------------------------------

class FakeLlm:
    """LlmPort stub that returns deterministic titles and ordering."""

    def __init__(self, titles: list[str] | None = None, order: list[int] | None = None):
        self._titles = titles
        self._order = order
        self.generate_calls: list = []
        self.order_calls: list = []

    def generate_titles(self, sections):
        self.generate_calls.append(sections)
        if self._titles is not None:
            return self._titles[: len(sections)]
        return [f"LLM Title {i}" for i in range(len(sections))]

    def order_sections(self, summaries):
        self.order_calls.append(summaries)
        if self._order is not None:
            return self._order
        return list(reversed(range(len(summaries))))


class FailingLlm:
    """LlmPort stub that always raises LlmUnavailableError."""

    def generate_titles(self, sections):
        raise LlmUnavailableError("test failure")

    def order_sections(self, summaries):
        raise LlmUnavailableError("test failure")


# ---------------------------------------------------------------------------
# SectionOrderer
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSectionOrderer:
    def test_no_llm_returns_original_order(self):
        orderer = SectionOrderer(llm=None)
        entries = [
            TocEntry(title="A", type="heading", originality="50%", level=1),
            TocEntry(title="B", type="heading", originality="50%", level=1),
            TocEntry(title="C", type="heading", originality="50%", level=1),
        ]
        result = orderer.order(entries)
        assert [e.title for e in result] == ["A", "B", "C"]

    def test_llm_reorders_sections(self):
        llm = FakeLlm(order=[2, 0, 1])
        orderer = SectionOrderer(llm=llm)
        entries = [
            TocEntry(title="A", type="heading", originality="50%", level=1),
            TocEntry(title="B", type="heading", originality="50%", level=1),
            TocEntry(title="C", type="heading", originality="50%", level=1),
        ]
        result = orderer.order(entries)
        assert [e.title for e in result] == ["C", "A", "B"]

    def test_single_section_skips_llm(self):
        llm = FakeLlm()
        orderer = SectionOrderer(llm=llm)
        entries = [
            TocEntry(title="A", type="heading", originality="50%", level=1),
        ]
        result = orderer.order(entries)
        assert len(llm.order_calls) == 0
        assert [e.title for e in result] == ["A"]

    def test_llm_failure_returns_original_order(self):
        orderer = SectionOrderer(llm=FailingLlm())
        entries = [
            TocEntry(title="A", type="heading", originality="50%", level=1),
            TocEntry(title="B", type="heading", originality="50%", level=1),
            TocEntry(title="C", type="heading", originality="50%", level=1),
        ]
        result = orderer.order(entries)
        assert [e.title for e in result] == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# TocTreeBuilder with LLM
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTocTreeBuilderWithLlm:
    def test_llm_titles_used_when_available(self):
        llm = FakeLlm(titles=["Chapter Alpha", "Chapter Beta"])
        builder = TocTreeBuilder(FakeAnalyzer(), TitleGenerator(), llm=llm)
        data = _make_idea_data(n=10)
        entries = builder.build(data, max_depth=2)

        headings = [e for e in entries if e.type == "heading"]
        assert len(headings) == 2
        assert headings[0].title == "Chapter Alpha"
        assert headings[1].title == "Chapter Beta"

    def test_tfidf_fallback_when_llm_fails(self):
        builder = TocTreeBuilder(FakeAnalyzer(), TitleGenerator(), llm=FailingLlm())
        data = _make_idea_data(n=10)
        entries = builder.build(data, max_depth=2)

        headings = [e for e in entries if e.type == "heading"]
        assert len(headings) == 2
        # TF-IDF fallback should produce non-empty titles
        for h in headings:
            assert len(h.title) > 0

    def test_orderer_applied_after_build(self):
        llm = FakeLlm(order=[1, 0])
        orderer = SectionOrderer(llm=llm)
        builder = TocTreeBuilder(FakeAnalyzer(), TitleGenerator(), orderer=orderer)
        data = _make_idea_data(n=10)
        entries = builder.build(data, max_depth=2)

        headings = [e for e in entries if e.type == "heading"]
        # FakeAnalyzer splits 10 items into 2 clusters (0..4 and 5..9),
        # orderer reverses them.
        assert len(headings) == 2
        # The second cluster's heading should now be first
        first_child_ids = {c.id for c in headings[0].children}
        assert "id_5" in first_child_ids or "id_6" in first_child_ids

    def test_all_ids_present_with_llm(self):
        llm = FakeLlm()
        orderer = SectionOrderer(llm=llm)
        builder = TocTreeBuilder(FakeAnalyzer(), TitleGenerator(), llm=llm, orderer=orderer)
        data = _make_idea_data(n=10)
        entries = builder.build(data)

        def collect_ids(nodes):
            result = []
            for node in nodes:
                if node.id is not None:
                    result.append(node.id)
                result.extend(collect_ids(node.children))
            return result

        assert sorted(collect_ids(entries)) == sorted(data.ids)


# ---------------------------------------------------------------------------
# DataSimilarity with LLM
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDataSimilarityWithLlm:
    def _make_ds_with_llm(self, n: int = 10):
        data = _make_idea_data(n)
        cache = FakeCache()
        repo = FakeRepository(data)
        llm = FakeLlm()
        ds = DataSimilarity(
            repository=repo,
            cache=cache,
            analyzer=FakeAnalyzer(),
            llm=llm,
        )
        return ds, cache, llm

    def test_llm_wired_through_datasimilarity(self):
        ds, cache, llm = self._make_ds_with_llm()
        result = ds.generate_toc_structure()

        assert isinstance(result, list)
        # LLM should have been called for title generation
        assert len(llm.generate_calls) > 0

    def test_headings_use_llm_titles(self):
        ds, _, llm = self._make_ds_with_llm()
        result = ds.generate_toc_structure()

        headings = [n for n in result if n.get("type") == "heading"]
        for h in headings:
            assert h["title"].startswith("LLM Title")

    def test_no_llm_uses_tfidf(self):
        data = _make_idea_data(10)
        cache = FakeCache()
        repo = FakeRepository(data)
        ds = DataSimilarity(
            repository=repo,
            cache=cache,
            analyzer=FakeAnalyzer(),
            llm=None,
        )
        result = ds.generate_toc_structure()
        headings = [n for n in result if n.get("type") == "heading"]
        for h in headings:
            assert not h["title"].startswith("LLM Title")
