"""
LLM client abstraction for TOC title generation and section ordering.

Provides a Protocol-based interface with three implementations:
  1. ClaudeLlmClient  – Anthropic Claude API (best quality)
  2. OllamaLlmClient  – Local Ollama server (offline fallback)
  3. TfidfFallbackClient – TF-IDF keyword extraction (zero external deps)

The factory ``create_llm_client()`` selects the best available backend
based on environment variables and service reachability.
"""

import json
import logging
import os
import re
from typing import Any, Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger("uvicorn.error")


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class LlmUnavailableError(Exception):
    """Raised when an LLM backend cannot fulfil a request."""


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

class LlmPort(Protocol):
    """Abstract interface for LLM-assisted TOC refinement."""

    def generate_titles(self, sections: list[dict[str, Any]]) -> list[str]:
        """Generate book-like titles for a batch of TOC sections.

        Args:
            sections: Each dict has keys ``ideas`` (list of summary strings)
                      and ``num_ideas`` (int).

        Returns:
            One title string per section, in the same order.

        Raises:
            LlmUnavailableError: If the LLM backend is unreachable or fails.
        """
        ...

    def order_sections(self, section_summaries: list[dict[str, Any]]) -> list[int]:
        """Determine optimal narrative reading order for TOC sections.

        Args:
            section_summaries: Each dict has keys ``title`` (str),
                ``num_ideas`` (int), and ``idea_titles`` (list[str]).

        Returns:
            List of 0-based indices representing the optimal order.

        Raises:
            LlmUnavailableError: If the LLM backend is unreachable or fails.
        """
        ...


# ---------------------------------------------------------------------------
# Prompt builders (shared between Claude and Ollama)
# ---------------------------------------------------------------------------

_TITLE_PROMPT_TEMPLATE = """\
You are writing the table of contents for a professional book.
For each section below, generate a concise, evocative book chapter title \
(max 8 words).
The title must read like a real book chapter — NOT a keyword list.
Do NOT use ampersands or generic phrases like "Various Topics".

{sections_block}

Respond with ONLY a JSON array of titles, one per section, in the same order.
Example: ["The Dawn of Innovation", "Building Resilient Systems"]"""

_ORDER_PROMPT_TEMPLATE = """\
You are organizing a book's table of contents.
Order these sections to create a coherent narrative arc: \
foundational concepts first, then applications, \
then advanced topics. Think like a book editor.

{sections_block}

Respond with ONLY a JSON array of 0-based indices in optimal reading order.
Example: [2, 0, 3, 1]"""


