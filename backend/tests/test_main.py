import sys
import os
from unittest.mock import Mock, patch
import pytest
import sqlite3

# Add both the backend directory (for bare imports inside main.py like `from authenticator import ...`)
# and the repo root (for package-style imports like `from backend.main import ...`) to the path.
_tests_dir = os.path.dirname(__file__)
_backend_dir = os.path.join(_tests_dir, '..')
_repo_root = os.path.join(_tests_dir, '../..')
sys.path.insert(0, os.path.abspath(_backend_dir))
sys.path.insert(0, os.path.abspath(_repo_root))

# Provide a valid database path before importing backend.main, because main.py calls
# init_database() at module level and needs NAME_DB to be set.
os.environ.setdefault("NAME_DB", os.path.join(os.path.abspath(_tests_dir), "test_main_database.db"))

from fastapi.testclient import TestClient
from backend.main import app, get_db

client = TestClient(app)


@pytest.mark.unit
class TestMainAPI:
    """Test cases for the main API endpoints"""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        import tempfile
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.test_db = self._tmp.name
        self._tmp.close()
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
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def _get_auth_headers(self):
        """Helper method to get authentication headers with valid JWT token"""
        # First, we need to verify OTP to get a token
        login_data = {
            "email": "test@example.com",
            "otp_code": "123456"  # Any code, since we're mocking verify_access
        }

        # Mock verify_access to return True
        with patch('backend.main.verify_access', return_value=True):
            response = client.post("/verify-otp", json=login_data)
            assert response.status_code == 200
            token = response.json()["access_token"]

            return {"Authorization": f"Bearer {token}"}

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
            {"id": 1, "title": "Test Idea 1", "content": "Content 1", "tags": "tag1", "book_id": 1},
            {"id": 2, "title": "Test Idea 2", "content": "Content 2", "tags": "tag2", "book_id": 1}
        ]

        # Get authentication headers
        headers = self._get_auth_headers()

        response = client.get("/ideas", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["title"] == "Test Idea 1"
        mock_get_ideas.assert_called_with(None)

    @patch('backend.main.get_ideas')
    def test_get_all_ideas_with_book_id(self, mock_get_ideas):
        """Test getting ideas filtered by book_id"""
        mock_get_ideas.return_value = [
            {"id": 1, "title": "Test Idea 1", "content": "Content 1", "tags": "tag1", "book_id": 5}
        ]
        headers = self._get_auth_headers()

        response = client.get("/ideas?book_id=5", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        mock_get_ideas.assert_called_with(5)

    @patch('backend.main.get_idea_from_tags')
    def test_get_ideas_by_tags(self, mock_get_ideas_by_tags):
        """Test getting ideas by tags"""
        # Mock the get_idea_from_tags function
        # Note: tags should be strings, not lists, to match the Pydantic model
        mock_get_ideas_by_tags.return_value = [
            {"id": 1, "title": "Test Idea 1", "content": "Content 1", "tags": "tag1", "book_id": 1}
        ]

        # Get authentication headers
        headers = self._get_auth_headers()

        response = client.get("/ideas/tags/tag1;tag2", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Test Idea 1"
        mock_get_ideas_by_tags.assert_called_with("tag1;tag2", None)

    @patch('backend.main.get_idea_from_tags')
    def test_get_ideas_by_tags_with_book_id(self, mock_get_ideas_by_tags):
        """Test getting ideas by tags filtered by book_id"""
        mock_get_ideas_by_tags.return_value = [
            {"id": 1, "title": "Test Idea 1", "content": "Content 1", "tags": "tag1", "book_id": 2}
        ]
        headers = self._get_auth_headers()

        response = client.get("/ideas/tags/tag1?book_id=2", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        mock_get_ideas_by_tags.assert_called_with("tag1", 2)

    @patch('backend.main.get_similar_idea')
    def test_search_ideas(self, mock_get_similar_idea):
        """Test searching ideas"""
        # Get authentication headers
        headers = self._get_auth_headers()

        # Mock the get_similar_idea function
        # Note: tags should be strings, not lists, to match the Pydantic model
        mock_get_similar_idea.return_value = [
            {"id": 1, "title": "Test Idea 1", "content": "Content 1", "tags": "tag1", "book_id": 1}
        ]

        response = client.get("/ideas/search/test", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    @patch('backend.main.get_content')
    def test_get_idea_content(self, mock_get_content):
        """Test getting idea content"""
        # Get authentication headers
        headers = self._get_auth_headers()

        # Mock the get_content function
        mock_get_content.return_value = "This is the content of idea 1"

        response = client.get("/ideas/1/content", headers=headers)
        assert response.status_code == 200
        assert response.json() == "This is the content of idea 1"

    @patch('backend.main.get_tags')
    def test_get_all_tags(self, mock_get_tags):
        """Test getting all tags"""
        # Get authentication headers
        headers = self._get_auth_headers()

        # Mock the get_tags function
        mock_get_tags.return_value = [
            {"name": "tag1"},
            {"name": "tag2"}
        ]

        response = client.get("/tags", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "tag1"
        mock_get_tags.assert_called_with(None)

    @patch('backend.main.get_tags')
    def test_get_tags_with_book_id(self, mock_get_tags):
        """Test getting tags filtered by book_id"""
        headers = self._get_auth_headers()
        mock_get_tags.return_value = [{"name": "book-tag"}]

        response = client.get("/tags?book_id=3", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "book-tag"
        mock_get_tags.assert_called_with(3)

    @patch('backend.main.get_tags_from_idea')
    def test_get_tags_for_idea(self, mock_get_tags_from_idea):
        """Test getting tags for a specific idea"""
        # Get authentication headers
        headers = self._get_auth_headers()

        # Mock the get_tags_from_idea function
        mock_get_tags_from_idea.return_value = ["tag1", "tag2"]

        response = client.get("/ideas/1/tags", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data == ["tag1", "tag2"]

    @patch('backend.main.get_similar_idea')
    def test_get_similar_ideas_endpoint(self, mock_get_similar_idea):
        """Test getting similar ideas"""
        # Get authentication headers
        headers = self._get_auth_headers()

        # Mock the get_similar_idea function
        # Note: tags should be strings, not lists, to match the Pydantic model
        mock_get_similar_idea.return_value = [
            {"id": 2, "title": "Similar Idea", "content": "Similar content", "tags": "tag1", "book_id": 1}
        ]

        response = client.get("/ideas/similar/TestIdea", headers=headers)
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

        # Get authentication headers
        headers = self._get_auth_headers()

        # Test with tags
        idea_data = {
            "title": "New Idea",
            "content": "This is a new idea",
            "tags": "tag1;tag2;tag3",
            "book_id": 1
        }

        response = client.post("/ideas", json=idea_data, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data

        # Verify that add_idea was called with correct parameters (using email instead of owner_id)
        mock_add_idea.assert_called_once_with(
            "New Idea", "This is a new idea", owner_email="test@example.com", book_id=1
        )

        # Verify that tags were processed
        assert mock_add_tag.call_count == 3
        assert mock_add_relation.call_count == 3

    @patch('backend.main.add_idea')
    def test_create_idea_without_tags(self, mock_add_idea):
        """Test creating a new idea without tags"""
        # Mock the add_idea function to return an ID
        mock_add_idea.return_value = 1

        # Get authentication headers
        headers = self._get_auth_headers()

        # Test without tags but with book_id
        idea_data = {
            "title": "New Idea",
            "content": "This is a new idea",
            "book_id": 1
        }

        response = client.post("/ideas", json=idea_data, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
    
    @patch('backend.main.add_idea')
    def test_create_idea_missing_email_in_token(self, mock_add_idea):
        """Test creating an idea when email is missing from JWT token"""
        # Mock the add_idea function
        mock_add_idea.return_value = 1

        # Create a JWT token without email (malformed token)
        from backend.main import SECRET_KEY, ALGORITHM
        from jose import jwt
        from datetime import datetime, timedelta
        
        # Create a token with missing 'sub' field
        token = jwt.encode(
            {"exp": (datetime.utcnow() + timedelta(hours=1)).timestamp()},  # Missing 'sub'
            SECRET_KEY,
            algorithm=ALGORITHM
        )

        headers = {"Authorization": f"Bearer {token}"}
        idea_data = {
            "title": "New Idea",
            "content": "This is a new idea"
        }

        response = client.post("/ideas", json=idea_data, headers=headers)
        assert response.status_code == 401  # Unauthorized (JWT validation fails)
        data = response.json()
        assert "detail" in data
        assert "Could not validate credentials" in data["detail"]

    @patch('backend.main.add_tag')
    def test_create_tag(self, mock_add_tag):
        """Test creating a new tag"""
        # Get authentication headers
        headers = self._get_auth_headers()

        tag_data = {"name": "new-tag"}

        response = client.post("/tags", json=tag_data, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Tag 'new-tag' added successfully"
        mock_add_tag.assert_called_once_with("new-tag")

    @patch('backend.main.add_relation')
    def test_create_relation(self, mock_add_relation):
        """Test creating a new relation"""
        # Get authentication headers
        headers = self._get_auth_headers()

        relation_data = {
            "idea_id": 1,
            "tag_name": "test-tag"
        }

        response = client.post("/relations", json=relation_data, headers=headers)
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
        # Get authentication headers
        headers = self._get_auth_headers()

        # Mock the get_tags_from_idea function
        mock_get_tags_from_idea.return_value = ["old-tag1", "old-tag2"]

        # Test with updated tags
        idea_data = {
            "id": 1,
            "title": "Updated Idea",
            "content": "Updated content",
            "tags": "new-tag1;new-tag2",
            "book_id": 1
        }

        response = client.put("/ideas/1", json=idea_data, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Idea '1' updated successfully"

        # Verify that update_idea was called
        mock_update_idea.assert_called_once_with(id=1, title="Updated Idea", content="Updated content")

    @patch('backend.main.remove_idea')
    def test_delete_idea(self, mock_remove_idea):
        """Test deleting an idea"""
        # Get authentication headers
        headers = self._get_auth_headers()

        # DELETE endpoints with Pydantic models - use json parameter
        # Note: TestClient.delete() doesn't support json parameter directly
        # We need to use a workaround by sending the data as part of the request
        response = client.request(
            "DELETE",
            "/ideas/1",
            json={
                "id": 1,
                "title": "Idea to Delete",
                "content": "Content to delete",
                "book_id": 1
            },
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Idea '1' removed successfully"
        mock_remove_idea.assert_called_once_with(id=1, title="Idea to Delete")

    @patch('backend.main.remove_tag')
    def test_delete_tag(self, mock_remove_tag):
        """Test deleting a tag"""
        # Get authentication headers
        headers = self._get_auth_headers()
        response = client.delete("/tags/test-tag", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Tag 'test-tag' removed successfully"
        mock_remove_tag.assert_called_once_with("test-tag")

    @patch('backend.main.remove_relation')
    def test_delete_relation(self, mock_remove_relation):
        """Test deleting a relation"""
        # Get authentication headers
        headers = self._get_auth_headers()

        # DELETE endpoints with Pydantic models - use json parameter
        # Note: TestClient.delete() doesn't support json parameter directly
        # We need to use a workaround by sending the data as part of the request
        response = client.request(
            "DELETE",
            "/relations",
            json={
                "idea_id": 1,
                "tag_name": "test-tag"
            },
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        mock_remove_relation.assert_called_once_with(1, "test-tag")

    @patch('backend.main.verify_access')
    def test_verify_otp_success(self, mock_verify_access):
        """Test OTP verification success with JWT token"""
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
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # Verify the token is a valid JWT (can be decoded)
        from jose import jwt
        from backend.main import SECRET_KEY, ALGORITHM

        token = data["access_token"]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            assert payload["sub"] == "test@example.com"
            assert "exp" in payload
        except Exception as e:
            pytest.fail(f"JWT token is invalid: {str(e)}")

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

    @patch('backend.main.DataSimilarity')
    def test_get_toc_structure_from_cache(self, mock_data_similarity):
        """Test getting TOC structure from cache"""
        # Get authentication headers
        headers = self._get_auth_headers()

        # Mock the DataSimilarity instance
        mock_instance = Mock()
        mock_instance.load_toc_structure.return_value = [
            {"title": "Section 1", "type": "heading", "children": []}
        ]
        mock_instance.generate_toc_structure.return_value = []
        mock_data_similarity.return_value = mock_instance

        response = client.get("/toc/structure", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Section 1"

        # Verify that load_toc_structure was called and generate_toc_structure was not
        mock_instance.load_toc_structure.assert_called_once()
        mock_instance.generate_toc_structure.assert_not_called()

    @patch('backend.main.DataSimilarity')
    def test_get_toc_structure_generate_new(self, mock_data_similarity):
        """Test generating new TOC structure when cache is empty"""
        # Get authentication headers
        headers = self._get_auth_headers()

        # Mock the DataSimilarity instance
        mock_instance = Mock()
        mock_instance.load_toc_structure.return_value = None  # No cache
        mock_instance.generate_toc_structure.return_value = [
            {"title": "New Section", "type": "heading", "children": []}
        ]
        mock_data_similarity.return_value = mock_instance

        response = client.get("/toc/structure", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "New Section"

        # Verify that both methods were called
        mock_instance.load_toc_structure.assert_called_once()
        mock_instance.generate_toc_structure.assert_called_once()

    @patch('backend.main.DataSimilarity')
    def test_update_toc_structure(self, mock_data_similarity):
        """Test updating TOC structure"""
        # Get authentication headers
        headers = self._get_auth_headers()

        # Mock the DataSimilarity class
        mock_instance = Mock()
        mock_instance.generate_toc_structure.return_value = [
            {"title": "Updated Section", "type": "heading", "children": []}
        ]
        mock_data_similarity.return_value = mock_instance

        response = client.post("/toc/update", headers=headers)
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
        # Get authentication headers
        headers = self._get_auth_headers()

        with patch('backend.main.get_ideas') as mock_get_ideas:
            # Mock the get_ideas function to raise an exception
            mock_get_ideas.side_effect = Exception("Database error")

            response = client.get("/ideas", headers=headers)
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert "Error retrieving data" in data["detail"]

    def test_error_handling_create_idea(self):
        """Test error handling in create_idea endpoint"""
        # Get authentication headers
        headers = self._get_auth_headers()

        with patch('backend.main.add_idea') as mock_add_idea:
            # Mock the add_idea function to raise an exception
            mock_add_idea.side_effect = Exception("Database error")

            idea_data = {
                "title": "New Idea",
                "content": "This is a new idea",
                "book_id": 1
            }

            response = client.post("/ideas", json=idea_data, headers=headers)
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert "Error adding idea" in data["detail"]

    def test_invalid_input_create_idea(self):
        """Test invalid input in create_idea endpoint"""
        # Get authentication headers
        headers = self._get_auth_headers()

        # Test with missing required fields
        idea_data = {
            "title": "New Idea"
            # Missing content
        }

        response = client.post("/ideas", json=idea_data, headers=headers)
        assert response.status_code == 422  # Validation error

    def test_invalid_input_create_tag(self):
        """Test invalid input in create_tag endpoint"""
        # Get authentication headers
        headers = self._get_auth_headers()

        # Test with missing required field
        tag_data = {}  # Missing name

        response = client.post("/tags", json=tag_data, headers=headers)
        assert response.status_code == 422  # Validation error

    @patch('backend.main.get_ideas')
    def test_get_all_ideas_with_jwt_auth(self, mock_get_ideas):
        """Test getting all ideas with JWT authentication"""
        # Mock the get_ideas function to return test data
        mock_get_ideas.return_value = [
            {"id": 1, "title": "Test Idea 1", "content": "Content 1", "tags": "tag1"},
            {"id": 2, "title": "Test Idea 2", "content": "Content 2", "tags": "tag2"}
        ]

        # First, get a JWT token
        with patch('backend.main.verify_access') as mock_verify_access:
            mock_verify_access.return_value = True
            login_data = {
                "email": "test@example.com",
                "otp_code": "123456"
            }
            login_response = client.post("/verify-otp", json=login_data)
            token = login_response.json()["access_token"]

        # Now test the protected endpoint with the token
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/ideas", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["title"] == "Test Idea 1"

    @patch('backend.main.get_ideas')
    def test_get_all_ideas_without_jwt_auth(self, mock_get_ideas):
        """Test getting all ideas without JWT authentication (should fail)"""
        # Mock the get_ideas function
        mock_get_ideas.return_value = []

        # Test without authentication
        response = client.get("/ideas")
        assert response.status_code == 401  # Unauthorized
        data = response.json()
        assert "detail" in data
        # The error message can be either "Could not validate credentials" or "Not authenticated"
        assert "validate credentials" in data["detail"] or "Not authenticated" in data["detail"]

    @patch('backend.main.add_idea')
    @patch('backend.main.add_tag')
    @patch('backend.main.add_relation')
    def test_create_idea_with_jwt_auth(self, mock_add_relation, mock_add_tag, mock_add_idea):
        """Test creating an idea with JWT authentication"""
        # Mock the add_idea function to return an ID
        mock_add_idea.return_value = 1

        # First, get a JWT token
        with patch('backend.main.verify_access') as mock_verify_access:
            mock_verify_access.return_value = True
            login_data = {
                "email": "test@example.com",
                "otp_code": "123456"
            }
            login_response = client.post("/verify-otp", json=login_data)
            token = login_response.json()["access_token"]

        # Now test the protected endpoint with the token
        headers = {"Authorization": f"Bearer {token}"}
        idea_data = {
            "title": "New Idea",
            "content": "This is a new idea",
            "tags": "tag1;tag2",
            "book_id": 1
        }

        response = client.post("/ideas", json=idea_data, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data

    @patch('backend.main.add_idea')
    def test_create_idea_without_jwt_auth(self, mock_add_idea):
        """Test creating an idea without JWT authentication (should fail)"""
        # Mock the add_idea function
        mock_add_idea.return_value = 1

        # Test without authentication
        idea_data = {
            "title": "New Idea",
            "content": "This is a new idea"
        }

        response = client.post("/ideas", json=idea_data)
        assert response.status_code == 401  # Unauthorized
        data = response.json()
        assert "detail" in data
        # The error message can be either "Could not validate credentials" or "Not authenticated"
        assert "validate credentials" in data["detail"] or "Not authenticated" in data["detail"]

    def test_jwt_token_expiration(self):
        """Test JWT token expiration"""
        from backend.main import create_access_token
        from datetime import timedelta

        # Create a token that expired 1 hour ago
        expired_token = create_access_token(
            {"sub": "test@example.com"},
            expires_delta=timedelta(minutes=-60)
        )

        # Test that the expired token is rejected
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/ideas", headers=headers)
        assert response.status_code == 401  # Unauthorized
        data = response.json()
        assert "detail" in data
        assert "Could not validate credentials" in data["detail"]

    def test_invalid_jwt_token(self):
        """Test with invalid JWT token"""
        # Use an invalid token
        invalid_token = "invalid.token.here"

        headers = {"Authorization": f"Bearer {invalid_token}"}
        response = client.get("/ideas", headers=headers)
        assert response.status_code == 401  # Unauthorized
        data = response.json()
        assert "detail" in data
        assert "Could not validate credentials" in data["detail"]

    def test_malformed_jwt_token(self):
        """Test with malformed JWT token"""
        # Use a malformed token (missing parts)
        malformed_token = "invalid.token"

        headers = {"Authorization": f"Bearer {malformed_token}"}
        response = client.get("/ideas", headers=headers)
        assert response.status_code == 401  # Unauthorized
        data = response.json()
        assert "detail" in data
        assert "Could not validate credentials" in data["detail"]

    def test_missing_authorization_header(self):
        """Test with missing Authorization header"""
        # Test without Authorization header
        response = client.get("/ideas")
        assert response.status_code == 401  # Unauthorized
        data = response.json()
        assert "detail" in data
        # The error message can be either "Could not validate credentials" or "Not authenticated"
        assert "validate credentials" in data["detail"] or "Not authenticated" in data["detail"]

    def test_wrong_authorization_scheme(self):
        """Test with wrong authorization scheme"""
        # Use wrong scheme (not Bearer)
        token = "some-token"
        headers = {"Authorization": f"Basic {token}"}

        response = client.get("/ideas", headers=headers)
        assert response.status_code == 401  # Unauthorized

    def test_jwt_token_with_different_email(self):
        """Test JWT token created for different email"""
        from backend.main import create_access_token
        from datetime import timedelta

        # Create a token for a different user
        token = create_access_token(
            {"sub": "different@example.com"},
            expires_delta=timedelta(minutes=30)
        )

        # The token should still be valid (we're not checking user identity in the endpoint)
        headers = {"Authorization": f"Bearer {token}"}
        with patch('backend.main.get_ideas') as mock_get_ideas:
            mock_get_ideas.return_value = []
            response = client.get("/ideas", headers=headers)
            assert response.status_code == 200

    def test_jwt_token_payload_structure(self):
        """Test JWT token payload structure"""
        from backend.main import create_access_token
        from datetime import timedelta, datetime
        from jose import jwt

        # Create a token
        token = create_access_token(
            {"sub": "test@example.com"},
            expires_delta=timedelta(minutes=30)
        )

        # Decode and verify the payload structure
        from backend.main import SECRET_KEY, ALGORITHM
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Verify required fields
        assert "sub" in payload
        assert payload["sub"] == "test@example.com"
        assert "exp" in payload

        # Verify expiration time is reasonable (within next 90 minutes to account for test timing)
        expire_time = datetime.utcfromtimestamp(payload["exp"])
        time_diff = expire_time - datetime.utcnow()
        assert time_diff.total_seconds() > 0  # Token should not be expired
        assert time_diff.total_seconds() < 5400  # Token should expire within 90 minutes

    def test_jwt_token_algorithm_validation(self):
        """Test JWT token algorithm validation"""
        from jose import jwt
        from backend.main import SECRET_KEY
        from datetime import datetime, timedelta

        # Create a token with wrong algorithm
        wrong_algorithm_token = jwt.encode(
            {"sub": "test@example.com", "exp": datetime.utcnow() + timedelta(hours=1)},
            SECRET_KEY,
            algorithm="HS512"  # Wrong algorithm
        )

        # Test that the token is rejected due to wrong algorithm
        headers = {"Authorization": f"Bearer {wrong_algorithm_token}"}
        response = client.get("/ideas", headers=headers)
        assert response.status_code == 401  # Unauthorized

    def test_multiple_jwt_protected_endpoints(self):
        """Test multiple JWT-protected endpoints"""
        # Get a JWT token first
        with patch('backend.main.verify_access') as mock_verify_access:
            mock_verify_access.return_value = True
            login_data = {
                "email": "test@example.com",
                "otp_code": "123456"
            }
            login_response = client.post("/verify-otp", json=login_data)
            token = login_response.json()["access_token"]

        headers = {"Authorization": f"Bearer {token}"}

        # Test multiple protected endpoints
        with patch('backend.main.get_ideas') as mock_get_ideas:
            with patch('backend.main.get_idea_from_tags') as mock_get_ideas_by_tags:
                with patch('backend.main.get_tags') as mock_get_tags:
                    # Mock the functions
                    mock_get_ideas.return_value = [{"id": 1, "title": "Test", "content": "Content", "tags": "tag1"}]
                    mock_get_ideas_by_tags.return_value = [
                        {"id": 1, "title": "Test", "content": "Content", "tags": "tag1"}
                    ]
                    mock_get_tags.return_value = [{"name": "tag1"}]

                    # Test GET /ideas
                    response = client.get("/ideas", headers=headers)
                    assert response.status_code == 200

                    # Test GET /ideas/tags/{tags}
                    response = client.get("/ideas/tags/tag1", headers=headers)
                    assert response.status_code == 200

                    # Test GET /tags
                    response = client.get("/tags", headers=headers)
                    assert response.status_code == 200

    def test_jwt_token_persistence_across_requests(self):
        """Test that JWT token works across multiple requests"""
        # Get a JWT token
        with patch('backend.main.verify_access') as mock_verify_access:
            mock_verify_access.return_value = True
            login_data = {
                "email": "test@example.com",
                "otp_code": "123456"
            }
            login_response = client.post("/verify-otp", json=login_data)
            token = login_response.json()["access_token"]

        headers = {"Authorization": f"Bearer {token}"}

        # Use the same token for multiple requests
        with patch('backend.main.get_ideas') as mock_get_ideas:
            with patch('backend.main.get_tags') as mock_get_tags:
                mock_get_ideas.return_value = [{"id": 1, "title": "Test", "content": "Content", "tags": "tag1"}]
                mock_get_tags.return_value = [{"name": "tag1"}]

                # First request
                response1 = client.get("/ideas", headers=headers)
                assert response1.status_code == 200

                # Second request with same token
                response2 = client.get("/tags", headers=headers)
                assert response2.status_code == 200

                # Third request with same token
                response3 = client.get("/ideas", headers=headers)
                assert response3.status_code == 200

    def test_jwt_token_with_special_characters_in_email(self):
        """Test JWT token with special characters in email"""
        from backend.main import create_access_token
        from datetime import timedelta
        from jose import jwt

        # Create a token with email containing special characters
        special_email = "user+test@example.com"
        token = create_access_token(
            {"sub": special_email},
            expires_delta=timedelta(minutes=30)
        )

        # Verify the token contains the email correctly
        from backend.main import SECRET_KEY, ALGORITHM
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == special_email

        # Test that the token works
        headers = {"Authorization": f"Bearer {token}"}
        with patch('backend.main.get_ideas') as mock_get_ideas:
            mock_get_ideas.return_value = []
            response = client.get("/ideas", headers=headers)
            assert response.status_code == 200

    @patch('backend.main.get_user_ideas')
    def test_get_user_ideas(self, mock_get_user_ideas):
        """Test getting ideas for the current user"""
        # Get authentication headers
        headers = self._get_auth_headers()

        # Mock the get_user_ideas function to return test data
        # Note: tags should be strings, not lists, to match the Pydantic model
        mock_get_user_ideas.return_value = [
            {"id": 1, "title": "User Idea 1", "content": "Content 1", "tags": "tag1"},
            {"id": 2, "title": "User Idea 2", "content": "Content 2", "tags": "tag2"}
        ]

        response = client.get("/user/ideas", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["title"] == "User Idea 1"

        # Verify that get_user_ideas was called with the current user email
        mock_get_user_ideas.assert_called_once_with("test@example.com")

    @patch('backend.main.get_user_ideas')
    def test_get_user_ideas_empty_result(self, mock_get_user_ideas):
        """Test getting ideas for a user with no ideas"""
        # Get authentication headers
        headers = self._get_auth_headers()

        # Mock the get_user_ideas function to return empty list
        mock_get_user_ideas.return_value = []

        response = client.get("/user/ideas", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

        # Verify that get_user_ideas was called
        mock_get_user_ideas.assert_called_once()

    @patch('backend.main.get_user_ideas')
    def test_get_user_ideas_with_tags(self, mock_get_user_ideas):
        """Test getting user ideas with tags"""
        # Get authentication headers
        headers = self._get_auth_headers()

        # Mock the get_user_ideas function to return data with tags
        # Note: tags should be strings, not lists, to match the Pydantic model
        mock_get_user_ideas.return_value = [
            {"id": 1, "title": "User Idea", "content": "Content", "tags": "tag1;tag2"}
        ]

        response = client.get("/user/ideas", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["tags"] == "tag1;tag2"

        # Verify that get_user_ideas was called
        mock_get_user_ideas.assert_called_once()

    @patch('backend.main.get_user_ideas')
    def test_get_user_ideas_error_handling(self, mock_get_user_ideas):
        """Test error handling in get_user_ideas endpoint"""
        # Get authentication headers
        headers = self._get_auth_headers()

        # Mock the get_user_ideas function to raise an exception
        mock_get_user_ideas.side_effect = Exception("Database error")

        response = client.get("/user/ideas", headers=headers)
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Error retrieving data" in data["detail"]

        # Verify that get_user_ideas was called
        mock_get_user_ideas.assert_called_once()


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def _get_auth_headers(self):
        """Helper method to get authentication headers with valid JWT token"""
        # First, we need to verify OTP to get a token
        login_data = {
            "email": "test@example.com",
            "otp_code": "123456"  # Any code, since we're mocking verify_access
        }

        # Mock verify_access to return True
        with patch('backend.main.verify_access', return_value=True):
            response = client.post("/verify-otp", json=login_data)
            assert response.status_code == 200
            token = response.json()["access_token"]

            return {"Authorization": f"Bearer {token}"}

    def test_empty_tags_list(self):
        """Test handling of empty tags list"""
        # Get authentication headers
        headers = self._get_auth_headers()

        with patch('backend.main.add_idea') as mock_add_idea:
            mock_add_idea.return_value = 1

            idea_data = {
                "title": "Idea with Empty Tags",
                "content": "Content",
                "tags": "",
                "book_id": 1
            }

            response = client.post("/ideas", json=idea_data, headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert "id" in data

    def test_whitespace_tags(self):
        """Test handling of tags with whitespace"""
        # Get authentication headers
        headers = self._get_auth_headers()

        with patch('backend.main.add_idea') as mock_add_idea:
            with patch('backend.main.add_tag') as mock_add_tag:
                with patch('backend.main.add_relation'):
                    mock_add_idea.return_value = 1

                    idea_data = {
                        "title": "Idea with Whitespace Tags",
                        "content": "Content",
                        "tags": "  tag1  ;  tag2  ;  tag3  ",
                        "book_id": 1
                    }

                    response = client.post("/ideas", json=idea_data, headers=headers)
                    assert response.status_code == 200

                    # Verify that tags were processed correctly (whitespace stripped)
                    assert mock_add_tag.call_count == 3

    def test_special_characters_in_tags(self):
        """Test handling of special characters in tags"""
        # Get authentication headers
        headers = self._get_auth_headers()

        with patch('backend.main.add_idea') as mock_add_idea:
            with patch('backend.main.add_tag') as mock_add_tag:
                with patch('backend.main.add_relation'):
                    mock_add_idea.return_value = 1

                    idea_data = {
                        "title": "Idea with Special Tags",
                        "content": "Content",
                        "tags": "tag-1;tag_2;tag.3;tag@4",
                        "book_id": 1
                    }

                    response = client.post("/ideas", json=idea_data, headers=headers)
                    assert response.status_code == 200

                    # Verify that all tags were processed
                    assert mock_add_tag.call_count == 4

    def test_duplicate_tags(self):
        """Test handling of duplicate tags"""
        # Get authentication headers
        headers = self._get_auth_headers()

        with patch('backend.main.add_idea') as mock_add_idea:
            with patch('backend.main.add_tag') as mock_add_tag:
                with patch('backend.main.add_relation'):
                    mock_add_idea.return_value = 1

                    idea_data = {
                        "title": "Idea with Duplicate Tags",
                        "content": "Content",
                        "tags": "tag1;tag2;tag1;tag3;tag2",
                        "book_id": 1
                    }

                    response = client.post("/ideas", json=idea_data, headers=headers)
                    assert response.status_code == 200

                    # Verify that all tags were processed (including duplicates)
                    assert mock_add_tag.call_count == 5

    def test_long_content(self):
        """Test handling of very long content"""
        # Get authentication headers
        headers = self._get_auth_headers()

        with patch('backend.main.add_idea') as mock_add_idea:
            mock_add_idea.return_value = 1

            # Create a very long content string
            long_content = "A" * 10000

            idea_data = {
                "title": "Idea with Long Content",
                "content": long_content,
                "book_id": 1
            }

            response = client.post("/ideas", json=idea_data, headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert "id" in data

    def test_special_characters_in_title(self):
        """Test handling of special characters in title"""
        # Get authentication headers
        headers = self._get_auth_headers()

        with patch('backend.main.add_idea') as mock_add_idea:
            mock_add_idea.return_value = 1

            idea_data = {
                "title": "Idea with Special Chars: / \\ | ? * < >",
                "content": "Content",
                "book_id": 1
            }

            response = client.post("/ideas", json=idea_data, headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert "id" in data

    def test_unicode_characters(self):
        """Test handling of unicode characters"""
        # Get authentication headers
        headers = self._get_auth_headers()

        with patch('backend.main.add_idea') as mock_add_idea:
            mock_add_idea.return_value = 1

            idea_data = {
                "title": "Idea with Unicode: 你好世界 🌍",
                "content": "Content with unicode: café, naïve, résumé",
                "book_id": 1
            }

            response = client.post("/ideas", json=idea_data, headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert "id" in data

    def test_empty_search(self):
        """Test searching with empty string"""
        # Get authentication headers
        headers = self._get_auth_headers()

        with patch('backend.main.get_similar_idea') as mock_get_similar_idea:
            mock_get_similar_idea.return_value = []

            # The endpoint expects a path parameter, so we need to provide a valid search term
            response = client.get("/ideas/search/empty", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert data == []

    def test_search_with_special_chars(self):
        """Test searching with special characters"""
        # Get authentication headers
        headers = self._get_auth_headers()

        with patch('backend.main.get_similar_idea') as mock_get_similar_idea:
            # Note: tags should be strings, not lists, to match the Pydantic model
            mock_get_similar_idea.return_value = [
                {"id": 1, "title": "Test Idea", "content": "Content", "tags": "tag1"}
            ]

            response = client.get("/ideas/search/test?query=special", headers=headers)
            assert response.status_code == 200

    def test_get_nonexistent_idea_content(self):
        """Test getting content for non-existent idea"""
        # Get authentication headers
        headers = self._get_auth_headers()

        with patch('backend.main.get_content') as mock_get_content:
            # Mock the get_content function to raise an exception
            mock_get_content.side_effect = Exception("Idea not found")

            response = client.get("/ideas/999999/content", headers=headers)
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data

    def test_update_nonexistent_idea(self):
        """Test updating non-existent idea"""
        # Get authentication headers
        headers = self._get_auth_headers()

        with patch('backend.main.update_idea') as mock_update_idea:
            # Mock the update_idea function to raise an exception
            mock_update_idea.side_effect = Exception("Idea not found")

            idea_data = {
                "id": 999999,
                "title": "Updated Idea",
                "content": "Updated content"
            }

            response = client.put("/ideas/999999", json=idea_data, headers=headers)
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data

    def test_delete_nonexistent_idea(self):
        """Test deleting non-existent idea"""
        # Get authentication headers
        headers = self._get_auth_headers()

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
                },
                headers=headers
            )
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data

    def test_delete_nonexistent_tag(self):
        """Test deleting non-existent tag"""
        # Get authentication headers
        headers = self._get_auth_headers()
        with patch('backend.main.remove_tag') as mock_remove_tag:
            # Mock the remove_tag function to raise an exception
            mock_remove_tag.side_effect = Exception("Tag not found")

            response = client.delete("/tags/nonexistent-tag", headers=headers)
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


@pytest.mark.unit
class TestBookAPI:
    """Unit tests for book and book-author endpoints."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        import tempfile
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.test_db = self._tmp.name
        self._tmp.close()
        os.environ["NAME_DB"] = self.test_db

        from backend.data_handler import init_database
        init_database()

        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)",
            ("testuser", "test@example.com", "hashed_password"),
        )
        self.user_id = cursor.lastrowid
        conn.commit()
        conn.close()

    def teardown_method(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def _get_auth_headers(self):
        login_data = {"email": "test@example.com", "otp_code": "123456"}
        with patch("backend.main.verify_access", return_value=True):
            response = client.post("/verify-otp", json=login_data)
            assert response.status_code == 200
            token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    # ----- GET /books -----

    @patch("backend.main.get_books")
    def test_get_all_books(self, mock_get_books):
        """GET /books returns list of books."""
        mock_get_books.return_value = [
            {"id": 1, "title": "Book One"},
            {"id": 2, "title": "Book Two"},
        ]
        headers = self._get_auth_headers()
        response = client.get("/books", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["title"] == "Book One"

    @patch("backend.main.get_books")
    def test_get_all_books_empty(self, mock_get_books):
        """GET /books returns empty list when no books exist."""
        mock_get_books.return_value = []
        headers = self._get_auth_headers()
        response = client.get("/books", headers=headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_get_books_requires_auth(self):
        """GET /books returns 401 without a token."""
        response = client.get("/books")
        assert response.status_code == 401

    @patch("backend.main.get_books")
    def test_get_books_error_handling(self, mock_get_books):
        """GET /books returns 500 on unexpected error."""
        mock_get_books.side_effect = Exception("DB error")
        headers = self._get_auth_headers()
        response = client.get("/books", headers=headers)
        assert response.status_code == 500
        assert "Error retrieving books" in response.json()["detail"]

    # ----- POST /books -----

    @patch("backend.main.add_book")
    def test_create_book(self, mock_add_book):
        """POST /books creates a book and returns its id."""
        mock_add_book.return_value = 42
        headers = self._get_auth_headers()
        response = client.post("/books", json={"title": "My New Book"}, headers=headers)
        assert response.status_code == 200
        assert response.json() == {"id": 42}
        mock_add_book.assert_called_once_with("My New Book")

    def test_create_book_requires_title(self):
        """POST /books with missing title returns 422."""
        headers = self._get_auth_headers()
        response = client.post("/books", json={}, headers=headers)
        assert response.status_code == 422

    def test_create_book_requires_auth(self):
        """POST /books returns 401 without a token."""
        response = client.post("/books", json={"title": "No Auth"})
        assert response.status_code == 401

    @patch("backend.main.add_book")
    def test_create_book_error_handling(self, mock_add_book):
        """POST /books returns 500 on unexpected error."""
        mock_add_book.side_effect = Exception("DB error")
        headers = self._get_auth_headers()
        response = client.post("/books", json={"title": "Bad Book"}, headers=headers)
        assert response.status_code == 500
        assert "Error creating book" in response.json()["detail"]

    # ----- DELETE /books/{id} -----

    @patch("backend.main.remove_book")
    def test_delete_book(self, mock_remove_book):
        """DELETE /books/{id} removes the book."""
        headers = self._get_auth_headers()
        response = client.delete("/books/7", headers=headers)
        assert response.status_code == 200
        assert response.json() == {"message": "Book '7' removed successfully"}
        mock_remove_book.assert_called_once_with(7)

    def test_delete_book_requires_auth(self):
        """DELETE /books/{id} returns 401 without a token."""
        response = client.delete("/books/1")
        assert response.status_code == 401

    @patch("backend.main.remove_book")
    def test_delete_book_error_handling(self, mock_remove_book):
        """DELETE /books/{id} returns 500 on unexpected error."""
        mock_remove_book.side_effect = Exception("DB error")
        headers = self._get_auth_headers()
        response = client.delete("/books/1", headers=headers)
        assert response.status_code == 500
        assert "Error removing book" in response.json()["detail"]

    # ----- GET /books/{id}/authors -----

    @patch("backend.main.get_book_authors")
    def test_get_book_authors(self, mock_get_book_authors):
        """GET /books/{id}/authors returns the author list."""
        mock_get_book_authors.return_value = [
            {"id": 1, "username": "alice", "email": "alice@example.com"},
            {"id": 2, "username": "bob", "email": "bob@example.com"},
        ]
        headers = self._get_auth_headers()
        response = client.get("/books/3/authors", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["email"] == "alice@example.com"
        mock_get_book_authors.assert_called_once_with(3)

    @patch("backend.main.get_book_authors")
    def test_get_book_authors_empty(self, mock_get_book_authors):
        """GET /books/{id}/authors returns empty list when no authors."""
        mock_get_book_authors.return_value = []
        headers = self._get_auth_headers()
        response = client.get("/books/5/authors", headers=headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_get_book_authors_requires_auth(self):
        """GET /books/{id}/authors returns 401 without a token."""
        response = client.get("/books/1/authors")
        assert response.status_code == 401

    @patch("backend.main.get_book_authors")
    def test_get_book_authors_error_handling(self, mock_get_book_authors):
        """GET /books/{id}/authors returns 500 on unexpected error."""
        mock_get_book_authors.side_effect = Exception("DB error")
        headers = self._get_auth_headers()
        response = client.get("/books/1/authors", headers=headers)
        assert response.status_code == 500
        assert "Error retrieving book authors" in response.json()["detail"]

    # ----- POST /book-authors -----

    @patch("backend.main.add_book_author")
    def test_add_book_author(self, mock_add_book_author):
        """POST /book-authors links a user to a book."""
        headers = self._get_auth_headers()
        response = client.post(
            "/book-authors", json={"book_id": 2, "user_id": 5}, headers=headers
        )
        assert response.status_code == 200
        assert response.json() == {"message": "User '5' added as author of book '2'"}
        mock_add_book_author.assert_called_once_with(2, 5)

    def test_add_book_author_requires_auth(self):
        """POST /book-authors returns 401 without a token."""
        response = client.post("/book-authors", json={"book_id": 1, "user_id": 1})
        assert response.status_code == 401

    def test_add_book_author_validation(self):
        """POST /book-authors with missing fields returns 422."""
        headers = self._get_auth_headers()
        response = client.post("/book-authors", json={"book_id": 1}, headers=headers)
        assert response.status_code == 422

    @patch("backend.main.add_book_author")
    def test_add_book_author_error_handling(self, mock_add_book_author):
        """POST /book-authors returns 500 on unexpected error."""
        mock_add_book_author.side_effect = Exception("DB error")
        headers = self._get_auth_headers()
        response = client.post(
            "/book-authors", json={"book_id": 1, "user_id": 1}, headers=headers
        )
        assert response.status_code == 500
        assert "Error adding book author" in response.json()["detail"]

    # ----- DELETE /book-authors -----

    @patch("backend.main.remove_book_author")
    def test_remove_book_author(self, mock_remove_book_author):
        """DELETE /book-authors unlinks a user from a book."""
        headers = self._get_auth_headers()
        response = client.request(
            "DELETE", "/book-authors", json={"book_id": 2, "user_id": 5}, headers=headers
        )
        assert response.status_code == 200
        assert response.json() == {"message": "User '5' removed from authors of book '2'"}
        mock_remove_book_author.assert_called_once_with(2, 5)

    def test_remove_book_author_requires_auth(self):
        """DELETE /book-authors returns 401 without a token."""
        response = client.request(
            "DELETE", "/book-authors", json={"book_id": 1, "user_id": 1}
        )
        assert response.status_code == 401

    @patch("backend.main.remove_book_author")
    def test_remove_book_author_error_handling(self, mock_remove_book_author):
        """DELETE /book-authors returns 500 on unexpected error."""
        mock_remove_book_author.side_effect = Exception("DB error")
        headers = self._get_auth_headers()
        response = client.request(
            "DELETE", "/book-authors", json={"book_id": 1, "user_id": 1}, headers=headers
        )
        assert response.status_code == 500
        assert "Error removing book author" in response.json()["detail"]


@pytest.mark.unit
class TestUsersAPI:
    """Unit tests for the GET /users endpoint."""

    def setup_method(self):
        import tempfile
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.test_db = self._tmp.name
        self._tmp.close()
        os.environ["NAME_DB"] = self.test_db
        from backend.data_handler import init_database
        init_database()
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)",
            ("testuser", "test@example.com", "hashed_password"),
        )
        conn.commit()
        conn.close()

    def teardown_method(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def _get_auth_headers(self):
        login_data = {"email": "test@example.com", "otp_code": "123456"}
        with patch("backend.main.verify_access", return_value=True):
            response = client.post("/verify-otp", json=login_data)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    @patch("backend.main.get_users")
    def test_get_all_users_returns_list(self, mock_get_users):
        mock_get_users.return_value = [
            {"id": 1, "username": "alice", "email": "alice@example.com"},
            {"id": 2, "username": "bob",   "email": "bob@example.com"},
        ]
        headers = self._get_auth_headers()
        response = client.get("/users", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["username"] == "alice"
        assert data[1]["email"] == "bob@example.com"

    @patch("backend.main.get_users")
    def test_get_all_users_empty(self, mock_get_users):
        mock_get_users.return_value = []
        headers = self._get_auth_headers()
        response = client.get("/users", headers=headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_get_all_users_requires_auth(self):
        response = client.get("/users")
        assert response.status_code == 401

    @patch("backend.main.get_users")
    def test_get_all_users_error_handling(self, mock_get_users):
        mock_get_users.side_effect = Exception("DB failure")
        headers = self._get_auth_headers()
        response = client.get("/users", headers=headers)
        assert response.status_code == 500
        assert "Error retrieving users" in response.json()["detail"]
