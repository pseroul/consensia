import sys
import os

# Add the backend directory to the path so we can import utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.utils import format_text


class TestUtils:
    """Test cases for utils functions"""

    def test_format_text_basic(self):
        """Title appears twice, tags comma-separated, no comments."""
        result = format_text("My Idea", "A short description", ["alpha", "beta"])
        assert result == "My Idea. Tags: alpha, beta. My Idea: A short description"

    def test_format_text_empty_tags(self):
        """Empty tag list produces an empty Tags section."""
        result = format_text("Title", "Content", [])
        assert result == "Title. Tags: . Title: Content"

    def test_format_text_single_tag(self):
        """Single tag should not have trailing comma."""
        result = format_text("T", "D", ["only"])
        assert result == "T. Tags: only. T: D"

    def test_format_text_with_comments(self):
        """Comments are appended last, joined by ' | '."""
        result = format_text("Idea", "Desc", ["t1"], ["first comment", "second comment"])
        assert result == "Idea. Tags: t1. Idea: Desc Comments: first comment | second comment"

    def test_format_text_none_comments_omitted(self):
        """Passing comments=None produces same output as no comments arg."""
        without = format_text("X", "Y", ["z"])
        with_none = format_text("X", "Y", ["z"], None)
        assert without == with_none

    def test_format_text_empty_comments_list_omitted(self):
        """An empty comments list should not append the Comments section."""
        result = format_text("X", "Y", ["z"], [])
        assert "Comments" not in result

    def test_format_text_title_repeated(self):
        """The title must appear at the start AND before the description."""
        result = format_text("RepTitle", "body text", [])
        parts = result.split("RepTitle")
        assert len(parts) == 3  # "RepTitle" occurs twice → three parts
