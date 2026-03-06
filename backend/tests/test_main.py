import sys
import os
from unittest.mock import Mock, patch, MagicMock
import pytest
import sqlite3

# Add the backend directory to the path so we can import main
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from backend.main import app, get_db, IdeaItem, TagItem, RelationItem, LoginRequest

client = TestClient(app)


class TestMainAPI:
    """Test cases for the main API endpoints"""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Create a temporary database for testing
        self.test_db = os.path.join(os.path.dirname(__file__), "test_main_database.db")
        os.environ["NAME_DB"] = self.test_db
        
        # Initialize the database
        from backend.data_handler import init_database
        init_database()
        
        # Insert test user
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)",
                      ("testuser", "test@example.com", "hashed_password"))
        conn.commit()
        conn.close()

    def teardown_method(self):
        """Clean up after each test method."""
        # Remove the test database file
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_health_check(self):
        """Test the health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    @patch('backend.main.get_ideas')
    def test_get_all_ideas(self, mock_get_ideas):
        """Test getting all ideas"""
        # Mock the get_ideas function to return test data
        # Note: tags should be strings, not lists, to match the Pydantic model
        mock_get_ideas.return_value = [
            {"id": 1, "title": "Test Idea 1", "content": "Content 1", "tags": "tag1"},
            {"id": 2, "title": "Test Idea 2", "content": "Content 2", "tags": "tag2"}
        ]
        
        response = client.get("/ideas")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["title"] == "Test Idea 1"

    @patch('backend.main.get_idea_from_tags')
    def test_get_ideas_by_tags(self, mock_get_ideas_by_tags):
        """Test getting ideas by tags"""
        # Mock the get_idea_from_tags function
        # Note: tags should be strings, not lists, to match the Pydantic model
        mock_get_ideas_by_tags.return_value = [
            {"id": 1, "title": "Test Idea 1", "content": "Content 1", "tags": "tag1"}
        ]
        
        response = client.get("/ideas/tags/tag1;tag2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Test Idea 1"

    @patch('backend.main.get_similar_idea')
    def test_search_ideas(self, mock_get_similar_idea):
        """Test searching ideas"""
        # Mock the get_similar_idea function
        # Note: tags should be strings, not lists, to match the Pydantic model
        mock_get_similar_idea.return_value = [
            {"id": 1, "title": "Test Idea 1", "content": "Content 1", "tags": "tag1"}
        ]
        
        response = client.get("/ideas/search/test")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    @patch('backend.main.get_content')
    def test_get_idea_content(self, mock_get_content):
        """Test getting idea content"""
        # Mock the get_content function
        mock_get_content.return_value = "This is the content of idea 1"
        
        response = client.get("/ideas/1/content")
        assert response.status_code == 200
        assert response.json() == "This is the content of idea 1"

    @patch('backend.main.get_tags')
    def test_get_all_tags(self, mock_get_tags):
        """Test getting all tags"""
        # Mock the get_tags function
        mock_get_tags.return_value = [
            {"name": "tag1"},
            {"name": "tag2"}
        ]
        
        response = client.get("/tags")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "tag1"

    @patch('backend.main.get_tags_from_idea')
    def test_get_tags_for_idea(self, mock_get_tags_from_idea):
        """Test getting tags for a specific idea"""
        # Mock the get_tags_from_idea function
        mock_get_tags_from_idea.return_value = ["tag1", "tag2"]
        
        response = client.get("/ideas/1/tags")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data == ["tag1", "tag2"]

    @patch('backend.main.get_similar_idea')
    def test_get_similar_ideas_endpoint(self, mock_get_similar_idea):
        """Test getting similar ideas"""
        # Mock the get_similar_idea function
        # Note: tags should be strings, not lists, to match the Pydantic model
        mock_get_similar_idea.return_value = [
            {"id": 2, "title": "Similar Idea", "content": "Similar content", "tags": "tag1"}
        ]
        
        response = client.get("/ideas/similar/TestIdea")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Similar Idea"

    @patch('backend.main.add_idea')
    @patch('backend.main.add_tag')
    @patch('backend.main.add_relation')
    def test_create_idea(self, mock_add_relation, mock_add_tag, mock_add_idea):
        """Test creating a new idea"""
        # Mock the add_idea function to return an ID
        mock_add_idea.return_value = 1
        
        # Test with tags
        idea_data = {
            "title": "New Idea",
            "content": "This is a new idea",
            "tags": "tag1;tag2;tag3"
        }
        
        response = client.post("/ideas", json=idea_data)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        
        # Verify that add_idea was called with correct parameters
        mock_add_idea.assert_called_once_with("New Idea", "This is a new idea", owner=1)
        
        # Verify that tags were processed
        assert mock_add_tag.call_count == 3
        assert mock_add_relation.call_count == 3

    @patch('backend.main.add_idea')
    def test_create_idea_without_tags(self, mock_add_idea):
        """Test creating a new idea without tags"""
        # Mock the add_idea function to return an ID
        mock_add_idea.return_value = 1
        
        # Test without tags
        idea_data = {
            "title": "New Idea",
            "content": "This is a new idea"
        }
        
        response = client.post("/ideas", json=idea_data)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data

    @patch('backend.main.add_tag')
    def test_create_tag(self, mock_add_tag):
        """Test creating a new tag"""
        tag_data = {"name": "new-tag"}
        
        response = client.post("/tags", json=tag_data)
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Tag 'new-tag' added successfully"
        mock_add_tag.assert_called_once_with("new-tag")

    @patch('backend.main.add_relation')
    def test_create_relation(self, mock_add_relation):
        """Test creating a new relation"""
        relation_data = {
            "idea_id": 1,
            "tag_name": "test-tag"
        }
        
        response = client.post("/relations", json=relation_data)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        mock_add_relation.assert_called_once_with(1, "test-tag")

    @patch('backend.main.update_idea')
    @patch('backend.main.get_tags_from_idea')
    @patch('backend.main.add_tag')
    @patch('backend.main.add_relation')
    @patch('backend.main.remove_relation')
    def test_update_idea(self, mock_remove_relation, mock_add_relation, mock_add_tag, 
                         mock_get_tags_from_idea, mock_update_idea):
        """Test updating an existing idea"""
        # Mock the get_tags_from_idea function
        mock_get_tags_from_idea.return_value = ["old-tag1", "old-tag2"]
        
        # Test with updated tags
        idea_data = {
            "id": 1,
            "title": "Updated Idea",
            "content": "Updated content",
            "tags": "new-tag1;new-tag2"
        }
        
        response = client.put("/ideas/1", json=idea_data)
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Idea '1' updated successfully"
        
        # Verify that update_idea was called
        mock_update_idea.assert_called_once_with(id=1, title="Updated Idea", content="Updated content")

    @patch('backend.main.remove_idea')
    def test_delete_idea(self, mock_remove_idea):
        """Test deleting an idea"""
        # DELETE endpoints with Pydantic models - use json parameter
        # Note: TestClient.delete() doesn't support json parameter directly
        # We need to use a workaround by sending the data as part of the request
        response = client.request(
            "DELETE",
            "/ideas/1",
            json={
                "id": 1,
                "title": "Idea to Delete",
                "content": "Content to delete"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Idea '1' removed successfully"
        mock_remove_idea.assert_called_once_with(id=1, title="Idea to Delete")

    @patch('backend.main.remove_tag')
    def test_delete_tag(self, mock_remove_tag):
        """Test deleting a tag"""
        response = client.delete("/tags/test-tag")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Tag 'test-tag' removed successfully"
        mock_remove_tag.assert_called_once_with("test-tag")

    @patch('backend.main.remove_relation')
    def test_delete_relation(self, mock_remove_relation):
        """Test deleting a relation"""
        # DELETE endpoints with Pydantic models - use json parameter
        # Note: TestClient.delete() doesn't support json parameter directly
        # We need to use a workaround by sending the data as part of the request
        response = client.request(
            "DELETE",
            "/relations",
            json={
                "idea_id": 1,
                "tag_name": "test-tag"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        mock_remove_relation.assert_called_once_with(1, "test-tag")

    @patch('backend.main.verify_access')
    def test_verify_otp_success(self, mock_verify_access):
        """Test OTP verification success"""
        # Mock the verify_access function to return True
        mock_verify_access.return_value = True
        
        login_data = {
            "email": "test@example.com",
            "otp_code": "123456"
        }
        
        response = client.post("/verify-otp", json=login_data)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["message"] == "Connection authorized"

    @patch('backend.main.verify_access')
    def test_verify_otp_failure(self, mock_verify_access):
        """Test OTP verification failure"""
        # Mock the verify_access function to return False
        mock_verify_access.return_value = False
        
        login_data = {
            "email": "test@example.com",
            "otp_code": "invalid"
        }
        
        response = client.post("/verify-otp", json=login_data)
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "Invalid or expired code" in data["detail"]

    @patch('backend.main.load_toc_structure')
    @patch('backend.main.DataSimilarity')
    def test_get_toc_structure_from_cache(self, mock_data_similarity, mock_load_toc):
        """Test getting TOC structure from cache"""
        # Mock the load_toc_structure function to return cached data
        mock_load_toc.return_value = [
            {"title": "Section 1", "type": "heading", "children": []}
        ]
        
        response = client.get("/toc/structure")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Section 1"
        
        # Verify that DataSimilarity was not called (using cache)
        mock_data_similarity.assert_not_called()

    @patch('backend.main.load_toc_structure')
    @patch('backend.main.DataSimilarity')
    def test_get_toc_structure_generate_new(self, mock_data_similarity, mock_load_toc):
        """Test generating new TOC structure when cache is empty"""
        # Mock the load_toc_structure function to return None (no cache)
        mock_load_toc.return_value = None
        
        # Mock the DataSimilarity class
        mock_instance = Mock()
        mock_instance.generate_toc_structure.return_value = [
            {"title": "New Section", "type": "heading", "children": []}
        ]
        mock_data_similarity.return_value = mock_instance
        
        response = client.get("/toc/structure")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "New Section"
        
        # Verify that DataSimilarity was called to generate new structure
        mock_data_similarity.assert_called_once()
        mock_instance.generate_toc_structure.assert_called_once()

    @patch('backend.main.DataSimilarity')
    def test_update_toc_structure(self, mock_data_similarity):
        """Test updating TOC structure"""
        # Mock the DataSimilarity class
        mock_instance = Mock()
        mock_instance.generate_toc_structure.return_value = [
            {"title": "Updated Section", "type": "heading", "children": []}
        ]
        mock_data_similarity.return_value = mock_instance
        
        response = client.post("/toc/update")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "toc added successfully"
        
        # Verify that DataSimilarity was called
        mock_data_similarity.assert_called_once()
        mock_instance.generate_toc_structure.assert_called_once()

    def test_get_db_connection(self):
        """Test database connection helper function"""
        # Test that get_db yields a connection
        for conn in get_db():
            assert isinstance(conn, sqlite3.Connection)
            conn.close()
            break

    def test_error_handling_get_ideas(self):
        """Test error handling in get_all_ideas endpoint"""
        with patch('backend.main.get_ideas') as mock_get_ideas:
            # Mock the get_ideas function to raise an exception
            mock_get_ideas.side_effect = Exception("Database error")
            
            response = client.get("/ideas")
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert "Error retrieving data" in data["detail"]

    def test_error_handling_create_idea(self):
        """Test error handling in create_idea endpoint"""
        with patch('backend.main.add_idea') as mock_add_idea:
            # Mock the add_idea function to raise an exception
            mock_add_idea.side_effect = Exception("Database error")
            
            idea_data = {
                "title": "New Idea",
                "content": "This is a new idea"
            }
            
            response = client.post("/ideas", json=idea_data)
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert "Error adding idea" in data["detail"]

    def test_invalid_input_create_idea(self):
        """Test invalid input in create_idea endpoint"""
        # Test with missing required fields
        idea_data = {
            "title": "New Idea"
            # Missing content
        }
        
        response = client.post("/ideas", json=idea_data)
        assert response.status_code == 422  # Validation error

    def test_invalid_input_create_tag(self):
        """Test invalid input in create_tag endpoint"""
        # Test with missing required field
        tag_data = {}  # Missing name
        
        response = client.post("/tags", json=tag_data)
        assert response.status_code == 422  # Validation error


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_empty_tags_list(self):
        """Test handling of empty tags list"""
        with patch('backend.main.add_idea') as mock_add_idea:
            mock_add_idea.return_value = 1
            
            idea_data = {
                "title": "Idea with Empty Tags",
                "content": "Content",
                "tags": ""
            }
            
            response = client.post("/ideas", json=idea_data)
            assert response.status_code == 200
            data = response.json()
            assert "id" in data

    def test_whitespace_tags(self):
        """Test handling of tags with whitespace"""
        with patch('backend.main.add_idea') as mock_add_idea:
            with patch('backend.main.add_tag') as mock_add_tag:
                with patch('backend.main.add_relation') as mock_add_relation:
                    mock_add_idea.return_value = 1
                    
                    idea_data = {
                        "title": "Idea with Whitespace Tags",
                        "content": "Content",
                        "tags": "  tag1  ;  tag2  ;  tag3  "
                    }
                    
                    response = client.post("/ideas", json=idea_data)
                    assert response.status_code == 200
                    
                    # Verify that tags were processed correctly (whitespace stripped)
                    assert mock_add_tag.call_count == 3

    def test_special_characters_in_tags(self):
        """Test handling of special characters in tags"""
        with patch('backend.main.add_idea') as mock_add_idea:
            with patch('backend.main.add_tag') as mock_add_tag:
                with patch('backend.main.add_relation') as mock_add_relation:
                    mock_add_idea.return_value = 1
                    
                    idea_data = {
                        "title": "Idea with Special Tags",
                        "content": "Content",
                        "tags": "tag-1;tag_2;tag.3;tag@4"
                    }
                    
                    response = client.post("/ideas", json=idea_data)
                    assert response.status_code == 200
                    
                    # Verify that all tags were processed
                    assert mock_add_tag.call_count == 4

    def test_duplicate_tags(self):
        """Test handling of duplicate tags"""
        with patch('backend.main.add_idea') as mock_add_idea:
            with patch('backend.main.add_tag') as mock_add_tag:
                with patch('backend.main.add_relation') as mock_add_relation:
                    mock_add_idea.return_value = 1
                    
                    idea_data = {
                        "title": "Idea with Duplicate Tags",
                        "content": "Content",
                        "tags": "tag1;tag2;tag1;tag3;tag2"
                    }
                    
                    response = client.post("/ideas", json=idea_data)
                    assert response.status_code == 200
                    
                    # Verify that all tags were processed (including duplicates)
                    assert mock_add_tag.call_count == 5

    def test_long_content(self):
        """Test handling of very long content"""
        with patch('backend.main.add_idea') as mock_add_idea:
            mock_add_idea.return_value = 1
            
            # Create a very long content string
            long_content = "A" * 10000
            
            idea_data = {
                "title": "Idea with Long Content",
                "content": long_content
            }
            
            response = client.post("/ideas", json=idea_data)
            assert response.status_code == 200
            data = response.json()
            assert "id" in data

    def test_special_characters_in_title(self):
        """Test handling of special characters in title"""
        with patch('backend.main.add_idea') as mock_add_idea:
            mock_add_idea.return_value = 1
            
            idea_data = {
                "title": "Idea with Special Chars: / \\ | ? * < >",
                "content": "Content"
            }
            
            response = client.post("/ideas", json=idea_data)
            assert response.status_code == 200
            data = response.json()
            assert "id" in data

    def test_unicode_characters(self):
        """Test handling of unicode characters"""
        with patch('backend.main.add_idea') as mock_add_idea:
            mock_add_idea.return_value = 1
            
            idea_data = {
                "title": "Idea with Unicode: 你好世界 🌍",
                "content": "Content with unicode: café, naïve, résumé"
            }
            
            response = client.post("/ideas", json=idea_data)
            assert response.status_code == 200
            data = response.json()
            assert "id" in data

    def test_empty_search(self):
        """Test searching with empty string"""
        with patch('backend.main.get_similar_idea') as mock_get_similar_idea:
            mock_get_similar_idea.return_value = []
            
            # The endpoint expects a path parameter, so we need to provide a valid search term
            response = client.get("/ideas/search/empty")
            assert response.status_code == 200
            data = response.json()
            assert data == []

    def test_search_with_special_chars(self):
        """Test searching with special characters"""
        with patch('backend.main.get_similar_idea') as mock_get_similar_idea:
            # Note: tags should be strings, not lists, to match the Pydantic model
            mock_get_similar_idea.return_value = [
                {"id": 1, "title": "Test Idea", "content": "Content", "tags": "tag1"}
            ]
            
            response = client.get("/ideas/search/test?query=special")
            assert response.status_code == 200

    def test_get_nonexistent_idea_content(self):
        """Test getting content for non-existent idea"""
        with patch('backend.main.get_content') as mock_get_content:
            # Mock the get_content function to raise an exception
            mock_get_content.side_effect = Exception("Idea not found")
            
            response = client.get("/ideas/999999/content")
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data

    def test_update_nonexistent_idea(self):
        """Test updating non-existent idea"""
        with patch('backend.main.update_idea') as mock_update_idea:
            # Mock the update_idea function to raise an exception
            mock_update_idea.side_effect = Exception("Idea not found")
            
            idea_data = {
                "id": 999999,
                "title": "Updated Idea",
                "content": "Updated content"
            }
            
            response = client.put("/ideas/999999", json=idea_data)
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data

    def test_delete_nonexistent_idea(self):
        """Test deleting non-existent idea"""
        with patch('backend.main.remove_idea') as mock_remove_idea:
            # Mock the remove_idea function to raise an exception
            mock_remove_idea.side_effect = Exception("Idea not found")
            
            response = client.request(
                "DELETE",
                "/ideas/999999",
                json={
                    "id": 999999,
                    "title": "Idea to Delete",
                    "content": "Content to delete"
                }
            )
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data

    def test_delete_nonexistent_tag(self):
        """Test deleting non-existent tag"""
        with patch('backend.main.remove_tag') as mock_remove_tag:
            # Mock the remove_tag function to raise an exception
            mock_remove_tag.side_effect = Exception("Tag not found")
            
            response = client.delete("/tags/nonexistent-tag")
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data

    def test_invalid_otp_format(self):
        """Test OTP verification with invalid format"""
        with patch('backend.main.verify_access') as mock_verify_access:
            # Mock the verify_access function to return False
            mock_verify_access.return_value = False
            
            login_data = {
                "email": "test@example.com",
                "otp_code": "invalid-code-with-dashes"
            }
            
            response = client.post("/verify-otp", json=login_data)
            assert response.status_code == 401
            data = response.json()
            assert "detail" in data

    def test_empty_otp(self):
        """Test OTP verification with empty code"""
        with patch('backend.main.verify_access') as mock_verify_access:
            # Mock the verify_access function to return False
            mock_verify_access.return_value = False
            
            login_data = {
                "email": "test@example.com",
                "otp_code": ""
            }
            
            response = client.post("/verify-otp", json=login_data)
            assert response.status_code == 401

    def test_missing_otp_fields(self):
        """Test OTP verification with missing fields"""
        # Test with missing email
        login_data = {
            "otp_code": "123456"
        }
        
        response = client.post("/verify-otp", json=login_data)
        assert response.status_code == 422  # Validation error

        # Test with missing OTP code
        login_data = {
            "email": "test@example.com"
        }
        
        response = client.post("/verify-otp", json=login_data)
        assert response.status_code == 422  # Validation error
