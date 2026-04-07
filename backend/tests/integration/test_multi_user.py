"""
Integration tests for multi-user isolation.

Contracts asserted:
- GET /user/ideas only returns ideas owned by the currently authenticated user.
  Alice cannot see Bob's ideas via this endpoint, and vice versa.
- GET /ideas (all ideas) returns ideas from every user; both Alice's and Bob's
  ideas are included.
- POST /ideas creates the idea under the authenticated user's ownership.
  The idea therefore appears in that user's /user/ideas but not the other's.
- A token issued for a user whose email doesn't exist in the database causes
  add_idea to return -1 (no crash, but the idea is not created).
"""

import pytest
from tests.integration.conftest import make_token


@pytest.mark.integration
class TestUserIdeaIsolation:
    def test_user_ideas_only_returns_own_ideas(self, client, alice, bob, book):
        client.post(
            "/ideas",
            json={"title": "Alice's Private Idea", "content": "For Alice only", "book_id": book},
            headers=alice["headers"],
        )
        client.post(
            "/ideas",
            json={"title": "Bob's Private Idea", "content": "For Bob only", "book_id": book},
            headers=bob["headers"],
        )

        alice_ideas = client.get("/user/ideas", headers=alice["headers"]).json()
        alice_titles = [i["title"] for i in alice_ideas]

        assert "Alice's Private Idea" in alice_titles
        assert "Bob's Private Idea" not in alice_titles

    def test_other_user_ideas_excluded_for_bob(self, client, alice, bob, book):
        client.post(
            "/ideas",
            json={"title": "Alice's Idea", "content": "Alice", "book_id": book},
            headers=alice["headers"],
        )
        client.post(
            "/ideas",
            json={"title": "Bob's Idea", "content": "Bob", "book_id": book},
            headers=bob["headers"],
        )

        bob_ideas = client.get("/user/ideas", headers=bob["headers"]).json()
        bob_titles = [i["title"] for i in bob_ideas]

        assert "Bob's Idea" in bob_titles
        assert "Alice's Idea" not in bob_titles

    def test_all_ideas_shows_both_users(self, client, alice, bob, book):
        client.post(
            "/ideas",
            json={"title": "From Alice", "content": "A", "book_id": book},
            headers=alice["headers"],
        )
        client.post(
            "/ideas",
            json={"title": "From Bob", "content": "B", "book_id": book},
            headers=bob["headers"],
        )

        all_ideas = client.get("/ideas", headers=alice["headers"]).json()
        titles = [i["title"] for i in all_ideas]

        assert "From Alice" in titles
        assert "From Bob" in titles

    def test_idea_ownership_is_determined_by_token_email(self, client, alice, bob, book):
        """
        Alice creates an idea; it must appear under Alice's /user/ideas
        but not Bob's, proving ownership is stored and queried by email.
        """
        client.post(
            "/ideas",
            json={"title": "Ownership Test", "content": "Owned by Alice", "book_id": book},
            headers=alice["headers"],
        )

        alice_owns = any(
            i["title"] == "Ownership Test"
            for i in client.get("/user/ideas", headers=alice["headers"]).json()
        )
        bob_sees = any(
            i["title"] == "Ownership Test"
            for i in client.get("/user/ideas", headers=bob["headers"]).json()
        )

        assert alice_owns is True
        assert bob_sees is False

    def test_two_users_can_have_independent_idea_sets(self, client, alice, bob, book):
        for i in range(3):
            client.post(
                "/ideas",
                json={"title": f"Alice Idea {i}", "content": "A", "book_id": book},
                headers=alice["headers"],
            )
        for i in range(2):
            client.post(
                "/ideas",
                json={"title": f"Bob Idea {i}", "content": "B", "book_id": book},
                headers=bob["headers"],
            )

        alice_count = len(client.get("/user/ideas", headers=alice["headers"]).json())
        bob_count = len(client.get("/user/ideas", headers=bob["headers"]).json())

        assert alice_count == 3
        assert bob_count == 2


@pytest.mark.integration
class TestGhostUserToken:
    def test_create_idea_for_nonexistent_user_returns_200_but_id_is_negative(
        self, client, db_path, alice
    ):
        """
        add_idea returns -1 when the owner email is not in the users table.
        The API wraps this in a 200 response with {"id": -1}.
        This is a documented (if quirky) contract worth pinning before refactor.
        """
        # Create a book first (alice is used to authenticate the book creation)
        book_resp = client.post("/books", json={"title": "Ghost Book"}, headers=alice["headers"])
        book_id = book_resp.json()["id"]

        ghost_headers = {"Authorization": f"Bearer {make_token('ghost@nowhere.com')}"}
        response = client.post(
            "/ideas",
            json={"title": "Ghost Idea", "content": "Nobody owns this", "book_id": book_id},
            headers=ghost_headers,
        )
        assert response.status_code == 200
        assert response.json()["id"] == -1
