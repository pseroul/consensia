import sys
import os
import pytest
from unittest.mock import Mock, patch

# Add the backend directory to the path so we can import chroma_client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.chroma_client import ChromaClient

@pytest.mark.unit
class TestChromaClient:
    """Test cases for ChromaClient class"""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        with patch('backend.chroma_client.chromadb.PersistentClient') as mock_client:
            with patch('backend.chroma_client.embedding_functions.SentenceTransformerEmbeddingFunction'):
                self.mock_collection = Mock()
                mock_client.return_value.get_or_create_collection.return_value = self.mock_collection
                self.chroma_client = ChromaClient(collection_name="TestCollection")

    def test_init(self):
        """Test ChromaClient initialization"""
        assert hasattr(self.chroma_client, 'client')
        assert hasattr(self.chroma_client, 'emb_fn')
        assert hasattr(self.chroma_client, 'collection')
        assert self.chroma_client.model_name == "all-mpnet-base-v2"

    def test_insert_idea(self):
        """insert_idea stores title, tags, and original description in metadata."""
        self.chroma_client.insert_idea("Test Idea", "This is a test description", ["tag1", "tag2"])

        self.mock_collection.add.assert_called_once()
        kwargs = self.mock_collection.add.call_args[1]

        assert len(kwargs['documents']) == 1
        assert kwargs['metadatas'][0]['title'] == "Test Idea"
        assert kwargs['metadatas'][0]['tags'] == "tag1,tag2"
        assert kwargs['metadatas'][0]['description'] == "This is a test description"
        assert kwargs['ids'][0] == "Test Idea"

    def test_insert_idea_with_comments(self):
        """insert_idea passes comments through to format_text."""
        self.chroma_client.insert_idea("Idea", "Desc", [], ["comment one"])

        kwargs = self.mock_collection.add.call_args[1]
        assert "comment one" in kwargs['documents'][0]

    def test_insert_idea_stores_original_description(self):
        """Original description must be in metadata even when LLM summarizes."""
        mock_llm = Mock()
        mock_llm.summarize_texts.return_value = ["short summary"]

        with patch('backend.chroma_client.chromadb.PersistentClient') as mock_client:
            with patch('backend.chroma_client.embedding_functions.SentenceTransformerEmbeddingFunction'):
                mock_col = Mock()
                mock_client.return_value.get_or_create_collection.return_value = mock_col
                client = ChromaClient(collection_name="T", llm=mock_llm)

        long_content = "word " * 70  # exceeds _WORD_THRESHOLD
        client.insert_idea("Title", long_content, [])

        kwargs = mock_col.add.call_args[1]
        assert kwargs['metadatas'][0]['description'] == long_content

    def test_update_idea(self):
        """update_idea stores title, tags, and original description in metadata."""
        self.chroma_client.update_idea("Updated Idea", "Updated description", ["t"])

        self.mock_collection.update.assert_called_once()
        kwargs = self.mock_collection.update.call_args[1]

        assert len(kwargs['documents']) == 1
        assert kwargs['metadatas'][0]['title'] == "Updated Idea"
        assert kwargs['metadatas'][0]['tags'] == "t"
        assert kwargs['metadatas'][0]['description'] == "Updated description"
        assert kwargs['ids'][0] == "Updated Idea"

    def test_remove_idea(self):
        """Test remove_idea method"""
        self.chroma_client.remove_idea('Idea removed')

        self.mock_collection.delete.assert_called_once()
        kwargs = self.mock_collection.delete.call_args[1]
        assert kwargs['ids'] == ["Idea removed"]

    def test_get_similar_idea(self):
        """Test get_similar_idea method"""
        mock_results = {
            'ids': [['Idea 1', 'Idea 2']],
            'documents': [['Document 1', 'Document 2']]
        }
        self.mock_collection.query.return_value = mock_results

        results = self.chroma_client.get_similar_idea("test query", 5)

        self.mock_collection.query.assert_called_once_with(
            query_texts=["test query"],
            n_results=5
        )
        assert len(results) == 2
        assert results[0] == 'Idea 1'
        assert results[1] == 'Idea 2'

    def test_get_all_ideas(self):
        """get_all_ideas must include metadatas in addition to embeddings and documents."""
        mock_result = Mock()
        self.mock_collection.get.return_value = mock_result

        result = self.chroma_client.get_all_ideas(100)

        self.mock_collection.get.assert_called_once_with(
            include=['embeddings', 'documents', 'metadatas'],
            limit=100
        )
        assert result == mock_result

    def test_bulk_insert(self):
        """bulk_insert calls collection.add with correct documents, metadatas, ids."""
        ideas = [
            {"title": "A", "description": "desc a", "tags": ["t1"]},
            {"title": "B", "description": "desc b", "tags": []},
        ]
        self.chroma_client.bulk_insert(ideas)

        self.mock_collection.add.assert_called_once()
        kwargs = self.mock_collection.add.call_args[1]
        assert kwargs['ids'] == ["A", "B"]
        assert kwargs['metadatas'][0]['description'] == "desc a"
        assert kwargs['metadatas'][1]['description'] == "desc b"

    def test_bulk_insert_stores_originals(self):
        """bulk_insert must store original descriptions in metadata, not summaries."""
        mock_llm = Mock()
        mock_llm.summarize_texts.return_value = ["summary"]

        with patch('backend.chroma_client.chromadb.PersistentClient') as mock_client:
            with patch('backend.chroma_client.embedding_functions.SentenceTransformerEmbeddingFunction'):
                mock_col = Mock()
                mock_client.return_value.get_or_create_collection.return_value = mock_col
                client = ChromaClient(collection_name="T", llm=mock_llm)

        long_desc = "word " * 70
        ideas = [{"title": "X", "description": long_desc, "tags": []}]
        client.bulk_insert(ideas)

        kwargs = mock_col.add.call_args[1]
        assert kwargs['metadatas'][0]['description'] == long_desc

    def test_maybe_summarize_skips_short_text(self):
        """_maybe_summarize must not call the LLM for short texts."""
        mock_llm = Mock()

        with patch('backend.chroma_client.chromadb.PersistentClient') as mock_client:
            with patch('backend.chroma_client.embedding_functions.SentenceTransformerEmbeddingFunction'):
                mock_col = Mock()
                mock_client.return_value.get_or_create_collection.return_value = mock_col
                client = ChromaClient(collection_name="T", llm=mock_llm)

        result = client._maybe_summarize("short text")
        mock_llm.summarize_texts.assert_not_called()
        assert result == "short text"

    def test_maybe_summarize_fallback_on_error(self):
        """_maybe_summarize must return original text when the LLM raises."""
        mock_llm = Mock()
        mock_llm.summarize_texts.side_effect = Exception("LLM down")

        with patch('backend.chroma_client.chromadb.PersistentClient') as mock_client:
            with patch('backend.chroma_client.embedding_functions.SentenceTransformerEmbeddingFunction'):
                mock_col = Mock()
                mock_client.return_value.get_or_create_collection.return_value = mock_col
                client = ChromaClient(collection_name="T", llm=mock_llm)

        long_text = "word " * 70
        result = client._maybe_summarize(long_text)
        assert result == long_text
