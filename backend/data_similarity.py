import re
import os
import json
import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Any, Protocol

import umap
import hdbscan
from sklearn.preprocessing import MinMaxScaler
from sklearn.feature_extraction.text import TfidfVectorizer

from chroma_client import ChromaClient
from utils import unformat_text

logger = logging.getLogger("uvicorn.error")


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

@dataclass
class IdeaData:
    """Raw ideas fetched from the vector store, kept together for cohesion."""
    documents: list[str]
    ids: list[str]
    embeddings: list[list[float]]


@dataclass
class ClusteringResult:
    """
    Unified output of EmbeddingAnalyzer.

    Both fields are derived from the same UMAP-reduced space, ensuring full
    consistency between cluster membership and originality scores.

    Attributes:
        labels:        Integer cluster label per idea.
                       -1 means HDBSCAN classified the point as noise
                       (i.e. the idea is genuinely isolated → leaf node).
        originalities: Normalised outlier score in [0, 1] per idea.
                       Higher = more original / atypical.
    """
    labels: np.ndarray         # shape (N,)
    originalities: np.ndarray  # shape (N,)


@dataclass
class TocEntry:
    """
    Single node in the table-of-contents tree.

      type == "idea"    → leaf node representing one idea
      type == "heading" → internal node grouping a cluster of ideas
    """
    title: str
    type: str                         # "idea" | "heading"
    originality: str                  # human-readable percentage, e.g. "73%"
    id: str | None = None             # leaf only
    text: str | None = None           # leaf only
    level: int | None = None          # heading only
    children: list["TocEntry"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dict (used by the cache and the API)."""
        d: dict[str, Any] = {
            "title": self.title,
            "type": self.type,
            "originality": self.originality,
        }
        if self.id is not None:
            d["id"] = self.id
        if self.text is not None:
            d["text"] = self.text
        if self.level is not None:
            d["level"] = self.level
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        return d


# ---------------------------------------------------------------------------
# Protocols – Dependency Inversion boundaries
# ---------------------------------------------------------------------------

class IdeaRepository(Protocol):
    """Abstraction over the vector store; makes DataSimilarity unit-testable."""
    def get_all_ideas(self) -> dict[str, Any]: ...


class TocCachePort(Protocol):
    """Abstraction for persisting and loading the TOC structure."""
    def save(self, structure: list[dict]) -> None: ...
    def load(self) -> list[dict] | None: ...


# ---------------------------------------------------------------------------
# FileTocCache – Single Responsibility: JSON persistence
# ---------------------------------------------------------------------------

class FileTocCache:
    """
    Persist and restore the TOC structure as a JSON file.

    The path is resolved at construction time so that a missing environment
    variable raises immediately rather than failing silently at runtime.
    """

    def __init__(self, cache_path: str | None = None) -> None:
        self._path: str = cache_path or os.getenv("TOC_CACHE_PATH", "")
        if not self._path:
            raise ValueError(
                "TOC_CACHE_PATH environment variable is not set. "
                "Pass cache_path explicitly or export the variable."
            )

    def save(self, structure: list[dict]) -> None:
        try:
            with open(self._path, "w") as f:
                json.dump(structure, f)
            logger.debug("TOC structure saved to %s", self._path)
        except OSError as exc:
            logger.error("Error saving TOC structure: %s", exc)

    def load(self) -> list[dict] | None:
        try:
            if os.path.exists(self._path):
                with open(self._path, "r") as f:
                    return json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Error loading TOC structure: %s", exc)
        return None


# ---------------------------------------------------------------------------
# EmbeddingAnalyzer – Single Responsibility: clustering + originality in one pass
# ---------------------------------------------------------------------------

class EmbeddingAnalyzer:
    """
    Reduce embeddings with UMAP then run HDBSCAN once to obtain both
    cluster labels and originality scores.

    Why HDBSCAN replaces the previous AgglomerativeClustering + LOF pair:

    1. Consistency
       Both outputs (labels, outlier_scores_) come from the same density model
       fitted in the same UMAP-reduced space.
       Previously, originality was computed in 10-D UMAP space while clustering
       ran on raw ~768-D embeddings — a spatial mismatch that could make a
       point appear "original" yet land inside a dense cluster.

    2. Single pass
       HDBSCAN.outlier_scores_ is a by-product of fit(); no second model (LOF)
       is needed, halving the compute cost.

    3. Adaptive clusters
       HDBSCAN discovers the natural groupings in the data without a fixed
       n_clusters parameter. AgglomerativeClustering with n_clusters=sqrt(N)
       forced equal-size splits that ignored density variations.

    4. Noise handling
       Points labelled -1 are genuinely isolated ideas; they become singleton
       leaf nodes rather than being forced into the nearest cluster.

    Trade-offs:
    - min_cluster_size must be tuned (default 3 works for prose-length ideas).
    - On very small datasets (< 2 * min_cluster_size) the method falls back to
      treating every point as its own cluster with full originality.
    """

    _UMAP_NEIGHBORS: int = 15
    _UMAP_COMPONENTS: int = 10
    _RANDOM_STATE: int = 42

    def __init__(self, min_cluster_size: int = 3) -> None:
        self._min_cluster_size = min_cluster_size

    def analyze(self, embeddings: list[list[float]]) -> ClusteringResult:
        """
        Run the full UMAP → HDBSCAN pipeline.

        Args:
            embeddings: Raw embedding vectors of shape (N, D).

        Returns:
            ClusteringResult with consistent labels and originality scores.
        """
        X = np.array(embeddings, dtype="float32")
        n = len(X)

        if n < self._min_cluster_size * 2:
            logger.debug(
                "EmbeddingAnalyzer: only %d points – skipping clustering", n
            )
            return ClusteringResult(
                labels=np.arange(n, dtype=int),
                originalities=np.ones(n, dtype="float32"),
            )

        logger.debug("EmbeddingAnalyzer: reducing %d embeddings with UMAP", n)
        reduced = umap.UMAP(
            n_neighbors=self._UMAP_NEIGHBORS,
            n_components=self._UMAP_COMPONENTS,
            metric="cosine",
            low_memory=True,
            random_state=self._RANDOM_STATE,
        ).fit_transform(X)

        logger.debug("EmbeddingAnalyzer: fitting HDBSCAN")
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self._min_cluster_size,
            metric="euclidean",    # UMAP output is Euclidean-friendly
            prediction_data=True,  # enables soft membership if needed later
        )
        clusterer.fit(reduced)

        # outlier_scores_:  0   = dense core member  → low originality
        #                  high = peripheral / isolated → high originality
        originalities: np.ndarray = MinMaxScaler().fit_transform(
            clusterer.outlier_scores_.reshape(-1, 1)
        ).flatten()

        n_clusters = len(set(clusterer.labels_)) - (1 if -1 in clusterer.labels_ else 0)
        n_noise = int((clusterer.labels_ == -1).sum())
        logger.debug(
            "EmbeddingAnalyzer: %d clusters, %d noise points", n_clusters, n_noise
        )

        return ClusteringResult(
            labels=clusterer.labels_,
            originalities=originalities,
        )


# ---------------------------------------------------------------------------
# TitleGenerator – Single Responsibility: representative cluster title
# ---------------------------------------------------------------------------

class TitleGenerator:
    """
    Produce a short descriptive title for a cluster of documents.

    Strategy:
    - Fit a TF-IDF vectorizer on all documents in the cluster.
    - Score terms by their *mean* TF-IDF weight across documents
      (mean rather than sum makes the score cluster-size independent).
    - Greedily select up to _TITLE_TERMS non-redundant key concepts.
    - sublinear_tf=True dampens the dominance of very frequent tokens.
    """

    _MAX_FEATURES: int = 40
    _TITLE_TERMS: int = 3
    _PUNCTUATION_RE = re.compile(r"[^\w\s]")

    def generate(self, cluster_docs: list[str]) -> str:
        """
        Args:
            cluster_docs: Raw text of each idea in the cluster.

        Returns:
            A short capitalised title string (e.g. "Machine Learning & Hardware").
        """
        if not cluster_docs:
            return "New Section"
        if len(cluster_docs) == 1:
            return cluster_docs[0][:40].capitalize()

        clean = [self._PUNCTUATION_RE.sub(" ", d.lower()) for d in cluster_docs]

        try:
            vectorizer = TfidfVectorizer(
                stop_words="english",
                ngram_range=(1, 2),
                max_features=self._MAX_FEATURES,
                sublinear_tf=True,
            )
            tfidf_matrix = vectorizer.fit_transform(clean)
            terms = vectorizer.get_feature_names_out()
            mean_scores = np.asarray(tfidf_matrix.mean(axis=0)).flatten()

            ranked_terms = terms[np.argsort(mean_scores)[::-1]]
            selected = self._pick_non_redundant_terms(ranked_terms)
            title = " & ".join(t.capitalize() for t in selected)
            logger.debug("TitleGenerator: '%s'", title)
            return title if len(title) > 2 else f"Ideas: {cluster_docs[0][:20]}"

        except Exception as exc:
            logger.warning("TitleGenerator fallback (%s): %s", type(exc).__name__, exc)
            return f"Section: {cluster_docs[0][:30]}…"

    def _pick_non_redundant_terms(self, sorted_terms: np.ndarray) -> list[str]:
        """Greedy selection: skip any term whose words overlap an already-selected term."""
        selected: list[str] = []
        for term in sorted_terms:
            if len(selected) >= self._TITLE_TERMS:
                break
            words = set(term.split())
            if any(words & set(s.split()) for s in selected):
                continue
            selected.append(term)
        return selected


# ---------------------------------------------------------------------------
# TocTreeBuilder – Single Responsibility: recursive tree assembly
# ---------------------------------------------------------------------------

class TocTreeBuilder:
    """
    Recursively build a hierarchical TocEntry tree from a flat list of ideas.

    At each recursion level EmbeddingAnalyzer is called on the current subset
    of embeddings, so labels and originalities are always consistent within
    each sub-tree.

    Recursion stops when:
    - The subset is too small (<= _MIN_LEAF_SIZE), OR
    - The maximum depth has been reached, OR
    - HDBSCAN produced only one real cluster (no meaningful split).
    """

    _MIN_LEAF_SIZE: int = 3
    _DEFAULT_MAX_DEPTH: int = 3

    def __init__(
        self,
        analyzer: EmbeddingAnalyzer,
        title_generator: TitleGenerator,
    ) -> None:
        self._analyzer = analyzer
        self._titler = title_generator

    # ------------------------------------------------------------------
    # Public entry-point
    # ------------------------------------------------------------------

    def build(
        self,
        data: IdeaData,
        max_depth: int = _DEFAULT_MAX_DEPTH,
    ) -> list[TocEntry]:
        """
        Build the full TOC tree.

        Args:
            data:      Ideas to organise (documents, ids, embeddings).
            max_depth: Maximum nesting depth of the output tree.

        Returns:
            Top-level list of TocEntry nodes.
        """
        return self._recurse(
            docs=data.documents,
            ids=data.ids,
            embeddings=data.embeddings,
            level=1,
            max_depth=max_depth,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _recurse(
        self,
        docs: list[str],
        ids: list[str],
        embeddings: list[list[float]],
        level: int,
        max_depth: int,
    ) -> list[TocEntry]:
        n = len(docs)

        # Base case: too few ideas or depth limit reached → emit leaf nodes.
        if n <= self._MIN_LEAF_SIZE or level > max_depth:
            result = self._analyzer.analyze(embeddings)
            return self._make_leaves(docs, ids, result.originalities)

        result = self._analyzer.analyze(embeddings)
        real_clusters = np.unique(result.labels[result.labels != -1])

        # Single cluster or all noise → no split is useful, emit leaves.
        if len(real_clusters) <= 1:
            return self._make_leaves(docs, ids, result.originalities)

        entries: list[TocEntry] = []

        # Noise points (label == -1) are truly isolated ideas → direct leaves.
        noise_idx = np.where(result.labels == -1)[0]
        for i in noise_idx:
            entries.append(TocEntry(
                title=ids[i],
                text=unformat_text(ids[i], docs[i], []),
                type="idea",
                id=ids[i],
                originality=self._fmt_pct(float(result.originalities[i])),
            ))

        # Recurse into each real cluster.
        for label in real_clusters:
            idx = np.where(result.labels == label)[0]
            sub_docs = [docs[i] for i in idx]
            sub_ids = [ids[i] for i in idx]
            sub_emb = [embeddings[i] for i in idx]
            sub_orig = result.originalities[idx]

            children = self._recurse(sub_docs, sub_ids, sub_emb, level + 1, max_depth)
            entries.append(TocEntry(
                title=self._titler.generate(sub_docs),
                type="heading",
                level=level,
                originality=self._fmt_pct(float(sub_orig.mean())),
                children=children,
            ))

        return entries

    @staticmethod
    def _make_leaves(
        docs: list[str],
        ids: list[str],
        originalities: np.ndarray,
    ) -> list[TocEntry]:
        return [
            TocEntry(
                title=id_,
                text=unformat_text(id_, doc, []),
                type="idea",
                id=id_,
                originality=TocTreeBuilder._fmt_pct(float(orig)),
            )
            for doc, id_, orig in zip(docs, ids, originalities, strict=False)
        ]

    @staticmethod
    def _fmt_pct(value: float) -> str:
        return f"{int(value * 100)}%"


# ---------------------------------------------------------------------------
# DataSimilarity – Public façade / orchestrator
# ---------------------------------------------------------------------------

class DataSimilarity:
    """
    Orchestrate the full pipeline: fetch → analyse → build tree → cache.

    All collaborators are injected via __init__, making every component
    independently testable and replaceable (Open/Closed + Dependency Inversion).

    Default wiring uses the concrete implementations; pass custom objects in tests.
    """

    def __init__(
        self,
        repository: IdeaRepository | None = None,
        cache: TocCachePort | None = None,
        analyzer: EmbeddingAnalyzer | None = None,
        title_generator: TitleGenerator | None = None,
        tree_builder: TocTreeBuilder | None = None,
    ) -> None:
        _analyzer = analyzer or EmbeddingAnalyzer()
        _titler = title_generator or TitleGenerator()

        self._repo: IdeaRepository = repository or ChromaClient()
        self._cache: TocCachePort = cache or FileTocCache()
        self._tree_builder: TocTreeBuilder = (
            tree_builder or TocTreeBuilder(_analyzer, _titler)
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_toc_structure(self) -> list[dict]:
        """
        Build the full hierarchical TOC, persist it to cache, and return it.

        Returns:
            JSON-serialisable list-of-dicts representing the idea tree.
        """
        raw = self._repo.get_all_ideas()
        data = IdeaData(
            documents=raw["documents"],
            ids=raw["ids"],
            embeddings=raw["embeddings"],
        )

        logger.debug("Building TOC tree for %d ideas…", len(data.ids))
        tree = self._tree_builder.build(data)

        result = [entry.to_dict() for entry in tree]
        self._cache.save(result)
        return result

    def load_toc_structure(self) -> list[dict] | None:
        """
        Return a previously cached TOC structure if one exists.

        Returns:
            Cached structure, or None if no valid cache exists.
        """
        return self._cache.load()
