import sys
import os
from unittest.mock import Mock, patch, mock_open, MagicMock
import json
import pytest

# Add the backend directory to the path so we can import authenticator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.authenticator import generate_auth_link, verify_access


class TestAuthenticator:
    """Test cases for authenticator functions"""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Set environment variable for user database path
        self.user_db_path = os.path.join(os.path.dirname(__file__), "test_user_db.json")
        os.environ['USER_DB'] = self.user_db_path

    def teardown_method(self):
        """Clean up after each test method."""
        # Remove the user database file if it exists
        if os.path.exists(self.user_db_path):
            os.remove(self.user_db_path)

    @patch('backend.authenticator.pyotp')
    @patch('backend.authenticator.os.getenv')
    def test_generate_auth_link(self, mock_getenv, mock_pyotp):
        """Test generate_auth_link function"""
        # Set up mock environment
        mock_getenv.return_value = self.user_db_path
        
        # Set up mock for pyotp functions
        mock_pyotp.random_base32.return_value = "TEST_SECRET_BASE32"
        mock_totp = Mock()
        mock_totp.provisioning_uri.return_value = "otpauth://test/uri"
        mock_pyotp.TOTP.return_value = mock_totp
        
        # Call the function
        generate_auth_link("test@example.com", False)
        
        # Verify the file was created and contains expected data
        assert os.path.exists(self.user_db_path)
        
        with open(self.user_db_path, 'r') as f:
            user_data = json.load(f)
            assert user_data["email"] == "test@example.com"
            assert user_data["otp_secret"] == "TEST_SECRET_BASE32"
        
        # Verify pyotp functions were called correctly
        mock_pyotp.random_base32.assert_called_once()
        mock_pyotp.TOTP.assert_called_once_with("TEST_SECRET_BASE32")
        mock_totp.provisioning_uri.assert_called_once()

    @patch('backend.authenticator.pyotp')
    @patch('backend.authenticator.os.getenv')
    def test_generate_auth_link_debug(self, mock_getenv, mock_pyotp):
        """Test generate_auth_link function with debug mode"""
        # Set up mock environment
        mock_getenv.return_value = self.user_db_path
        
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

    @patch('backend.authenticator.os.getenv')
    @patch('backend.authenticator.pyotp')
    def test_verify_access_success(self, mock_pyotp, mock_getenv):
        """Test verify_access function with valid credentials"""
        # Set up mock environment
        mock_getenv.return_value = self.user_db_path
        
        # Create a test user file
        test_user = {
            "email": "test@example.com",
            "otp_secret": "TEST_SECRET_BASE32"
        }
        with open(self.user_db_path, 'w') as f:
            json.dump(test_user, f)
        
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

    @patch('backend.authenticator.os.getenv')
    @patch('backend.authenticator.pyotp')
    def test_verify_access_wrong_email(self, mock_pyotp, mock_getenv):
        """Test verify_access function with wrong email"""
        # Set up mock environment
        mock_getenv.return_value = self.user_db_path
        
        # Create a test user file
        test_user = {
            "email": "correct@example.com",
            "otp_secret": "TEST_SECRET_BASE32"
        }
        with open(self.user_db_path, 'w') as f:
            json.dump(test_user, f)
        
        # Set up mock for pyotp
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_pyotp.TOTP.return_value = mock_totp
        
        # Call the function with wrong email
        result = verify_access("wrong@example.com", "123456")
        
        # Verify the result is False (email doesn't match)
        assert result is False

    @patch('backend.authenticator.os.getenv')
    @patch('backend.authenticator.pyotp')
    def test_verify_access_wrong_code(self, mock_pyotp, mock_getenv):
        """Test verify_access function with wrong OTP code"""
        # Set up mock environment
        mock_getenv.return_value = self.user_db_path
        
        # Create a test user file
        test_user = {
            "email": "test@example.com",
            "otp_secret": "TEST_SECRET_BASE32"
        }
        with open(self.user_db_path, 'w') as f:
            json.dump(test_user, f)
        
        # Set up mock for pyotp
        mock_totp = Mock()
        mock_totp.verify.return_value = False  # Wrong code
        mock_pyotp.TOTP.return_value = mock_totp
        
        # Call the function with wrong code
        result = verify_access("test@example.com", "wrongcode")
        
        # Verify the result is False (code verification failed)
        assert result is False

    @patch('backend.authenticator.os.getenv')
    def test_verify_access_file_not_found(self, mock_getenv):
        """Test verify_access function when user file doesn't exist"""
        # Set up mock environment to return non-existent file
        mock_getenv.return_value = "/non/existent/file.json"
        
        # Call the function - should raise FileNotFoundError
        with pytest.raises(FileNotFoundError):
            verify_access("test@example.com", "123456")

    @patch('backend.authenticator.os.getenv')
    def test_verify_access_invalid_json(self, mock_getenv):
        """Test verify_access function with invalid JSON in user file"""
        # Set up mock environment
        mock_getenv.return_value = self.user_db_path
        
        # Create a file with invalid JSON
        with open(self.user_db_path, 'w') as f:
            f.write("invalid json {{{")
        
        # Call the function - should raise JSONDecodeError
        with pytest.raises(json.JSONDecodeError):
            verify_access("test@example.com", "123456")

    @patch('backend.authenticator.os.getenv')
    @patch('backend.authenticator.pyotp')
    def test_verify_access_missing_fields(self, mock_pyotp, mock_getenv):
        """Test verify_access function with missing fields in user data"""
        # Set up mock environment
        mock_getenv.return_value = self.user_db_path
        
        # Create a user file with missing email field
        test_user = {
            "otp_secret": "TEST_SECRET_BASE32"
            # Missing email
        }
        with open(self.user_db_path, 'w') as f:
            json.dump(test_user, f)
        
        # Set up mock for pyotp
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_pyotp.TOTP.return_value = mock_totp
        
        # Call the function - should raise KeyError when accessing missing email field
        with pytest.raises(KeyError):
            verify_access("test@example.com", "123456")

    @patch('backend.authenticator.os.getenv')
    @patch('backend.authenticator.pyotp')
    def test_verify_access_missing_secret(self, mock_pyotp, mock_getenv):
        """Test verify_access function with missing secret in user data"""
        # Set up mock environment
        mock_getenv.return_value = self.user_db_path
        
        # Create a user file with missing otp_secret field
        test_user = {
            "email": "test@example.com"
            # Missing otp_secret
        }
        with open(self.user_db_path, 'w') as f:
            json.dump(test_user, f)
        
        # Set up mock for pyotp
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_pyotp.TOTP.return_value = mock_totp
        
        # Call the function - should raise KeyError when accessing missing secret
        with pytest.raises(KeyError):
            verify_access("test@example.com", "123456")


