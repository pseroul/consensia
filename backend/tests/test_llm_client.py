import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import pytest
from unittest.mock import patch, MagicMock
from urllib.error import URLError

from backend.llm_client import (
    LlmUnavailableError,
    ClaudeLlmClient,
    OllamaLlmClient,
    TfidfFallbackClient,
    create_llm_client,
    _parse_json_array,
    _build_title_sections_block,
    _build_order_sections_block,
    _build_summarize_texts_block,
)


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

def _sample_sections(n: int = 3) -> list[dict]:
    return [
        {
            "ideas": [f"Idea {j} about topic {i}" for j in range(3)],
            "num_ideas": 3,
        }
        for i in range(n)
    ]


def _sample_summaries(n: int = 3) -> list[dict]:
    return [
        {
            "title": f"Section {i}",
            "num_ideas": 3,
            "idea_titles": [f"Idea {j}" for j in range(3)],
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# _parse_json_array
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestParseJsonArray:
    def test_parses_valid_json_array(self):
        assert _parse_json_array('["a", "b"]') == ["a", "b"]

    def test_parses_array_with_surrounding_text(self):
        assert _parse_json_array('Here: [1, 2, 3] done') == [1, 2, 3]

    def test_raises_on_no_array(self):
        with pytest.raises(LlmUnavailableError, match="No JSON array"):
            _parse_json_array("no array here")

    def test_parses_multiline_json(self):
        text = 'Result:\n[\n  "Title A",\n  "Title B"\n]'
        assert _parse_json_array(text) == ["Title A", "Title B"]


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPromptBuilders:
    def test_title_block_contains_section_numbers(self):
        block = _build_title_sections_block(_sample_sections(2))
        assert "Section 1" in block
        assert "Section 2" in block

    def test_title_block_truncates_long_ideas(self):
        sections = [{"ideas": ["x" * 200], "num_ideas": 1}]
        block = _build_title_sections_block(sections)
        for line in block.split("\n"):
            if line.startswith("- "):
                assert len(line) <= 152  # "- " + 150 chars

    def test_order_block_contains_indices(self):
        block = _build_order_sections_block(_sample_summaries(3))
        assert "0." in block
        assert "1." in block
        assert "2." in block

    def test_summarize_block_contains_text_numbers(self):
        block = _build_summarize_texts_block(["hello", "world"])
        assert "Text 1:" in block
        assert "Text 2:" in block
        assert "hello" in block
        assert "world" in block

    def test_summarize_block_truncates_long_texts(self):
        block = _build_summarize_texts_block(["x" * 2000])
        assert len(block) < 2000  # truncated to 1000 chars per text


# ---------------------------------------------------------------------------
# ClaudeLlmClient
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestClaudeLlmClient:
    def test_raises_without_api_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        mock_anthropic = MagicMock()
        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            with pytest.raises(LlmUnavailableError, match="ANTHROPIC_API_KEY"):
                ClaudeLlmClient(api_key="")

    def test_raises_when_anthropic_not_installed(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with patch.dict(sys.modules, {"anthropic": None}):
            with pytest.raises(LlmUnavailableError, match="anthropic package"):
                ClaudeLlmClient(api_key="test-key")

    def test_generate_titles_success(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        mock_anthropic = MagicMock()
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='["The Art of Code", "Digital Horizons", "New Frontiers"]')]
        mock_client.messages.create.return_value = mock_response

        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            client = ClaudeLlmClient(api_key="test-key")
            titles = client.generate_titles(_sample_sections(3))

        assert titles == ["The Art of Code", "Digital Horizons", "New Frontiers"]

    def test_generate_titles_wrong_count_raises(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        mock_anthropic = MagicMock()
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='["Only One"]')]
        mock_client.messages.create.return_value = mock_response

        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            client = ClaudeLlmClient(api_key="test-key")
            with pytest.raises(LlmUnavailableError, match="Expected 3"):
                client.generate_titles(_sample_sections(3))

    def test_order_sections_success(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        mock_anthropic = MagicMock()
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="[2, 0, 1]")]
        mock_client.messages.create.return_value = mock_response

        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            client = ClaudeLlmClient(api_key="test-key")
            order = client.order_sections(_sample_summaries(3))

        assert order == [2, 0, 1]

    def test_order_sections_invalid_indices_raises(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        mock_anthropic = MagicMock()
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="[0, 1, 99]")]
        mock_client.messages.create.return_value = mock_response

        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            client = ClaudeLlmClient(api_key="test-key")
            with pytest.raises(LlmUnavailableError, match="Invalid indices"):
                client.order_sections(_sample_summaries(3))

    def test_order_sections_duplicate_indices_raises(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        mock_anthropic = MagicMock()
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="[0, 0, 1]")]
        mock_client.messages.create.return_value = mock_response

        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            client = ClaudeLlmClient(api_key="test-key")
            with pytest.raises(LlmUnavailableError, match="unique indices"):
                client.order_sections(_sample_summaries(3))

    def test_sanitise_long_title(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        mock_anthropic = MagicMock()
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        long_title = "A " * 50  # > 80 chars
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps([long_title]))]
        mock_client.messages.create.return_value = mock_response

        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            client = ClaudeLlmClient(api_key="test-key")
            titles = client.generate_titles(_sample_sections(1))

        assert len(titles[0]) <= 80

    def test_api_error_raises_llm_unavailable(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        mock_anthropic = MagicMock()
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("timeout")

        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            client = ClaudeLlmClient(api_key="test-key")
            with pytest.raises(LlmUnavailableError, match="Claude API error"):
                client.generate_titles(_sample_sections(1))

    def test_summarize_texts_success(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        mock_anthropic = MagicMock()
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='["Summary A", "Summary B"]')]
        mock_client.messages.create.return_value = mock_response

        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            client = ClaudeLlmClient(api_key="test-key")
            result = client.summarize_texts(["Long text A", "Long text B"])

        assert result == ["Summary A", "Summary B"]

    def test_summarize_texts_empty_returns_empty(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        mock_anthropic = MagicMock()
        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            client = ClaudeLlmClient(api_key="test-key")
            assert client.summarize_texts([]) == []

    def test_summarize_texts_wrong_count_raises(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        mock_anthropic = MagicMock()
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='["Only one"]')]
        mock_client.messages.create.return_value = mock_response

        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            client = ClaudeLlmClient(api_key="test-key")
            with pytest.raises(LlmUnavailableError, match="Expected 2"):
                client.summarize_texts(["text one", "text two"])

    def test_summarize_texts_batching(self, monkeypatch):
        """More than 20 texts should trigger multiple _call invocations."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        mock_anthropic = MagicMock()
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        def make_response(texts_count):
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text=json.dumps([f"s{i}" for i in range(texts_count)]))]
            return mock_response

        # 25 texts → 2 batches (20 + 5)
        mock_client.messages.create.side_effect = [
            make_response(20),
            make_response(5),
        ]

        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            client = ClaudeLlmClient(api_key="test-key")
            result = client.summarize_texts([f"text {i}" for i in range(25)])

        assert len(result) == 25
        assert mock_client.messages.create.call_count == 2


# ---------------------------------------------------------------------------
# OllamaLlmClient
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestOllamaLlmClient:
    def test_generate_titles_success(self):
        response_body = json.dumps({
            "response": '["The Art of Code", "Digital Horizons"]'
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("backend.llm_client.urlopen", return_value=mock_resp):
            client = OllamaLlmClient(base_url="http://fake:11434", model="test")
            titles = client.generate_titles(_sample_sections(2))

        assert titles == ["The Art of Code", "Digital Horizons"]

    def test_order_sections_success(self):
        response_body = json.dumps({"response": "[1, 0, 2]"}).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("backend.llm_client.urlopen", return_value=mock_resp):
            client = OllamaLlmClient(base_url="http://fake:11434", model="test")
            order = client.order_sections(_sample_summaries(3))

        assert order == [1, 0, 2]

    def test_network_error_raises_llm_unavailable(self):
        with patch("backend.llm_client.urlopen", side_effect=URLError("refused")):
            client = OllamaLlmClient(base_url="http://fake:11434", model="test")
            with pytest.raises(LlmUnavailableError, match="Ollama error"):
                client.generate_titles(_sample_sections(1))

    def test_summarize_texts_success(self):
        response_body = json.dumps({"response": '["Summary A", "Summary B"]'}).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("backend.llm_client.urlopen", return_value=mock_resp):
            client = OllamaLlmClient(base_url="http://fake:11434", model="test")
            result = client.summarize_texts(["Long text A", "Long text B"])

        assert result == ["Summary A", "Summary B"]

    def test_summarize_texts_empty_returns_empty(self):
        client = OllamaLlmClient(base_url="http://fake:11434", model="test")
        assert client.summarize_texts([]) == []

    def test_summarize_texts_wrong_count_raises(self):
        response_body = json.dumps({"response": '["Only one"]'}).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("backend.llm_client.urlopen", return_value=mock_resp):
            client = OllamaLlmClient(base_url="http://fake:11434", model="test")
            with pytest.raises(LlmUnavailableError, match="Expected 2"):
                client.summarize_texts(["text one", "text two"])


# ---------------------------------------------------------------------------
# TfidfFallbackClient
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTfidfFallbackClient:
    def test_generate_titles_returns_one_per_section(self):
        client = TfidfFallbackClient()
        sections = _sample_sections(3)
        titles = client.generate_titles(sections)
        assert len(titles) == 3
        assert all(isinstance(t, str) for t in titles)

    def test_order_sections_returns_identity(self):
        client = TfidfFallbackClient()
        order = client.order_sections(_sample_summaries(4))
        assert order == [0, 1, 2, 3]

    def test_empty_sections(self):
        client = TfidfFallbackClient()
        assert client.generate_titles([]) == []
        assert client.order_sections([]) == []

    def test_summarize_texts_passthrough(self):
        """TfidfFallbackClient must return texts unchanged."""
        client = TfidfFallbackClient()
        texts = ["hello world", "foo bar baz"]
        assert client.summarize_texts(texts) == texts

    def test_summarize_texts_empty(self):
        client = TfidfFallbackClient()
        assert client.summarize_texts([]) == []


# ---------------------------------------------------------------------------
# create_llm_client factory
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCreateLlmClient:
    def test_returns_tfidf_when_no_key_no_ollama(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OLLAMA_URL", raising=False)
        with patch("backend.llm_client._ollama_reachable", return_value=False):
            client = create_llm_client()
        assert isinstance(client, TfidfFallbackClient)

    def test_returns_claude_when_key_set(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        mock_anthropic = MagicMock()
        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            client = create_llm_client()
        assert isinstance(client, ClaudeLlmClient)

    def test_returns_ollama_when_reachable(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with patch("backend.llm_client._ollama_reachable", return_value=True):
            client = create_llm_client()
        assert isinstance(client, OllamaLlmClient)

    def test_falls_back_to_ollama_when_claude_fails(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "bad-key")
        with (
            patch.dict(sys.modules, {"anthropic": None}),
            patch("backend.llm_client._ollama_reachable", return_value=True),
        ):
            client = create_llm_client()
        assert isinstance(client, OllamaLlmClient)

    def test_falls_through_to_tfidf_when_all_fail(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "bad-key")
        with (
            patch.dict(sys.modules, {"anthropic": None}),
            patch("backend.llm_client._ollama_reachable", return_value=False),
        ):
            client = create_llm_client()
        assert isinstance(client, TfidfFallbackClient)
