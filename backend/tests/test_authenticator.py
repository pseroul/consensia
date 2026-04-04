import sys
import os
from unittest.mock import Mock, patch
import pytest
import sqlite3

# Add the backend directory to the path so we can import authenticator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.authenticator import generate_auth_link, verify_access
from backend.data_handler import init_database


@pytest.mark.unit
class TestAuthenticator:
    """Test cases for authenticator functions"""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        import tempfile
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.test_db_path = self._tmp.name
        self._tmp.close()
        os.environ['NAME_DB'] = self.test_db_path
        init_database()

    def teardown_method(self):
        """Clean up after each test method."""
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    @patch('backend.authenticator.pyotp')
    def test_generate_auth_link(self, mock_pyotp):
        """Test generate_auth_link function"""
        # Set up mock for pyotp functions
        mock_pyotp.random_base32.return_value = "TEST_SECRET_BASE32"
        mock_totp = Mock()
        mock_totp.provisioning_uri.return_value = "otpauth://test/uri"
        mock_pyotp.TOTP.return_value = mock_totp
        
        # Call the function
        generate_auth_link("test@example.com", False)
        
        # Verify the user was inserted into the database
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT username, email, hashed_password FROM users WHERE email = ?", ("test@example.com",))
        result = cursor.fetchone()
        conn.close()
        
        assert result is not None
        assert result[0] == "test"  # username extracted from email
        assert result[1] == "test@example.com"
        assert result[2] == "TEST_SECRET_BASE32"
        
        # Verify pyotp functions were called correctly
        mock_pyotp.random_base32.assert_called_once()
        mock_pyotp.TOTP.assert_called_once_with("TEST_SECRET_BASE32")
        mock_totp.provisioning_uri.assert_called_once()

    @patch('backend.authenticator.pyotp')
    def test_generate_auth_link_debug(self, mock_pyotp):
        """Test generate_auth_link function with debug mode"""
        # Set up mock for pyotp functions
        mock_pyotp.random_base32.return_value = "TEST_SECRET_BASE32"
        mock_totp = Mock()
        mock_totp.provisioning_uri.return_value = "otpauth://test/uri"
        mock_pyotp.TOTP.return_value = mock_totp
        
        # Call the function with debug=True
        generate_auth_link("test@example.com", True)
        
        # Verify pyotp.TOTP was called with the secret
        mock_pyotp.TOTP.assert_called_once_with("TEST_SECRET_BASE32")
        
        # Verify provisioning_uri was called (should include "Brainiac5-dev" for debug)
        call_args = mock_totp.provisioning_uri.call_args
        assert call_args is not None

    @patch('backend.authenticator.pyotp')
    def test_verify_access_success(self, mock_pyotp):
        """Test verify_access function with valid credentials"""
        # Insert a test user into the database
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)",
            ("test", "test@example.com", "TEST_SECRET_BASE32")
        )
        conn.commit()
        conn.close()
        
        # Set up mock for pyotp
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_pyotp.TOTP.return_value = mock_totp
        
        # Call the function with valid credentials
        result = verify_access("test@example.com", "123456")
        
        # Verify the result is True
        assert result is True
        
        # Verify pyotp.TOTP was called with the correct secret
        mock_pyotp.TOTP.assert_called_once_with("TEST_SECRET_BASE32")
        
        # Verify verify was called with the correct code
        mock_totp.verify.assert_called_once_with("123456")

    @patch('backend.authenticator.pyotp')
    def test_verify_access_wrong_email(self, mock_pyotp):
        """Test verify_access function with wrong email"""
        # Insert a test user into the database
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)",
            ("correct", "correct@example.com", "TEST_SECRET_BASE32")
        )
        conn.commit()
        conn.close()
        
        # Set up mock for pyotp
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_pyotp.TOTP.return_value = mock_totp
        
        # Call the function with wrong email
        result = verify_access("wrong@example.com", "123456")
        
        # Verify the result is False (email doesn't match)
        assert result is False

    @patch('backend.authenticator.pyotp')
    def test_verify_access_wrong_code(self, mock_pyotp):
        """Test verify_access function with wrong OTP code"""
        # Insert a test user into the database
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)",
            ("test", "test@example.com", "TEST_SECRET_BASE32")
        )
        conn.commit()
        conn.close()
        
        # Set up mock for pyotp
        mock_totp = Mock()
        mock_totp.verify.return_value = False  # Wrong code
        mock_pyotp.TOTP.return_value = mock_totp
        
        # Call the function with wrong code
        result = verify_access("test@example.com", "wrongcode")
        
        # Verify the result is False (code verification failed)
        assert result is False

    def test_verify_access_user_not_found(self):
        """Test verify_access function when user doesn't exist"""
        # Call the function with non-existent user
        result = verify_access("nonexistent@example.com", "123456")
        
        # Verify the result is False
        assert result is False

    def test_verify_access_missing_secret(self):
        """Test verify_access function when user has no secret"""
        # Insert a test user with empty secret
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, hashed_password) VALUES (?, ?, ?)",
            ("test", "test@example.com", "")
        )
        conn.commit()
        conn.close()
        
        # Call the function - should return False due to empty secret
        # pyotp.TOTP will fail with empty secret
        result = verify_access("test@example.com", "123456")
        assert result is False

    @patch('backend.authenticator.pyotp')
    def test_multiple_users(self, mock_pyotp):
        """Test that multiple users can be stored and verified"""
        # Set up mock for pyotp functions
        mock_pyotp.random_base32.side_effect = ["SECRET1", "SECRET2", "SECRET3"]
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_totp.provisioning_uri.return_value = "otpauth://test/uri"
        mock_pyotp.TOTP.return_value = mock_totp
        
        # Create multiple users
        generate_auth_link("user1@example.com", False)
        generate_auth_link("user2@example.com", False)
        generate_auth_link("user3@example.com", False)
        
        # Verify all users were inserted
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count == 3
        
        # Verify each user can be accessed
        mock_totp.verify.return_value = True
        assert verify_access("user1@example.com", "123456") is True
        assert verify_access("user2@example.com", "123456") is True
        assert verify_access("user3@example.com", "123456") is True

    @patch('backend.authenticator.pyotp')
    def test_duplicate_username_prevention(self, mock_pyotp):
        """Test that duplicate usernames are prevented"""
        # Set up mock for pyotp functions
        mock_pyotp.random_base32.return_value = "SECRET1"
        mock_totp = Mock()
        mock_totp.provisioning_uri.return_value = "otpauth://test/uri"
        mock_pyotp.TOTP.return_value = mock_totp
        
        # Create first user
        generate_auth_link("test@example.com", False)
        
        # Try to create second user with same username (same email)
        generate_auth_link("test@example.com", False)
        
        # Verify only one user exists
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", ("test",))
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count == 1
