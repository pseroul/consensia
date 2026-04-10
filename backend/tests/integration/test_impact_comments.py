"""
Integration tests for the impact comments feature.

Contracts asserted:
- GET /ideas/{idea_id}/impact-comments returns [] when no comments exist.
- POST /ideas/{idea_id}/impact-comments creates a comment for a book author.
- POST returns 403 when the user is not a book author.
- PUT /impact-comments/{comment_id} updates a comment owned by the user.
- PUT returns 403 when the user does not own the comment.
- DELETE /impact-comments/{comment_id} removes a comment owned by the user.
- DELETE removes any comment when the user is an admin.
- DELETE returns 403 when the user does not own the comment and is not admin.
- GET /books/{book_id}/impact-comments returns all comments for the book.
- Multiple users can comment on the same idea; all comments are visible to both.
- All endpoints return 401 without authentication.
"""

import sqlite3
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_user_id(db_path: str, email: str) -> int:
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row[0]


def _add_book_author(client, book_id: int, user_id: int, headers: dict) -> None:
    resp = client.post("/book-authors", json={"book_id": book_id, "user_id": user_id}, headers=headers)
    assert resp.status_code == 200


def _create_idea(client, book_id: int, headers: dict, title: str = "Test Idea") -> int:
    resp = client.post(
        "/ideas",
        json={"title": title, "content": "Some content", "book_id": book_id},
        headers=headers,
    )
    assert resp.status_code == 200
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# GET /ideas/{idea_id}/impact-comments
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestGetImpactComments:
    def test_get_comments_empty(self, client, alice, book, db_path):
        alice_id = _get_user_id(db_path, alice["email"])
        _add_book_author(client, book, alice_id, alice["headers"])
        idea_id = _create_idea(client, book, alice["headers"])

        response = client.get(f"/ideas/{idea_id}/impact-comments", headers=alice["headers"])
        assert response.status_code == 200
        assert response.json() == []

    def test_get_comments_with_data(self, client, alice, book, db_path):
        alice_id = _get_user_id(db_path, alice["email"])
        _add_book_author(client, book, alice_id, alice["headers"])
        idea_id = _create_idea(client, book, alice["headers"])

        client.post(
            f"/ideas/{idea_id}/impact-comments",
            json={"content": "My impact"},
            headers=alice["headers"],
        )

        response = client.get(f"/ideas/{idea_id}/impact-comments", headers=alice["headers"])
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["content"] == "My impact"
        assert body[0]["username"] == "alice"
        assert body[0]["user_email"] == alice["email"]

    def test_get_comments_requires_auth(self, client, alice, book, db_path):
        alice_id = _get_user_id(db_path, alice["email"])
        _add_book_author(client, book, alice_id, alice["headers"])
        idea_id = _create_idea(client, book, alice["headers"])

        response = client.get(f"/ideas/{idea_id}/impact-comments")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /ideas/{idea_id}/impact-comments
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestCreateImpactComment:
    def test_book_author_can_comment(self, client, alice, book, db_path):
        alice_id = _get_user_id(db_path, alice["email"])
        _add_book_author(client, book, alice_id, alice["headers"])
        idea_id = _create_idea(client, book, alice["headers"])

        response = client.post(
            f"/ideas/{idea_id}/impact-comments",
            json={"content": "This will change the world"},
            headers=alice["headers"],
        )
        assert response.status_code == 200
        body = response.json()
        assert body["content"] == "This will change the world"
        assert body["username"] == "alice"
        assert "id" in body
        assert "created_at" in body

    def test_non_book_author_gets_403(self, client, alice, bob, book, db_path):
        alice_id = _get_user_id(db_path, alice["email"])
        _add_book_author(client, book, alice_id, alice["headers"])
        idea_id = _create_idea(client, book, alice["headers"])

        # bob is NOT a book author
        response = client.post(
            f"/ideas/{idea_id}/impact-comments",
            json={"content": "Sneaky comment"},
            headers=bob["headers"],
        )
        assert response.status_code == 403

    def test_missing_idea_gets_404(self, client, alice, book, db_path):
        alice_id = _get_user_id(db_path, alice["email"])
        _add_book_author(client, book, alice_id, alice["headers"])

        response = client.post(
            "/ideas/99999/impact-comments",
            json={"content": "Ghost comment"},
            headers=alice["headers"],
        )
        assert response.status_code == 404

    def test_create_comment_requires_auth(self, client, alice, book, db_path):
        alice_id = _get_user_id(db_path, alice["email"])
        _add_book_author(client, book, alice_id, alice["headers"])
        idea_id = _create_idea(client, book, alice["headers"])

        response = client.post(
            f"/ideas/{idea_id}/impact-comments",
            json={"content": "No token"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# PUT /impact-comments/{comment_id}
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestUpdateImpactComment:
    def test_owner_can_update(self, client, alice, book, db_path):
        alice_id = _get_user_id(db_path, alice["email"])
        _add_book_author(client, book, alice_id, alice["headers"])
        idea_id = _create_idea(client, book, alice["headers"])

        comment_id = client.post(
            f"/ideas/{idea_id}/impact-comments",
            json={"content": "Original"},
            headers=alice["headers"],
        ).json()["id"]

        response = client.put(
            f"/impact-comments/{comment_id}",
            json={"content": "Updated"},
            headers=alice["headers"],
        )
        assert response.status_code == 200

        comments = client.get(
            f"/ideas/{idea_id}/impact-comments", headers=alice["headers"]
        ).json()
        assert comments[0]["content"] == "Updated"

    def test_non_owner_gets_403(self, client, alice, bob, book, db_path):
        alice_id = _get_user_id(db_path, alice["email"])
        bob_id = _get_user_id(db_path, bob["email"])
        _add_book_author(client, book, alice_id, alice["headers"])
        _add_book_author(client, book, bob_id, alice["headers"])
        idea_id = _create_idea(client, book, alice["headers"])

        comment_id = client.post(
            f"/ideas/{idea_id}/impact-comments",
            json={"content": "Alice's comment"},
            headers=alice["headers"],
        ).json()["id"]

        response = client.put(
            f"/impact-comments/{comment_id}",
            json={"content": "Bob hijacks"},
            headers=bob["headers"],
        )
        assert response.status_code == 403

    def test_update_requires_auth(self, client, alice, book, db_path):
        alice_id = _get_user_id(db_path, alice["email"])
        _add_book_author(client, book, alice_id, alice["headers"])
        idea_id = _create_idea(client, book, alice["headers"])

        comment_id = client.post(
            f"/ideas/{idea_id}/impact-comments",
            json={"content": "Original"},
            headers=alice["headers"],
        ).json()["id"]

        response = client.put(f"/impact-comments/{comment_id}", json={"content": "Hack"})
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /impact-comments/{comment_id}
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestDeleteImpactComment:
    def test_owner_can_delete(self, client, alice, book, db_path):
        alice_id = _get_user_id(db_path, alice["email"])
        _add_book_author(client, book, alice_id, alice["headers"])
        idea_id = _create_idea(client, book, alice["headers"])

        comment_id = client.post(
            f"/ideas/{idea_id}/impact-comments",
            json={"content": "Delete me"},
            headers=alice["headers"],
        ).json()["id"]

        response = client.delete(f"/impact-comments/{comment_id}", headers=alice["headers"])
        assert response.status_code == 200

        comments = client.get(
            f"/ideas/{idea_id}/impact-comments", headers=alice["headers"]
        ).json()
        assert comments == []

    def test_admin_can_delete_any(self, client, alice, bob, book, db_path):
        alice_id = _get_user_id(db_path, alice["email"])
        _add_book_author(client, book, alice_id, alice["headers"])
        idea_id = _create_idea(client, book, alice["headers"])

        comment_id = client.post(
            f"/ideas/{idea_id}/impact-comments",
            json={"content": "Alice's comment"},
            headers=alice["headers"],
        ).json()["id"]

        from backend.main import create_access_token
        from datetime import timedelta
        token = create_access_token(
            data={"sub": bob["email"], "is_admin": True},
            expires_delta=timedelta(minutes=30),
        )
        admin_headers = {"Authorization": f"Bearer {token}"}

        response = client.delete(f"/impact-comments/{comment_id}", headers=admin_headers)
        assert response.status_code == 200

    def test_non_owner_non_admin_gets_403(self, client, alice, bob, book, db_path):
        alice_id = _get_user_id(db_path, alice["email"])
        bob_id = _get_user_id(db_path, bob["email"])
        _add_book_author(client, book, alice_id, alice["headers"])
        _add_book_author(client, book, bob_id, alice["headers"])
        idea_id = _create_idea(client, book, alice["headers"])

        comment_id = client.post(
            f"/ideas/{idea_id}/impact-comments",
            json={"content": "Alice's comment"},
            headers=alice["headers"],
        ).json()["id"]

        response = client.delete(f"/impact-comments/{comment_id}", headers=bob["headers"])
        assert response.status_code == 403

    def test_delete_requires_auth(self, client, alice, book, db_path):
        alice_id = _get_user_id(db_path, alice["email"])
        _add_book_author(client, book, alice_id, alice["headers"])
        idea_id = _create_idea(client, book, alice["headers"])

        comment_id = client.post(
            f"/ideas/{idea_id}/impact-comments",
            json={"content": "Delete me"},
            headers=alice["headers"],
        ).json()["id"]

        response = client.delete(f"/impact-comments/{comment_id}")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /books/{book_id}/impact-comments
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestGetBookImpactComments:
    def test_returns_all_book_comments(self, client, alice, bob, book, db_path):
        alice_id = _get_user_id(db_path, alice["email"])
        bob_id = _get_user_id(db_path, bob["email"])
        _add_book_author(client, book, alice_id, alice["headers"])
        _add_book_author(client, book, bob_id, alice["headers"])

        idea1 = _create_idea(client, book, alice["headers"], "Idea One")
        idea2 = _create_idea(client, book, alice["headers"], "Idea Two")

        client.post(
            f"/ideas/{idea1}/impact-comments",
            json={"content": "Alice on idea 1"},
            headers=alice["headers"],
        )
        client.post(
            f"/ideas/{idea2}/impact-comments",
            json={"content": "Bob on idea 2"},
            headers=bob["headers"],
        )

        response = client.get(f"/books/{book}/impact-comments", headers=alice["headers"])
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        titles = {c["idea_title"] for c in body}
        assert titles == {"Idea One", "Idea Two"}

    def test_returns_empty_for_book_without_comments(self, client, alice, book):
        response = client.get(f"/books/{book}/impact-comments", headers=alice["headers"])
        assert response.status_code == 200
        assert response.json() == []

    def test_requires_auth(self, client, book):
        response = client.get(f"/books/{book}/impact-comments")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Multi-user
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestMultiUserImpactComments:
    def test_both_users_see_all_comments(self, client, alice, bob, book, db_path):
        alice_id = _get_user_id(db_path, alice["email"])
        bob_id = _get_user_id(db_path, bob["email"])
        _add_book_author(client, book, alice_id, alice["headers"])
        _add_book_author(client, book, bob_id, alice["headers"])
        idea_id = _create_idea(client, book, alice["headers"])

        client.post(
            f"/ideas/{idea_id}/impact-comments",
            json={"content": "Alice's impact"},
            headers=alice["headers"],
        )
        client.post(
            f"/ideas/{idea_id}/impact-comments",
            json={"content": "Bob's impact"},
            headers=bob["headers"],
        )

        alice_view = client.get(
            f"/ideas/{idea_id}/impact-comments", headers=alice["headers"]
        ).json()
        bob_view = client.get(
            f"/ideas/{idea_id}/impact-comments", headers=bob["headers"]
        ).json()

        assert len(alice_view) == 2
        assert len(bob_view) == 2
        contents = {c["content"] for c in alice_view}
        assert contents == {"Alice's impact", "Bob's impact"}

    def test_user_can_post_multiple_comments(self, client, alice, book, db_path):
        alice_id = _get_user_id(db_path, alice["email"])
        _add_book_author(client, book, alice_id, alice["headers"])
        idea_id = _create_idea(client, book, alice["headers"])

        client.post(
            f"/ideas/{idea_id}/impact-comments",
            json={"content": "First impact"},
            headers=alice["headers"],
        )
        client.post(
            f"/ideas/{idea_id}/impact-comments",
            json={"content": "Second impact"},
            headers=alice["headers"],
        )

        comments = client.get(
            f"/ideas/{idea_id}/impact-comments", headers=alice["headers"]
        ).json()
        assert len(comments) == 2
