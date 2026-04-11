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
    make_token,
)
from backend.main import SECRET_KEY, ALGORITHM, REFRESH_TOKEN_EXPIRE_DAYS


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

    def test_valid_otp_returns_refresh_token(self, client, db_path):
        email = "refresh_user@example.com"
        secret = create_db_user(db_path, email)
        valid_code = pyotp.TOTP(secret).now()

        response = client.post("/verify-otp", json={"email": email, "otp_code": valid_code})

        assert response.status_code == 200
        assert "refresh_token" in response.json()

    def test_valid_otp_access_token_has_type_access(self, client, db_path):
        email = "type_check_access@example.com"
        secret = create_db_user(db_path, email)
        valid_code = pyotp.TOTP(secret).now()

        response = client.post("/verify-otp", json={"email": email, "otp_code": valid_code})

        token = response.json()["access_token"]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["type"] == "access"

    def test_valid_otp_refresh_token_has_type_refresh(self, client, db_path):
        email = "type_check_refresh@example.com"
        secret = create_db_user(db_path, email)
        valid_code = pyotp.TOTP(secret).now()

        response = client.post("/verify-otp", json={"email": email, "otp_code": valid_code})

        token = response.json()["refresh_token"]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["type"] == "refresh"

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


# ---------------------------------------------------------------------------
# Helper: build a refresh token (uses the same signing key as the app)
# ---------------------------------------------------------------------------

def make_refresh_token(email: str, expires: timedelta = timedelta(days=7)) -> str:
    from backend.main import create_access_token
    return create_access_token(
        data={"sub": email},
        expires_delta=expires,
        jwt_kind="refresh",
    )


@pytest.mark.integration
class TestRefreshEndpoint:

    def test_valid_refresh_token_returns_new_access_token(self, client, alice):
        refresh_token = make_refresh_token(alice["email"])

        response = client.post("/auth/refresh", json={"refresh_token": refresh_token})

        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_valid_refresh_token_returns_new_refresh_token(self, client, alice):
        refresh_token = make_refresh_token(alice["email"])

        response = client.post("/auth/refresh", json={"refresh_token": refresh_token})

        assert response.status_code == 200
        assert "refresh_token" in response.json()

    def test_new_access_token_grants_access_to_ideas(self, client, alice):
        refresh_token = make_refresh_token(alice["email"])
        new_access = client.post(
            "/auth/refresh", json={"refresh_token": refresh_token}
        ).json()["access_token"]

        response = client.get(
            "/ideas",
            headers={"Authorization": f"Bearer {new_access}"},
        )
        assert response.status_code == 200

    def test_expired_refresh_token_returns_401(self, client, alice):
        expired = make_refresh_token(alice["email"], expires=timedelta(seconds=-1))

        response = client.post("/auth/refresh", json={"refresh_token": expired})

        assert response.status_code == 401

    def test_access_token_rejected_by_refresh_endpoint(self, client, alice):
        # An access token must not be accepted by /auth/refresh (type mismatch)
        access_token = make_token(alice["email"])

        response = client.post("/auth/refresh", json={"refresh_token": access_token})

        assert response.status_code == 401

    def test_refresh_token_rejected_by_protected_endpoints(self, client, alice):
        # A refresh token must not grant access to protected API endpoints
        refresh_token = make_refresh_token(alice["email"])

        response = client.get(
            "/ideas",
            headers={"Authorization": f"Bearer {refresh_token}"},
        )
        assert response.status_code == 401

    def test_refresh_without_body_returns_422(self, client):
        response = client.post("/auth/refresh")
        assert response.status_code == 422

    def test_refresh_with_garbage_token_returns_401(self, client):
        response = client.post(
            "/auth/refresh", json={"refresh_token": "not.a.jwt.token"}
        )
        assert response.status_code == 401

    def test_refresh_preserves_is_admin_claim(self, client, db_path):
        import sqlite3

        # Create an admin user
        email = "admin_refresh@example.com"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO users (username, email, hashed_password, is_admin) VALUES (?, ?, ?, ?)",
            ("admin_r", email, "secret", 1),
        )
        conn.commit()
        conn.close()

        from backend.main import create_access_token
        refresh_token = create_access_token(
            data={"sub": email, "is_admin": True},
            expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
            jwt_kind="refresh",
        )

        response = client.post("/auth/refresh", json={"refresh_token": refresh_token})

        assert response.status_code == 200
        new_access = response.json()["access_token"]
        payload = jwt.decode(new_access, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["is_admin"] is True
