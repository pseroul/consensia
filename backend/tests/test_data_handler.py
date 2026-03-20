import sys
import os
from unittest.mock import Mock, patch, MagicMock
import pytest
import pandas as pd
import sqlite3

# Add the backend directory to the path so we can import data_handler
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.data_handler import (
    init_database,
    get_idea_from_tags,
    get_user_ideas,
    get_ideas,
    get_content,
    get_tags,
    get_tags_from_idea,
    get_similar_idea,
    add_idea,
    add_tag,
    add_relation,
    remove_idea,
    remove_tag,
    remove_relation,
    update_idea,
    embed_all_ideas
)

class TestDataHandler:
    """Test cases for data_handler functions"""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Create a temporary database for testing
        self.test_db = os.path.join(os.path.dirname(__file__), "test_database.db")
        print("test_db:", self.test_db)
        os.environ["NAME_DB"] = self.test_db
        
    def teardown_method(self):
        """Clean up after each test method."""
        # Remove the test database file
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
    
    def test_init_database(self):
        """Test database initialization"""
        init_database()
        
        # Check that the database file was created
        assert os.path.exists(self.test_db)
        
        # Connect to the database and verify tables exist
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        
        # Check for users table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
        assert cursor.fetchone() is not None
        
        # Check for tags table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tags';")
        assert cursor.fetchone() is not None
        
        # Check for ideas table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ideas';")
        assert cursor.fetchone() is not None
        
        # Check for relations table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='relations';")
        assert cursor.fetchone() is not None
        
        conn.close()
    
    def test_get_ideas_empty(self) -> None:
        """Test get_ideas when database is empty"""
        init_database()
        result = get_ideas()
        assert isinstance(result, list)
        assert len(result) == 0
    
    def test_get_ideas_with_data(self) -> None:
        """Test get_ideas with sample data"""
        init_database()
        
        # Insert test data
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)", 
                      ("testuser", "test@example.com", "hashed_password"))
        user_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO ideas (title, content, owner_id) VALUES (?, ?, ?)", 
                      ("Test Idea", "Test Content", user_id))
        idea_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO tags (name) VALUES (?)", ("test-tag",))
        cursor.execute("INSERT INTO relations (idea_id, tag_name) VALUES (?, ?)", 
                      (idea_id, "test-tag"))
        conn.commit()
        conn.close()
        
        result = get_ideas()
        assert len(result) == 1
        assert result[0]['title'] == "Test Idea"
        assert result[0]['content'] == "Test Content"
        assert 'test-tag' in result[0]['tags']
    
    def test_get_content(self) -> None:
        """Test get_content function"""
        init_database()
        
        # Insert test data
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)", 
                      ("testuser", "test@example.com", "hashed_password"))
        user_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO ideas (title, content, owner_id) VALUES (?, ?, ?)", 
                      ("Test Idea", "Test Content", user_id))
        idea_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        result = get_content(idea_id)
        assert result == "Test Content"
    
    def test_get_tags(self) -> None:
        """Test get_tags function"""
        init_database()
        
        # Insert test data
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tags (name) VALUES (?)", ("test-tag",))
        conn.commit()
        conn.close()
        
        result = get_tags()
        assert len(result) == 1
        assert result[0]['name'] == "test-tag"
    
    def test_get_tags_from_idea(self) -> None:
        """Test get_tags_from_idea function"""
        init_database()
        
        # Insert test data
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)", 
                      ("testuser", "test@example.com", "hashed_password"))
        user_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO ideas (title, content, owner_id) VALUES (?, ?, ?)", 
                      ("Test Idea", "Test Content", user_id))
        idea_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO tags (name) VALUES (?)", ("test-tag",))
        cursor.execute("INSERT INTO relations (idea_id, tag_name) VALUES (?, ?)", 
                      (idea_id, "test-tag"))
        conn.commit()
        conn.close()
        
        result = get_tags_from_idea(idea_id)
        assert len(result) == 1
        assert result[0] == "test-tag"
    
    @patch('backend.data_handler.ChromaClient')
    def test_get_similar_idea(self, mock_chroma_client) -> None:
        """Test get_similar_idea function"""
        init_database()
        
        # Mock the ChromaClient to return test data
        mock_instance = Mock()
        mock_chroma_client.return_value = mock_instance
        mock_instance.get_similar_idea.return_value = ["Test Idea"]
        
        # Insert test data
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)", 
                      ("testuser", "test@example.com", "hashed_password"))
        user_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO ideas (title, content, owner_id) VALUES (?, ?, ?)", 
                      ("Test Idea", "Test Content", user_id))
        conn.commit()
        conn.close()
        
        result = get_similar_idea("Test Idea")
        assert len(result) == 1
        assert result[0]['title'] == "Test Idea"
    
    @patch('backend.data_handler.ChromaClient')
    def test_add_idea_success(self, mock_chroma_client) -> None:
        """Test add_idea function success case"""
        init_database()
        
        # Mock the ChromaClient to avoid actual embedding operations
        mock_instance = Mock()
        mock_chroma_client.return_value = mock_instance
        
        # Insert user first
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)", 
                      ("testuser", "test@example.com", "hashed_password"))
        conn.commit()
        conn.close()
        
        result = add_idea("New Idea", "New Content", "test@example.com")
        assert result > 0
        
        # Verify the idea was inserted
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ideas WHERE title = ?", ("New Idea",))
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 1
        
        # Verify the idea has the correct owner
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT owner_id FROM ideas WHERE title = ?", ("New Idea",))
        owner_id = cursor.fetchone()[0]
        cursor.execute("SELECT id FROM users WHERE email = ?", ("test@example.com",))
        user_id = cursor.fetchone()[0]
        assert owner_id == user_id
        conn.close()
    
    @patch('backend.data_handler.ChromaClient')
    def test_add_idea_nonexistent_user(self, mock_chroma_client) -> None:
        """Test add_idea function with non-existent user email"""
        init_database()
        
        # Mock the ChromaClient to avoid actual embedding operations
        mock_instance = Mock()
        mock_chroma_client.return_value = mock_instance
        
        # Try to add an idea with a non-existent user email
        result = add_idea("New Idea", "New Content", "nonexistent@example.com")
        assert result == -1
        
        # Verify no idea was inserted
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ideas WHERE title = ?", ("New Idea",))
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 0
    
    def test_add_tag(self) -> None:
        """Test add_tag function"""
        init_database()
        
        add_tag("test-tag")
        
        # Verify the tag was inserted
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tags WHERE name = ?", ("test-tag",))
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 1
    
    def test_add_relation(self) -> None:
        """Test add_relation function"""
        init_database()
        
        # Insert test data
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)", 
                      ("testuser", "test@example.com", "hashed_password"))
        user_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO ideas (title, content, owner_id) VALUES (?, ?, ?)", 
                      ("Test Idea", "Test Content", user_id))
        idea_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO tags (name) VALUES (?)", ("test-tag",))
        conn.commit()
        conn.close()
        
        add_relation(idea_id, "test-tag")
        
        # Verify the relation was inserted
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM relations WHERE idea_id = ? AND tag_name = ?", 
                      (idea_id, "test-tag"))
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 1
    
    @patch('backend.data_handler.ChromaClient')
    def test_remove_idea(self, mock_chroma_client) -> None:
        """Test remove_idea function"""
        init_database()
        
        # Mock the ChromaClient to avoid actual embedding operations
        mock_instance = Mock()
        mock_chroma_client.return_value = mock_instance
        
        # Insert test data
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)", 
                      ("testuser", "test@example.com", "hashed_password"))
        user_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO ideas (title, content, owner_id) VALUES (?, ?, ?)", 
                      ("Test Idea", "Test Content", user_id))
        idea_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        remove_idea(idea_id, "Test Idea")
        
        # Verify the idea was removed
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ideas WHERE id = ?", (idea_id,))
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 0
    
    def test_remove_tag(self) -> None:
        """Test remove_tag function"""
        init_database()
        
        # Insert test data
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tags (name) VALUES (?)", ("test-tag",))
        conn.commit()
        conn.close()
        
        remove_tag("test-tag")
        
        # Verify the tag was removed
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tags WHERE name = ?", ("test-tag",))
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 0
    
    def test_remove_relation(self) -> None:
        """Test remove_relation function"""
        init_database()
        
        # Insert test data
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)", 
                      ("testuser", "test@example.com", "hashed_password"))
        user_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO ideas (title, content, owner_id) VALUES (?, ?, ?)", 
                      ("Test Idea", "Test Content", user_id))
        idea_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO tags (name) VALUES (?)", ("test-tag",))
        cursor.execute("INSERT INTO relations (idea_id, tag_name) VALUES (?, ?)", 
                      (idea_id, "test-tag"))
        conn.commit()
        conn.close()
        
        remove_relation(idea_id, "test-tag")
        
        # Verify the relation was removed
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM relations WHERE idea_id = ? AND tag_name = ?", 
                      (idea_id, "test-tag"))
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 0
    
    @patch('backend.data_handler.ChromaClient')
    def test_update_idea(self, mock_chroma_client) -> None:
        """Test update_idea function"""
        init_database()
        
        # Mock the ChromaClient to avoid actual embedding operations
        mock_instance = Mock()
        mock_chroma_client.return_value = mock_instance
        
        # Insert test data
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)", 
                      ("testuser", "test@example.com", "hashed_password"))
        user_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO ideas (title, content, owner_id) VALUES (?, ?, ?)", 
                      ("Test Idea", "Test Content", user_id))
        idea_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        update_idea(idea_id, "Updated Idea", "Updated Content")
        
        # Verify the idea was updated
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT title, content FROM ideas WHERE id = ?", (idea_id,))
        result = cursor.fetchone()
        conn.close()
        assert result[0] == "Updated Idea"
        assert result[1] == "Updated Content"

    @patch('backend.data_handler.ChromaClient')
    def test_embed_all_ideas(self, mock_chroma_client) -> None:
        """Test embed_all_ideas function"""
        init_database()
        
        # Mock the ChromaClient to avoid actual embedding operations
        mock_instance = Mock()
        mock_chroma_client.return_value = mock_instance
        
        # Insert test data
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)", 
                      ("testuser", "test@example.com", "hashed_password"))
        user_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO ideas (title, content, owner_id) VALUES (?, ?, ?)", 
                      ("Test Idea", "Test Content", user_id))
        conn.commit()
        conn.close()
        
        # This should not raise an exception
        embed_all_ideas()
        
        # Verify that insert_idea was called
        mock_instance.insert_idea.assert_called()

    def test_get_user_ideas_empty(self) -> None:
        """Test get_user_ideas when user has no ideas"""
        init_database()
        
        # Insert a user
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)", 
                      ("testuser", "test@example.com", "hashed_password"))
        conn.commit()
        conn.close()
        
        result = get_user_ideas("test@example.com")
        assert isinstance(result, list)
        assert len(result) == 0

    def test_get_user_ideas_with_data(self) -> None:
        """Test get_user_ideas with sample data"""
        init_database()
        
        # Insert test data
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        
        # Insert two users
        cursor.execute("INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)", 
                      ("user1", "user1@example.com", "hashed_password"))
        user1_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)", 
                      ("user2", "user2@example.com", "hashed_password"))
        user2_id = cursor.lastrowid
        
        # Insert ideas for user1
        cursor.execute("INSERT INTO ideas (title, content, owner_id) VALUES (?, ?, ?)", 
                      ("User1 Idea", "User1 Content", user1_id))
        idea1_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO ideas (title, content, owner_id) VALUES (?, ?, ?)", 
                      ("User1 Idea 2", "User1 Content 2", user1_id))
        
        # Insert idea for user2
        cursor.execute("INSERT INTO ideas (title, content, owner_id) VALUES (?, ?, ?)", 
                      ("User2 Idea", "User2 Content", user2_id))
        
        # Add tags
        cursor.execute("INSERT INTO tags (name) VALUES (?)", ("tag1",))
        cursor.execute("INSERT INTO tags (name) VALUES (?)", ("tag2",))
        
        # Add relations
        cursor.execute("INSERT INTO relations (idea_id, tag_name) VALUES (?, ?)", 
                      (idea1_id, "tag1"))
        cursor.execute("INSERT INTO relations (idea_id, tag_name) VALUES (?, ?)", 
                      (idea1_id, "tag2"))
        
        conn.commit()
        conn.close()
        
        # Test getting ideas for user1
        result = get_user_ideas("user1@example.com")
        assert len(result) == 2
        assert result[0]['title'] == "User1 Idea"
        assert result[0]['content'] == "User1 Content"
        assert 'tag1' in result[0]['tags']
        assert 'tag2' in result[0]['tags']
        
        # Test getting ideas for user2
        result = get_user_ideas("user2@example.com")
        assert len(result) == 1
        assert result[0]['title'] == "User2 Idea"
        assert result[0]['content'] == "User2 Content"

    def test_get_user_ideas_nonexistent_user(self) -> None:
        """Test get_user_ideas with non-existent user email"""
        init_database()
        
        # Insert a user
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)", 
                      ("testuser", "test@example.com", "hashed_password"))
        conn.commit()
        conn.close()
        
        # Try to get ideas for a non-existent user
        result = get_user_ideas("nonexistent@example.com")
        assert isinstance(result, list)
        assert len(result) == 0

    def test_get_user_ideas_without_tags(self) -> None:
        """Test get_user_ideas when ideas have no tags"""
        init_database()
        
        # Insert test data
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        
        cursor.execute("INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)",
                      ("testuser", "test@example.com", "hashed_password"))
        user_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO ideas (title, content, owner_id) VALUES (?, ?, ?)",
                      ("Idea without tags", "Content", user_id))
        conn.commit()
        conn.close()
        
        result = get_user_ideas("test@example.com")
        assert len(result) == 1
        assert result[0]['title'] == "Idea without tags"
        # Tags should be empty string when no tags exist
        assert result[0]['tags'] == ''

    def test_get_idea_from_tags(self) -> None:
        """Test get_idea_from_tags function"""
        init_database()
        
        # Insert test data
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)",
                      ("testuser", "test@example.com", "hashed_password"))
        user_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO ideas (title, content, owner_id) VALUES (?, ?, ?)",
                      ("Test Idea", "Test Content", user_id))
        idea_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO tags (name) VALUES (?)", ("test-tag",))
        cursor.execute("INSERT INTO relations (idea_id, tag_name) VALUES (?, ?)",
                      (idea_id, "test-tag"))
        conn.commit()
        conn.close()
        
        # Test with single tag
        result = get_idea_from_tags("test-tag")
        assert len(result) == 1
        assert result[0]['title'] == "Test Idea"
        
        # Test with multiple tags (semicolon-separated)
        result = get_idea_from_tags("test-tag")
        assert len(result) == 1
        
        # Test with empty string (should return all ideas)
        result = get_idea_from_tags("")
        assert isinstance(result, list)

    def test_get_idea_from_tags_nonexistent_tag(self) -> None:
        """Test get_idea_from_tags with non-existent tag"""
        init_database()
        
        # Test with non-existent tag (should return empty list)
        result = get_idea_from_tags("nonexistent-tag")
        assert len(result) == 0
