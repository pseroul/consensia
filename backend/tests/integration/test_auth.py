"""
Integration tests for the authentication flow.

Tests the full chain without mocking verify_access:
  real TOTP secret → real pyotp.TOTP.verify() → real JWT issued → real JWT decoded

Contracts asserted:
- A valid OTP yields a well-formed JWT in the response body.
- An invalid OTP yields 401.
- Every protected endpoint rejects requests with no token, an invalid token,
  or an expired token.
- /health is accessible without any token.
- The JWT payload's "sub" claim carries the user's email.
"""

import pytest
import pyotp
from datetime import timedelta
from jose import jwt

from tests.integration.conftest import (
    create_db_user,
    auth_headers,
)
from backend.main import SECRET_KEY, ALGORITHM


@pytest.mark.integration
class TestOtpLogin:
    def test_valid_otp_returns_access_token(self, client, db_path):
        email = "login_user@example.com"
        secret = create_db_user(db_path, email)
        valid_code = pyotp.TOTP(secret).now()

        response = client.post("/verify-otp", json={"email": email, "otp_code": valid_code})

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    def test_valid_otp_token_contains_email_as_sub(self, client, db_path):
        email = "sub_check@example.com"
        secret = create_db_user(db_path, email)
        valid_code = pyotp.TOTP(secret).now()

        response = client.post("/verify-otp", json={"email": email, "otp_code": valid_code})

        token = response.json()["access_token"]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == email

    def test_invalid_otp_returns_401(self, client, db_path):
        email = "invalid_otp@example.com"
        create_db_user(db_path, email)

        response = client.post("/verify-otp", json={"email": email, "otp_code": "000000"})

        assert response.status_code == 401

    def test_unknown_email_returns_401(self, client):
        response = client.post(
            "/verify-otp",
            json={"email": "ghost@example.com", "otp_code": "123456"},
        )
        assert response.status_code == 401


@pytest.mark.integration
class TestProtectedEndpoints:
    def test_health_check_needs_no_token(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_ideas_without_token_returns_401(self, client):
        response = client.get("/ideas")
        assert response.status_code == 401

    def test_user_ideas_without_token_returns_401(self, client):
        response = client.get("/user/ideas")
        assert response.status_code == 401

    def test_tags_without_token_returns_401(self, client):
        response = client.get("/tags")
        assert response.status_code == 401

    def test_invalid_token_returns_401(self, client):
        headers = {"Authorization": "Bearer this.is.not.a.valid.token"}
        response = client.get("/ideas", headers=headers)
        assert response.status_code == 401

    def test_expired_token_returns_401(self, client, alice):
        expired_headers = auth_headers(alice["email"], expires=timedelta(seconds=-1))
        response = client.get("/ideas", headers=expired_headers)
        assert response.status_code == 401

    def test_valid_token_grants_access_to_ideas(self, client, alice):
        response = client.get("/ideas", headers=alice["headers"])
        assert response.status_code == 200

    def test_valid_token_grants_access_to_tags(self, client, alice):
        response = client.get("/tags", headers=alice["headers"])
        assert response.status_code == 200
