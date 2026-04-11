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
        # Mock the ChromaDB client to avoid actual database operations
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
        assert self.chroma_client.model_name == "all-MiniLM-L6-v2"
    
    def test_insert_idea(self):
        """Test insert_idea method"""
        # Test that insert_idea calls collection.add with correct parameters
        self.chroma_client.insert_idea("Test Idea", "This is a test description", [])
        
        self.mock_collection.add.assert_called_once()
        # Get the kwargs from the call
        kwargs = self.mock_collection.add.call_args[1]
        
        # Check that the correct data was passed
        assert len(kwargs['documents']) == 1
        assert kwargs['metadatas'][0]['title'] == "Test Idea"
        assert kwargs['ids'][0] == "Test Idea"
    
    def test_update_idea(self):
        """Test update_idea method"""
        # Test that update_idea calls collection.update with correct parameters
        self.chroma_client.update_idea("Updated Idea", "This is an updated description", [])
        
        self.mock_collection.update.assert_called_once()
        # Get the kwargs from the call
        kwargs = self.mock_collection.update.call_args[1]
        
        # Check that the correct data was passed
        assert len(kwargs['documents']) == 1
        assert kwargs['metadatas'][0]['title'] == "Updated Idea"
        assert kwargs['ids'][0] == "Updated Idea"
    
    def test_remove_idea(self):
        """Test remove_idea method"""
        # Test that remove_idea calls collection.delete with correct parameters
        self.chroma_client.remove_idea('Idea removed')
        
        self.mock_collection.delete.assert_called_once()
        # Get the kwargs from the call
        kwargs = self.mock_collection.delete.call_args[1]
        
        # Check that the correct ID was passed
        assert kwargs['ids'] == ["Idea removed"]
    
    def test_get_similar_idea(self):
        """Test get_similar_idea method"""
        # Mock the collection.query response
        mock_results = {
            'ids': [['Idea 1', 'Idea 2']],
            'documents': [['Document 1', 'Document 2']]
        }
        self.mock_collection.query.return_value = mock_results
        
        # Mock the utils.unformat_text function
        with patch('backend.chroma_client.utils.unformat_text') as mock_unformat:
            mock_unformat.side_effect = lambda title, content: f"{title}: {content}"
            
            results = self.chroma_client.get_similar_idea("test query", 5)
            
            # Check that query was called with correct parameters
            self.mock_collection.query.assert_called_once_with(
                query_texts=["test query"],
                n_results=5
            )
            
            # Check that we got the expected results
            assert len(results) == 2
            assert results[0] == 'Idea 1'
            assert results[1] == 'Idea 2'
    
    def test_get_all_ideas(self):
        """Test get_all_data method"""
        # Mock the collection.get response
        mock_result = Mock()
        self.mock_collection.get.return_value = mock_result
        
        result = self.chroma_client.get_all_ideas(100)
        
        # Check that get was called with correct parameters
        self.mock_collection.get.assert_called_once_with(
            include=['embeddings', 'documents'],
            limit=100
        )
        assert result == mock_result