import re
import os
import json
import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Any, Protocol

import umap
import hdbscan
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score
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
    Unified output of clustering analyzers.

    Both fields are derived from the same reduced space, ensuring full
    consistency between cluster membership and originality scores.

    Attributes:
        labels:        Integer cluster label per idea.
                       -1 means the point is classified as noise
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
# EmbeddingAnalyzer – UMAP + HDBSCAN (kept for backward compatibility)
# ---------------------------------------------------------------------------

class EmbeddingAnalyzer:
    """
    Reduce embeddings with UMAP then run HDBSCAN once to obtain both
    cluster labels and originality scores.

    Note: HDBSCAN produces noise points (label=-1) for ideas in low-density
    regions.  For a book-like TOC structure prefer ConstrainedClusteringAnalyzer
    which uses AgglomerativeClustering and guarantees no noise points.
    """

    _UMAP_NEIGHBORS: int = 15
    _UMAP_COMPONENTS: int = 10
    _RANDOM_STATE: int = 42

    def __init__(self, min_cluster_size: int = 3) -> None:
        self._min_cluster_size = min_cluster_size

    def analyze(self, embeddings: list[list[float]]) -> ClusteringResult:
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
        n_neighbors = max(2, min(self._UMAP_NEIGHBORS, n - 1))
        n_components = max(1, min(self._UMAP_COMPONENTS, n - 2))
        reduced = umap.UMAP(
            n_neighbors=n_neighbors,
            n_components=n_components,
            metric="cosine",
            low_memory=True,
            random_state=self._RANDOM_STATE,
        ).fit_transform(X)

        logger.debug("EmbeddingAnalyzer: fitting HDBSCAN")
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self._min_cluster_size,
            metric="euclidean",
            prediction_data=True,
        )
        clusterer.fit(reduced)

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
# ConstrainedClusteringAnalyzer – UMAP + AgglomerativeClustering
# ---------------------------------------------------------------------------