class TestEdgeCases:
    """Test edge cases and boundary conditions for authenticator"""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Set environment variable for user database path
        self.user_db_path = os.path.join(os.path.dirname(__file__), "test_user_db.json")
        os.environ['USER_DB'] = self.user_db_path

    def teardown_method(self):
        """Clean up after each test method."""
        # Remove the user database file if it exists
        if os.path.exists(self.user_db_path):
            os.remove(self.user_db_path)

    @patch('backend.authenticator.os.getenv')
    @patch('backend.authenticator.pyotp')
    def test_verify_access_empty_email(self, mock_pyotp, mock_getenv):
        """Test verify_access with empty email string"""
        # Set up mock environment
        mock_getenv.return_value = self.user_db_path
        
        # Create a test user file
        test_user = {
            "email": "test@example.com",
            "otp_secret": "TEST_SECRET_BASE32"
        }
        with open(self.user_db_path, 'w') as f:
            json.dump(test_user, f)
        
        # Set up mock for pyotp
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_pyotp.TOTP.return_value = mock_totp
        
        # Call with empty email
        result = verify_access("", "123456")
        assert result is False

    @patch('backend.authenticator.os.getenv')
    @patch('backend.authenticator.pyotp')
    def test_verify_access_empty_code(self, mock_pyotp, mock_getenv):
        """Test verify_access with empty OTP code"""
        # Set up mock environment
        mock_getenv.return_value = self.user_db_path
        
        # Create a test user file
        test_user = {
            "email": "test@example.com",
            "otp_secret": "TEST_SECRET_BASE32"
        }
        with open(self.user_db_path, 'w') as f:
            json.dump(test_user, f)
        
        # Set up mock for pyotp
        mock_totp = Mock()
        mock_totp.verify.return_value = False  # Empty code should fail
        mock_pyotp.TOTP.return_value = mock_totp
        
        # Call with empty code
        result = verify_access("test@example.com", "")
        assert result is False

    @patch('backend.authenticator.os.getenv')
    @patch('backend.authenticator.pyotp')
    def test_verify_access_special_chars_email(self, mock_pyotp, mock_getenv):
        """Test verify_access with special characters in email"""
        # Set up mock environment
        mock_getenv.return_value = self.user_db_path
        
        # Create a test user file with special characters in email
        test_user = {
            "email": "test+special@example.com",
            "otp_secret": "TEST_SECRET_BASE32"
        }
        with open(self.user_db_path, 'w') as f:
            json.dump(test_user, f)
        
        # Set up mock for pyotp
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_pyotp.TOTP.return_value = mock_totp
        
        # Call with matching email (including special characters)
        result = verify_access("test+special@example.com", "123456")
        assert result is True

    @patch('backend.authenticator.os.getenv')
    @patch('backend.authenticator.pyotp')
    def test_verify_access_long_code(self, mock_pyotp, mock_getenv):
        """Test verify_access with very long OTP code"""
        # Set up mock environment
        mock_getenv.return_value = self.user_db_path
        
        # Create a test user file
        test_user = {
            "email": "test@example.com",
            "otp_secret": "TEST_SECRET_BASE32"
        }
        with open(self.user_db_path, 'w') as f:
            json.dump(test_user, f)
        
        # Set up mock for pyotp
        mock_totp = Mock()
        mock_totp.verify.return_value = False  # Long code should fail
        mock_pyotp.TOTP.return_value = mock_totp
        
        # Call with very long code
        long_code = "A" * 100
        result = verify_access("test@example.com", long_code)
        assert result is False

    @patch('backend.authenticator.os.getenv')
    @patch('backend.authenticator.pyotp')
    def test_verify_access_unicode_email(self, mock_pyotp, mock_getenv):
        """Test verify_access with unicode characters in email"""
        # Set up mock environment
        mock_getenv.return_value = self.user_db_path
        
        # Create a test user file with unicode in email
        test_user = {
            "email": "test@example.com",
            "otp_secret": "TEST_SECRET_BASE32"
        }
        with open(self.user_db_path, 'w') as f:
            json.dump(test_user, f)
        
        # Set up mock for pyotp
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_pyotp.TOTP.return_value = mock_totp
        
        # Call with unicode in email (should fail to match)
        result = verify_access("tëst@example.com", "123456")
        assert result is False

    @patch('backend.authenticator.os.getenv')
    @patch('backend.authenticator.pyotp')
    def test_verify_access_case_sensitive_email(self, mock_pyotp, mock_getenv):
        """Test verify_access with case sensitivity in email"""
        # Set up mock environment
        mock_getenv.return_value = self.user_db_path
        
        # Create a test user file with specific case
        test_user = {
            "email": "Test@Example.com",
            "otp_secret": "TEST_SECRET_BASE32"
        }
        with open(self.user_db_path, 'w') as f:
            json.dump(test_user, f)
        
        # Set up mock for pyotp
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_pyotp.TOTP.return_value = mock_totp
        
        # Call with different case - should fail
        result = verify_access("test@example.com", "123456")
        assert result is False

    @patch('backend.authenticator.os.getenv')
    @patch('backend.authenticator.pyotp')
    def test_verify_access_numeric_code(self, mock_pyotp, mock_getenv):
        """Test verify_access with numeric OTP code"""
        # Set up mock environment
        mock_getenv.return_value = self.user_db_path
        
        # Create a test user file
        test_user = {
            "email": "test@example.com",
            "otp_secret": "TEST_SECRET_BASE32"
        }
        with open(self.user_db_path, 'w') as f:
            json.dump(test_user, f)
        
        # Set up mock for pyotp
        mock_totp = Mock()
        mock_totp.verify.return_value = True
        mock_pyotp.TOTP.return_value = mock_totp
        
        # Call with numeric code
        result = verify_access("test@example.com", "123456")
        assert result is True

    @patch('backend.authenticator.os.getenv')
    @patch('backend.authenticator.pyotp')
    def test_verify_access_alphanumeric_code(self, mock_pyotp, mock_getenv):
        """Test verify_access with alphanumeric OTP code"""
        # Set up mock environment
        mock_getenv.return_value = self.user_db_path
        
        # Create a test user file
        test_user = {
            "email": "test@example.com",
            "otp_secret": "TEST_SECRET_BASE32"
        }
        with open(self.user_db_path, 'w') as f:
            json.dump(test_user, f)
        
        # Set up mock for pyotp
        mock_totp = Mock()
        mock_totp.verify.return_value = False  # Alphanumeric should typically fail
        mock_pyotp.TOTP.return_value = mock_totp
        
        # Call with alphanumeric code
        result = verify_access("test@example.com", "ABC123")
        assert result is False
