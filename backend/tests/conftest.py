"""
Session-scoped fixtures shared across all unit tests in backend/tests/.

The ML module patching fixture here ensures that heavy ML dependencies
(umap, sentence_transformers, chromadb, hdbscan) are replaced with MagicMocks
exactly once at session start. This prevents test_main.py from injecting mocks
at import time, which would corrupt test_data_similarity.py::TestEmbeddingAnalyzer
(which exercises the real UMAP → HDBSCAN pipeline).

Only modules that are NOT already present in sys.modules are patched. If the
real library is installed and already imported by the time this fixture runs, it
is left alone.
"""

import sys
import pytest
from unittest.mock import MagicMock

_ML_MODULES = [
    "umap", "umap.umap_",
    "sentence_transformers",
    "chromadb", "chromadb.utils", "chromadb.utils.embedding_functions",
    "hdbscan", "hdbscan.hdbscan_",
]


@pytest.fixture(scope="session", autouse=True)
def patch_ml_modules():
    """Patch heavy ML modules once for the whole test session.

    test_data_similarity.py::TestEmbeddingAnalyzer intentionally exercises
    the real umap/hdbscan pipeline. Because that module imports umap/hdbscan
    at the top level, Python will have already loaded the real libraries before
    this fixture runs — so the ``if mod not in sys.modules`` guard ensures
    those real imports are never overwritten.
    """
    injected = []
    for mod in _ML_MODULES:
        if mod not in sys.modules:
            sys.modules[mod] = MagicMock()
            injected.append(mod)

    yield

    for mod in injected:
        sys.modules.pop(mod, None)