class ConstrainedClusteringAnalyzer:
    """
    Constrained clustering that produces structured, book-like TOC hierarchies.

    Unlike HDBSCAN, AgglomerativeClustering assigns every point to a cluster —
    there are no noise points.  This ensures the TOC has well-populated sections
    and chapters rather than a large number of isolated level-1 ideas.

    Algorithm:
    1. Reduce with UMAP (cosine metric, 5 components).
    2. Try each k in [min_clusters, max_clusters]; pick the k that maximises
       the silhouette score (Ward linkage ensures compact, convex clusters).
    3. Compute originality as the normalised Euclidean distance from each
       point's cluster centroid.

    Args:
        min_clusters: Minimum number of clusters to consider.
        max_clusters: Maximum number of clusters to consider.
    """

    _UMAP_NEIGHBORS: int = 15
    _UMAP_COMPONENTS: int = 5
    _RANDOM_STATE: int = 42
    _FALLBACK_THRESHOLD: int = 4  # points below this → skip clustering

    def __init__(self, min_clusters: int = 5, max_clusters: int = 10) -> None:
        self._min_clusters = min_clusters
        self._max_clusters = max_clusters

    def analyze(self, embeddings: list[list[float]]) -> ClusteringResult:
        X = np.array(embeddings, dtype="float32")
        n = len(X)

        if n < self._FALLBACK_THRESHOLD:
            logger.debug(
                "ConstrainedClusteringAnalyzer: only %d points – skipping", n
            )
            return ClusteringResult(
                labels=np.arange(n, dtype=int),
                originalities=np.ones(n, dtype="float32"),
            )

        logger.debug(
            "ConstrainedClusteringAnalyzer: reducing %d embeddings with UMAP", n
        )
        n_neighbors = max(2, min(self._UMAP_NEIGHBORS, n - 1))
        n_components = max(1, min(self._UMAP_COMPONENTS, n - 2))
        reduced = umap.UMAP(
            n_neighbors=n_neighbors,
            n_components=n_components,
            metric="cosine",
            low_memory=True,
            random_state=self._RANDOM_STATE,
        ).fit_transform(X)

        k_min = max(2, min(self._min_clusters, n // 2))
        k_max = max(k_min, min(self._max_clusters, n - 1))

        labels = self._best_k_labels(reduced, k_min, k_max)
        originalities = self._centroid_originalities(reduced, labels)

        n_clusters = len(np.unique(labels))
        logger.debug("ConstrainedClusteringAnalyzer: %d clusters", n_clusters)

        return ClusteringResult(labels=labels, originalities=originalities)

    def _best_k_labels(self, X: np.ndarray, k_min: int, k_max: int) -> np.ndarray:
        """Pick k in [k_min, k_max] that maximises the silhouette score."""
        best_score = -2.0
        best_labels: np.ndarray = np.zeros(len(X), dtype=int)

        for k in range(k_min, k_max + 1):
            lbls = AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(X)
            if len(np.unique(lbls)) < 2:
                continue
            score = float(silhouette_score(X, lbls))
            if score > best_score:
                best_score = score
                best_labels = lbls

        return best_labels.astype(int)

    def _centroid_originalities(
        self, X: np.ndarray, labels: np.ndarray
    ) -> np.ndarray:
        """Originality = distance from cluster centroid, normalised to [0, 1]."""
        dists = np.zeros(len(X), dtype="float32")
        for label in np.unique(labels):
            mask = labels == label
            centroid = X[mask].mean(axis=0)
            dists[mask] = np.linalg.norm(X[mask] - centroid, axis=1).astype("float32")

        if dists.max() == 0:
            return dists
        return MinMaxScaler().fit_transform(dists.reshape(-1, 1)).flatten().astype("float32")


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
# TocTreeBuilder – Two-level flat builder (sections → chapters → ideas)
# ---------------------------------------------------------------------------

class TocTreeBuilder:
    """
    Build a two-level TOC tree: sections (level 1) → chapters (level 2) → ideas.

    The first analyzer clusters all ideas into sections (target 5-10).
    The chapter analyzer sub-clusters large sections into chapters (target 2-4).
    This structure mirrors a book table of contents:
    - ~5-10 main sections
    - A few chapters per section (for sections large enough to warrant them)
    - Ideas as leaf nodes; only genuinely outlying ideas become isolated leaves

    The optional chapter_analyzer defaults to the section analyzer when omitted,
    preserving backward compatibility with injected test doubles.
    """

    _MIN_LEAF_SIZE: int = 3
    _CHAPTER_THRESHOLD: int = 5   # sections with > this many ideas get chapters
    _DEFAULT_MAX_DEPTH: int = 2

    def __init__(
        self,
        analyzer: Any,
        title_generator: TitleGenerator,
        chapter_analyzer: Any = None,
    ) -> None:
        self._analyzer = analyzer
        self._chapter_analyzer = chapter_analyzer if chapter_analyzer is not None else analyzer
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
            max_depth: Maximum nesting depth (1 = sections only, 2 = sections+chapters).

        Returns:
            Top-level list of TocEntry nodes.
        """
        docs = data.documents
        ids = data.ids
        embeddings = data.embeddings
        n = len(docs)

        # Base case: too few ideas → emit leaves directly.
        if n <= self._MIN_LEAF_SIZE:
            result = self._analyzer.analyze(embeddings)
            return self._make_leaves(docs, ids, result.originalities)

        result = self._analyzer.analyze(embeddings)
        real_clusters = np.unique(result.labels[result.labels != -1])

        # Single cluster or all noise → no useful split.
        if len(real_clusters) <= 1:
            return self._make_leaves(docs, ids, result.originalities)

        entries: list[TocEntry] = []

        # Noise points (label == -1) are genuinely isolated ideas → direct leaves.
        noise_idx = np.where(result.labels == -1)[0]
        for i in noise_idx:
            entries.append(TocEntry(
                title=ids[i],
                text=unformat_text(ids[i], docs[i], []),
                type="idea",
                id=ids[i],
                originality=self._fmt_pct(float(result.originalities[i])),
            ))

        # Build section headings.
        for label in real_clusters:
            idx = np.where(result.labels == label)[0]
            sec_docs = [docs[i] for i in idx]
            sec_ids = [ids[i] for i in idx]
            sec_emb = [embeddings[i] for i in idx]
            sec_orig = result.originalities[idx]

            if max_depth >= 2 and len(sec_ids) > self._CHAPTER_THRESHOLD:
                children = self._build_chapters(sec_docs, sec_ids, sec_emb)
            else:
                children = self._make_leaves(sec_docs, sec_ids, sec_orig)

            entries.append(TocEntry(
                title=self._titler.generate(sec_docs),
                type="heading",
                level=1,
                originality=self._fmt_pct(float(sec_orig.mean())),
                children=children,
            ))

        return entries

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_chapters(
        self,
        docs: list[str],
        ids: list[str],
        embeddings: list[list[float]],
    ) -> list[TocEntry]:
        """Sub-cluster a section into chapter headings (level 2)."""
        result = self._chapter_analyzer.analyze(embeddings)
        real_clusters = np.unique(result.labels[result.labels != -1])

        # Only one cluster → return ideas directly (no chapter headings needed).
        if len(real_clusters) <= 1:
            return self._make_leaves(docs, ids, result.originalities)

        chapters: list[TocEntry] = []

        # Noise points within this section → isolated leaves under section.
        noise_idx = np.where(result.labels == -1)[0]
        for i in noise_idx:
            chapters.append(TocEntry(
                title=ids[i],
                text=unformat_text(ids[i], docs[i], []),
                type="idea",
                id=ids[i],
                originality=self._fmt_pct(float(result.originalities[i])),
            ))

        for label in real_clusters:
            idx = np.where(result.labels == label)[0]
            ch_docs = [docs[i] for i in idx]
            ch_ids = [ids[i] for i in idx]
            ch_orig = result.originalities[idx]

            chapters.append(TocEntry(
                title=self._titler.generate(ch_docs),
                type="heading",
                level=2,
                originality=self._fmt_pct(float(ch_orig.mean())),
                children=self._make_leaves(ch_docs, ch_ids, ch_orig),
            ))

        return chapters

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

    Default wiring uses ConstrainedClusteringAnalyzer (two separate instances for
    sections and chapters) which produces structured, book-like TOC hierarchies
    with 5-10 sections and 2-4 chapters each.
    """

    def __init__(
        self,
        repository: IdeaRepository | None = None,
        cache: TocCachePort | None = None,
        analyzer: Any = None,
        title_generator: TitleGenerator | None = None,
        tree_builder: TocTreeBuilder | None = None,
    ) -> None:
        _titler = title_generator or TitleGenerator()

        if tree_builder is not None:
            _tree_builder = tree_builder
        elif analyzer is not None:
            # Caller supplied a custom analyzer → use it for both levels.
            _tree_builder = TocTreeBuilder(analyzer, _titler)
        else:
            # Default: constrained analyzers tuned for sections and chapters.
            _section_analyzer = ConstrainedClusteringAnalyzer(
                min_clusters=5, max_clusters=10
            )
            _chapter_analyzer = ConstrainedClusteringAnalyzer(
                min_clusters=2, max_clusters=4
            )
            _tree_builder = TocTreeBuilder(
                _section_analyzer, _titler, chapter_analyzer=_chapter_analyzer
            )

        self._repo: IdeaRepository = repository or ChromaClient()
        self._cache: TocCachePort = cache or FileTocCache()
        self._tree_builder: TocTreeBuilder = _tree_builder

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
