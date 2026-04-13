"""
Integration tests for the book and book-author endpoints.

Contracts asserted:
- POST /books creates a book visible in GET /books.
- GET /books returns all books including newly created ones.
- DELETE /books/{id} removes the book from GET /books.
- POST /book-authors links a user as an author; visible in GET /books/{id}/authors.
- DELETE /book-authors removes the link; user no longer in GET /books/{id}/authors.
- Multiple users can be authors of the same book.
- A book_id returned by POST /books is accepted by POST /ideas.
- All endpoints require authentication (401 without token).
"""

import sqlite3
import pytest


@pytest.mark.integration
class TestBookCRUD:
    def test_create_book_returns_numeric_id(self, client, alice):
        response = client.post(
            "/books", json={"title": "My First Book"}, headers=alice["headers"]
        )
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body["id"], int)
        assert body["id"] > 0

    def test_created_book_appears_in_list(self, client, alice):
        client.post("/books", json={"title": "Visible Book"}, headers=alice["headers"])
        response = client.get("/books", headers=alice["headers"])
        assert response.status_code == 200
        titles = [b["title"] for b in response.json()]
        assert "Visible Book" in titles

    def test_get_books_empty_initially(self, client, alice):
        response = client.get("/books", headers=alice["headers"])
        assert response.status_code == 200
        assert response.json() == []

    def test_get_books_returns_all_books(self, client, alice):
        client.post("/books", json={"title": "Book A"}, headers=alice["headers"])
        client.post("/books", json={"title": "Book B"}, headers=alice["headers"])
        client.post("/books", json={"title": "Book C"}, headers=alice["headers"])

        response = client.get("/books", headers=alice["headers"])
        assert response.status_code == 200
        titles = {b["title"] for b in response.json()}
        assert {"Book A", "Book B", "Book C"} == titles

    def test_delete_book_removes_it_from_list(self, client, alice):
        book_id = client.post(
            "/books", json={"title": "To Delete"}, headers=alice["headers"]
        ).json()["id"]

        client.delete(f"/books/{book_id}", headers=alice["headers"])

        titles = [b["title"] for b in client.get("/books", headers=alice["headers"]).json()]
        assert "To Delete" not in titles

    def test_delete_nonexistent_book_returns_200(self, client, alice):
        """remove_book swallows the no-op; endpoint should not raise."""
        response = client.delete("/books/99999", headers=alice["headers"])
        assert response.status_code == 200

    def test_book_requires_title(self, client, alice):
        response = client.post("/books", json={}, headers=alice["headers"])
        assert response.status_code == 422

    def test_get_books_requires_auth(self, client):
        response = client.get("/books")
        assert response.status_code == 401

    def test_create_book_requires_auth(self, client):
        response = client.post("/books", json={"title": "No Auth"})
        assert response.status_code == 401

    def test_delete_book_requires_auth(self, client):
        response = client.delete("/books/1")
        assert response.status_code == 401


