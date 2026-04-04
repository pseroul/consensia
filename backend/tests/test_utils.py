import sys
import os

# Add the backend directory to the path so we can import utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.utils import format_text, unformat_text


class TestUtils:
    """Test cases for utils functions"""

    def test_format_text(self):
        """Test format_text function"""
        # Test with single tag
        result = format_text("Test Idea", "This is a test description", ["test-tag"])
        expected = "Test Idea / [test-tag] : This is a test description"
        assert result == expected
        
        # Test with multiple tags
        result = format_text("Test Idea", "This is a test description", ["tag1", "tag2", "tag3"])
        expected = "Test Idea / [tag1;tag2;tag3] : This is a test description"
        assert result == expected
        
        # Test with empty tags list
        result = format_text("Test Idea", "This is a test description", [])
        expected = "Test Idea / [] : This is a test description"
        assert result == expected
        
        # Test with special characters in name and description
        result = format_text("Test/Idea", "Description with [brackets] and : colons", ["tag-1"])
        expected = "Test/Idea / [tag-1] : Description with [brackets] and : colons"
        assert result == expected

    def test_unformat_text(self):
        """Test unformat_text function"""
        # Test with single tag
        formatted = "Test Idea / [test-tag] : This is a test description"
        result = unformat_text("Test Idea", formatted, ["test-tag"])
        expected = "This is a test description"
        assert result == expected
        
        # Test with multiple tags
        formatted = "Test Idea / [tag1;tag2;tag3] : This is a test description"
        result = unformat_text("Test Idea", formatted, ["tag1", "tag2", "tag3"])
        expected = "This is a test description"
        assert result == expected
        
        # Test with empty tags list
        formatted = "Test Idea / [] : This is a test description"
        result = unformat_text("Test Idea", formatted, [])
        expected = "This is a test description"
        assert result == expected
        
        # Test with special characters in name and description
        formatted = "Test/Idea / [tag-1] : Description with [brackets] and : colons"
        result = unformat_text("Test/Idea", formatted, ["tag-1"])
        expected = "Description with [brackets] and : colons"
        assert result == expected
        
        # Test when formatted string doesn't match expected pattern
        # (should return the original description as-is)
        result = unformat_text("Test Idea", "Random formatted string", ["test-tag"])
        # The function will try to remove the pattern but it won't match, so it returns the original
        assert result == "Random formatted string"
