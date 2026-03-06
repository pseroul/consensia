import sys
import os
from unittest.mock import Mock, patch, MagicMock
import numpy as np
import pytest

# Add the backend directory to the path so we can import data_similarity
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.data_similarity import (
    DataSimilarity,
    save_toc_structure,
    load_toc_structure,
    unformat_text
)


class TestDataSimilarity:
    """Test cases for DataSimilarity class"""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.data_similarity = DataSimilarity()

    @patch('backend.data_similarity.ChromaClient')
    @patch('backend.data_similarity.save_toc_structure')
    def test_generate_toc_structure(self, mock_save, mock_chroma_client):
        """Test generate_toc_structure method"""
        # Mock the ChromaClient to return test data
        mock_instance = Mock()
        mock_chroma_client.return_value = mock_instance
        
        # Mock the get_all_ideas response
        mock_instance.get_all_ideas.return_value = {
            'documents': ['doc1', 'doc2', 'doc3'],
            'ids': ['id1', 'id2', 'id3'],
            'embeddings': [
                [0.1, 0.2, 0.3],
                [0.4, 0.5, 0.6],
                [0.7, 0.8, 0.9]
            ]
        }
        
        # Mock the generate_originality_score method
        with patch.object(self.data_similarity, 'generate_originality_score', return_value=[0.5, 0.6, 0.7]):
            with patch.object(self.data_similarity, '_generate_toc_structure', return_value=[{'title': 'Test'}]):
                result = self.data_similarity.generate_toc_structure()
                
                # Verify the result
                assert result == [{'title': 'Test'}]
                
                # Verify that save_toc_structure was called
                mock_save.assert_called_once()

    def test_generate_originality_score(self):
        """Test generate_originality_score method"""
        # Create test embeddings
        embeddings = [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
            [0.7, 0.8, 0.9]
        ]
        
        # Mock UMAP and LocalOutlierFactor
        with patch('backend.data_similarity.umap.UMAP') as mock_umap:
            with patch('backend.data_similarity.LocalOutlierFactor') as mock_lof:
                # Setup mocks
                mock_reducer = Mock()
                mock_reducer.fit_transform.return_value = np.array([
                    [0.1, 0.2],
                    [0.3, 0.4],
                    [0.5, 0.6]
                ])
                mock_umap.return_value = mock_reducer
                
                mock_lof_instance = Mock()
                mock_lof_instance.negative_outlier_factor_ = np.array([-0.5, -0.6, -0.7])
                mock_lof.return_value = mock_lof_instance
                
                # Call the method
                result = self.data_similarity.generate_originality_score(embeddings)
                
                # Verify the result is a list of floats
                assert isinstance(result, np.ndarray)
                assert len(result) == 3

    def test_generate_synthetic_title(self):
        """Test generate_synthetic_title method"""
        # Test with empty list
        result = self.data_similarity.generate_synthetic_title([])
        assert result == "New Section"
        
        # Test with single document
        result = self.data_similarity.generate_synthetic_title(["This is a test document"])
        assert len(result) > 0
        
        # Test with multiple documents
        cluster_docs = [
            "Machine learning is powerful",
            "Deep learning uses neural networks",
            "Artificial intelligence is growing"
        ]
        result = self.data_similarity.generate_synthetic_title(cluster_docs)
        assert len(result) > 0

    def test_generate_synthetic_title_exception(self):
        """Test generate_synthetic_title method with exception handling"""
        # Mock TfidfVectorizer to raise an exception
        with patch('backend.data_similarity.TfidfVectorizer') as mock_vectorizer:
            mock_vectorizer.side_effect = Exception("Test exception")
            
            result = self.data_similarity.generate_synthetic_title(["test document"])
            # Should return fallback title
            assert "Section : test document" in result

    @patch('backend.data_similarity.np')
    def test__generate_toc_structure_base_case(self, mock_np):
        """Test _generate_toc_structure method base case (small dataset)"""
        # Mock numpy to return small array
        mock_np.array.return_value = np.array([[0.1, 0.2, 0.3]])
        mock_np.where.return_value = (np.array([0]),)
        mock_np.unique.return_value = np.array([0])
        
        docs = ['doc1']
        ids = ['id1']
        embeddings = [[0.1, 0.2, 0.3]]
        originalities = [0.5]
        
        with patch('backend.data_similarity.unformat_text') as mock_unformat:
            mock_unformat.return_value = "Formatted text"
            
            result = self.data_similarity._generate_toc_structure(
                docs, ids, embeddings, originalities, level=1, max_depth=3
            )
            
            # Should return list of idea entries (base case)
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]['type'] == 'idea'
            assert result[0]['id'] == 'id1'




class TestTocCache:
    """Test cases for TOC cache functions"""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Set environment variable for cache path
        self.cache_path = os.path.join(os.path.dirname(__file__), "test_toc_cache.json")
        os.environ['TOC_CACHE_PATH'] = self.cache_path

    def teardown_method(self):
        """Clean up after each test method."""
        # Remove the cache file if it exists
        if os.path.exists(self.cache_path):
            os.remove(self.cache_path)

    def test_save_toc_structure(self):
        """Test save_toc_structure function"""
        test_structure = [
            {
                'title': 'Test Section',
                'type': 'heading',
                'children': [
                    {'title': 'Child 1', 'type': 'idea'}
                ]
            }
        ]
        
        save_toc_structure(test_structure)
        
        # Verify the file was created
        assert os.path.exists(self.cache_path)
        
        # Verify the content
        with open(self.cache_path, 'r') as f:
            content = f.read()
            assert 'Test Section' in content

    def test_load_toc_structure(self):
        """Test load_toc_structure function"""
        # First, save some test data
        test_structure = [
            {
                'title': 'Test Section',
                'type': 'heading',
                'children': [
                    {'title': 'Child 1', 'type': 'idea'}
                ]
            }
        ]
        save_toc_structure(test_structure)
        
        # Now load it
        result = load_toc_structure()
        
        # Verify the result
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]['title'] == 'Test Section'

    def test_load_toc_structure_no_file(self):
        """Test load_toc_structure when file doesn't exist"""
        # Make sure the file doesn't exist
        if os.path.exists(self.cache_path):
            os.remove(self.cache_path)
        
        result = load_toc_structure()
        assert result is None

    def test_load_toc_structure_corrupted(self):
        """Test load_toc_structure with corrupted file"""
        # Create a corrupted file
        with open(self.cache_path, 'w') as f:
            f.write('invalid json {{{{')
        
        result = load_toc_structure()
        assert result is None