@pytest.mark.integration
class TestBookAuthors:
    def test_add_author_to_book(self, client, alice, db_path):
        book_id = client.post(
            "/books", json={"title": "Authored Book"}, headers=alice["headers"]
        ).json()["id"]

        # Look up alice's user id
        conn = sqlite3.connect(db_path)
        alice_id = conn.execute(
            "SELECT id FROM users WHERE email = ?", (alice["email"],)
        ).fetchone()[0]
        conn.close()

        response = client.post(
            "/book-authors",
            json={"book_id": book_id, "user_id": alice_id},
            headers=alice["headers"],
        )
        assert response.status_code == 200

        authors = client.get(f"/books/{book_id}/authors", headers=alice["headers"]).json()
        emails = [a["email"] for a in authors]
        assert alice["email"] in emails

    def test_remove_author_from_book(self, client, alice, db_path):
        book_id = client.post(
            "/books", json={"title": "Co-authored"}, headers=alice["headers"]
        ).json()["id"]

        conn = sqlite3.connect(db_path)
        alice_id = conn.execute(
            "SELECT id FROM users WHERE email = ?", (alice["email"],)
        ).fetchone()[0]
        conn.close()

        client.post(
            "/book-authors",
            json={"book_id": book_id, "user_id": alice_id},
            headers=alice["headers"],
        )

        client.request(
            "DELETE",
            "/book-authors",
            json={"book_id": book_id, "user_id": alice_id},
            headers=alice["headers"],
        )

        authors = client.get(f"/books/{book_id}/authors", headers=alice["headers"]).json()
        assert not any(a["email"] == alice["email"] for a in authors)

    def test_multiple_authors_on_same_book(self, client, alice, bob, db_path):
        book_id = client.post(
            "/books", json={"title": "Joint Book"}, headers=alice["headers"]
        ).json()["id"]

        conn = sqlite3.connect(db_path)
        alice_id = conn.execute(
            "SELECT id FROM users WHERE email = ?", (alice["email"],)
        ).fetchone()[0]
        bob_id = conn.execute(
            "SELECT id FROM users WHERE email = ?", (bob["email"],)
        ).fetchone()[0]
        conn.close()

        client.post(
            "/book-authors",
            json={"book_id": book_id, "user_id": alice_id},
            headers=alice["headers"],
        )
        client.post(
            "/book-authors",
            json={"book_id": book_id, "user_id": bob_id},
            headers=alice["headers"],
        )

        authors = client.get(f"/books/{book_id}/authors", headers=alice["headers"]).json()
        emails = {a["email"] for a in authors}
        assert emails == {alice["email"], bob["email"]}

    def test_create_book_auto_adds_creator_as_author(self, client, alice):
        """Creating a book must automatically add the creator as an author."""
        book_id = client.post(
            "/books", json={"title": "Auto Author"}, headers=alice["headers"]
        ).json()["id"]

        authors = client.get(f"/books/{book_id}/authors", headers=alice["headers"]).json()
        emails = [a["email"] for a in authors]
        assert alice["email"] in emails

    def test_duplicate_author_silently_ignored(self, client, alice, db_path):
        """Adding the same author twice must not crash (IntegrityError swallowed)."""
        book_id = client.post(
            "/books", json={"title": "Dup Author"}, headers=alice["headers"]
        ).json()["id"]

        conn = sqlite3.connect(db_path)
        alice_id = conn.execute(
            "SELECT id FROM users WHERE email = ?", (alice["email"],)
        ).fetchone()[0]
        conn.close()

        payload = {"book_id": book_id, "user_id": alice_id}
        client.post("/book-authors", json=payload, headers=alice["headers"])
        response = client.post("/book-authors", json=payload, headers=alice["headers"])
        assert response.status_code == 200

        # Still only one entry
        authors = client.get(f"/books/{book_id}/authors", headers=alice["headers"]).json()
        assert len(authors) == 1

    def test_book_authors_endpoints_require_auth(self, client):
        response = client.get("/books/1/authors")
        assert response.status_code == 401

        response = client.post("/book-authors", json={"book_id": 1, "user_id": 1})
        assert response.status_code == 401

        response = client.request(
            "DELETE", "/book-authors", json={"book_id": 1, "user_id": 1}
        )
        assert response.status_code == 401


@pytest.mark.integration
class TestBookIdeaIntegration:
    def test_idea_created_with_book_id_stores_correct_reference(
        self, client, alice, book, db_path
    ):
        """The book_id stored in the ideas table matches the one sent in POST /ideas."""
        idea_id = client.post(
            "/ideas",
            json={"title": "Linked Idea", "content": "Content", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        conn = sqlite3.connect(db_path)
        stored_book_id = conn.execute(
            "SELECT book_id FROM ideas WHERE id = ?", (idea_id,)
        ).fetchone()[0]
        conn.close()

        assert stored_book_id == book

    def test_idea_response_includes_book_id(self, client, alice, book):
        """GET /ideas returns book_id for each idea."""
        client.post(
            "/ideas",
            json={"title": "Book-linked Idea", "content": "C", "book_id": book},
            headers=alice["headers"],
        )
        ideas = client.get("/ideas", headers=alice["headers"]).json()
        idea = next(i for i in ideas if i["title"] == "Book-linked Idea")
        assert idea["book_id"] == book

    def test_create_idea_without_book_id_returns_400(self, client, alice):
        """POST /ideas with no book_id must be rejected with 400."""
        response = client.post(
            "/ideas",
            json={"title": "No Book", "content": "Content"},
            headers=alice["headers"],
        )
        assert response.status_code == 400
        assert "book_id" in response.json()["detail"]