def _build_title_sections_block(sections: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for i, sec in enumerate(sections, 1):
        ideas = sec.get("ideas", [])
        lines = [f"- {idea[:150]}" for idea in ideas[:8]]
        parts.append(f"Section {i} ({sec.get('num_ideas', len(ideas))} ideas):\n" + "\n".join(lines))
    return "\n\n".join(parts)


def _build_order_sections_block(summaries: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for i, s in enumerate(summaries):
        sample = ", ".join(s.get("idea_titles", [])[:5])
        parts.append(f'{i}. "{s["title"]}" ({s["num_ideas"]} ideas about: {sample})')
    return "\n".join(parts)


def _parse_json_array(text: str) -> list:
    """Extract and parse a JSON array from LLM output."""
    match = re.search(r"\[.*]", text, re.DOTALL)
    if not match:
        raise LlmUnavailableError(f"No JSON array found in LLM response: {text[:200]}")
    return json.loads(match.group())


# ---------------------------------------------------------------------------
# ClaudeLlmClient
# ---------------------------------------------------------------------------

class ClaudeLlmClient:
    """LLM client using the Anthropic Claude API."""

    _TIMEOUT: float = 30.0
    _MAX_TITLE_LEN: int = 80

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        try:
            import anthropic  # noqa: F811
        except ImportError as exc:
            raise LlmUnavailableError(
                "anthropic package not installed"
            ) from exc

        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        if not self._api_key:
            raise LlmUnavailableError("ANTHROPIC_API_KEY is not set")

        self._model = model or os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001")
        self._client = anthropic.Anthropic(
            api_key=self._api_key,
            timeout=self._TIMEOUT,
        )
        logger.info("ClaudeLlmClient initialised (model=%s)", self._model)

    def generate_titles(self, sections: list[dict[str, Any]]) -> list[str]:
        block = _build_title_sections_block(sections)
        prompt = _TITLE_PROMPT_TEMPLATE.format(sections_block=block)
        raw = self._call(prompt)
        titles = _parse_json_array(raw)

        if len(titles) != len(sections):
            raise LlmUnavailableError(
                f"Expected {len(sections)} titles, got {len(titles)}"
            )

        return [self._sanitise_title(t) for t in titles]

    def order_sections(self, section_summaries: list[dict[str, Any]]) -> list[int]:
        block = _build_order_sections_block(section_summaries)
        prompt = _ORDER_PROMPT_TEMPLATE.format(sections_block=block)
        raw = self._call(prompt)
        indices = _parse_json_array(raw)

        n = len(section_summaries)
        if not all(isinstance(i, int) and 0 <= i < n for i in indices):
            raise LlmUnavailableError(f"Invalid indices in LLM response: {indices}")
        if len(set(indices)) != n:
            raise LlmUnavailableError(f"Expected {n} unique indices, got {indices}")

        return indices

    def _call(self, prompt: str) -> str:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as exc:
            raise LlmUnavailableError(f"Claude API error: {exc}") from exc

    def _sanitise_title(self, title: str) -> str:
        title = title.strip().strip('"').strip("'").strip()
        if len(title) > self._MAX_TITLE_LEN:
            title = title[: self._MAX_TITLE_LEN].rsplit(" ", 1)[0]
        return title if title else "Untitled Section"


# ---------------------------------------------------------------------------
# OllamaLlmClient
# ---------------------------------------------------------------------------

class OllamaLlmClient:
    """LLM client using a local Ollama server."""

    _TIMEOUT: float = 60.0
    _MAX_TITLE_LEN: int = 80

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self._base_url = (
            base_url or os.getenv("OLLAMA_URL", "http://localhost:11434")
        ).rstrip("/")
        self._model = model or os.getenv("OLLAMA_MODEL", "phi3:mini")
        logger.info(
            "OllamaLlmClient initialised (url=%s, model=%s)",
            self._base_url,
            self._model,
        )

    def generate_titles(self, sections: list[dict[str, Any]]) -> list[str]:
        block = _build_title_sections_block(sections)
        prompt = _TITLE_PROMPT_TEMPLATE.format(sections_block=block)
        raw = self._call(prompt)
        titles = _parse_json_array(raw)

        if len(titles) != len(sections):
            raise LlmUnavailableError(
                f"Expected {len(sections)} titles, got {len(titles)}"
            )

        return [self._sanitise_title(t) for t in titles]

    def order_sections(self, section_summaries: list[dict[str, Any]]) -> list[int]:
        block = _build_order_sections_block(section_summaries)
        prompt = _ORDER_PROMPT_TEMPLATE.format(sections_block=block)
        raw = self._call(prompt)
        indices = _parse_json_array(raw)

        n = len(section_summaries)
        if not all(isinstance(i, int) and 0 <= i < n for i in indices):
            raise LlmUnavailableError(f"Invalid indices in LLM response: {indices}")
        if len(set(indices)) != n:
            raise LlmUnavailableError(f"Expected {n} unique indices, got {indices}")

        return indices

    def _call(self, prompt: str) -> str:
        payload = json.dumps({
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }).encode()

        req = Request(  # noqa: S310
            f"{self._base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(req, timeout=self._TIMEOUT) as resp:  # noqa: S310
                body = json.loads(resp.read().decode())
                return body.get("response", "")
        except (URLError, OSError, json.JSONDecodeError, KeyError) as exc:
            raise LlmUnavailableError(f"Ollama error: {exc}") from exc

    def _sanitise_title(self, title: str) -> str:
        title = title.strip().strip('"').strip("'").strip()
        if len(title) > self._MAX_TITLE_LEN:
            title = title[: self._MAX_TITLE_LEN].rsplit(" ", 1)[0]
        return title if title else "Untitled Section"


# ---------------------------------------------------------------------------
# TfidfFallbackClient
# ---------------------------------------------------------------------------

class TfidfFallbackClient:
    """Zero-dependency fallback that delegates to TitleGenerator."""

    def __init__(self) -> None:
        from data_similarity import TitleGenerator

        self._titler = TitleGenerator()
        logger.info("TfidfFallbackClient initialised (no LLM available)")

    def generate_titles(self, sections: list[dict[str, Any]]) -> list[str]:
        return [
            self._titler.generate(sec.get("ideas", []))
            for sec in sections
        ]

    def order_sections(self, section_summaries: list[dict[str, Any]]) -> list[int]:
        return list(range(len(section_summaries)))


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def _ollama_reachable(base_url: str) -> bool:
    """Quick health check against the Ollama server."""
    try:
        req = Request(f"{base_url}/api/tags", method="GET")  # noqa: S310
        with urlopen(req, timeout=2) as resp:  # noqa: S310
            return resp.status == 200
    except (URLError, OSError):
        return False


def create_llm_client() -> LlmPort:
    """Select the best available LLM backend.

    Priority:
      1. Claude API  (if ``ANTHROPIC_API_KEY`` is set)
      2. Ollama      (if the local server responds)
      3. TF-IDF      (always available)
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if api_key:
        try:
            return ClaudeLlmClient(api_key=api_key)
        except LlmUnavailableError:
            logger.warning("Claude API unavailable, trying Ollama…")

    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    if _ollama_reachable(ollama_url):
        return OllamaLlmClient(base_url=ollama_url)

    logger.info("No LLM backend available, using TF-IDF fallback")
    return TfidfFallbackClient()
