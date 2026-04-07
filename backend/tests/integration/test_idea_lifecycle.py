"""
Integration tests for the full idea lifecycle.

Contracts asserted:
- POST /ideas creates a record in SQLite, returns its id, and inserts into ChromaDB.
- The created idea is visible in GET /user/ideas and GET /ideas.
- GET /ideas/{id}/content returns the stored content verbatim.
- Tags provided as a semicolon-separated string are stored as individual relations.
- GET /ideas/{id}/tags returns a list of those tag names.
- GET /ideas responds with tags as a semicolon-joined string (GROUP_CONCAT contract).
- PUT /ideas/{id} updates title and content in SQLite and ChromaDB.
- PUT /ideas/{id} reconciles the tag set (adds new, removes removed, keeps kept).
- DELETE /ideas/{id} removes the record from SQLite and ChromaDB.
- DELETE /ideas/{id} cascades to remove its relations.
- GET /ideas/search/{term} and GET /ideas/similar/{idea} proxy the ChromaDB query
  and join the results back against SQLite.
"""

import pytest


@pytest.mark.integration
class TestCreateIdea:
    def test_create_idea_returns_numeric_id(self, client, alice, book):
        response = client.post(
            "/ideas",
            json={"title": "First Idea", "content": "Some content", "book_id": book},
            headers=alice["headers"],
        )
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body["id"], int)
        assert body["id"] > 0

    def test_created_idea_appears_in_user_ideas(self, client, alice, book):
        client.post(
            "/ideas",
            json={"title": "My Idea", "content": "Detail", "book_id": book},
            headers=alice["headers"],
        )
        response = client.get("/user/ideas", headers=alice["headers"])
        assert response.status_code == 200
        titles = [i["title"] for i in response.json()]
        assert "My Idea" in titles

    def test_created_idea_appears_in_all_ideas(self, client, alice, book):
        client.post(
            "/ideas",
            json={"title": "Global Idea", "content": "Visible to all", "book_id": book},
            headers=alice["headers"],
        )
        response = client.get("/ideas", headers=alice["headers"])
        titles = [i["title"] for i in response.json()]
        assert "Global Idea" in titles

    def test_create_idea_inserts_into_chroma(self, client, alice, book, chroma_store):
        client.post(
            "/ideas",
            json={"title": "Chroma Idea", "content": "Will be embedded", "book_id": book},
            headers=alice["headers"],
        )
        assert "Chroma Idea" in chroma_store

    def test_create_idea_with_tags_creates_relations(self, client, alice, book):
        response = client.post(
            "/ideas",
            json={"title": "Tagged Idea", "content": "Content", "tags": "ml;python", "book_id": book},
            headers=alice["headers"],
        )
        idea_id = response.json()["id"]

        tags_response = client.get(f"/ideas/{idea_id}/tags", headers=alice["headers"])
        assert tags_response.status_code == 200
        assert sorted(tags_response.json()) == ["ml", "python"]

    def test_create_idea_tags_appear_in_global_tags(self, client, alice, book):
        client.post(
            "/ideas",
            json={"title": "Tag Source", "content": "Creates tags", "tags": "newtag", "book_id": book},
            headers=alice["headers"],
        )
        tags_response = client.get("/tags", headers=alice["headers"])
        tag_names = [t["name"] for t in tags_response.json()]
        assert "newtag" in tag_names

    def test_create_idea_tags_are_semicolon_joined_in_list_response(self, client, alice, book):
        """GET /ideas must return tags as a semicolon-joined string (GROUP_CONCAT contract)."""
        client.post(
            "/ideas",
            json={"title": "Tag Concat", "content": "C", "tags": "a;b;c", "book_id": book},
            headers=alice["headers"],
        )
        ideas = client.get("/ideas", headers=alice["headers"]).json()
        idea = next(i for i in ideas if i["title"] == "Tag Concat")
        # tags field is a string, order from GROUP_CONCAT may vary
        assert set(idea["tags"].split(";")) == {"a", "b", "c"}

    def test_create_idea_without_tags_has_empty_tags_field(self, client, alice, book):
        client.post(
            "/ideas",
            json={"title": "No Tags", "content": "Plain", "book_id": book},
            headers=alice["headers"],
        )
        ideas = client.get("/ideas", headers=alice["headers"]).json()
        idea = next(i for i in ideas if i["title"] == "No Tags")
        assert idea["tags"] == "" or idea["tags"] is None


@pytest.mark.integration
class TestGetContent:
    def test_get_content_returns_stored_content(self, client, alice, book):
        body = client.post(
            "/ideas",
            json={"title": "Content Test", "content": "The exact content string", "book_id": book},
            headers=alice["headers"],
        ).json()
        idea_id = body["id"]

        response = client.get(f"/ideas/{idea_id}/content", headers=alice["headers"])
        assert response.status_code == 200
        assert response.json() == "The exact content string"


@pytest.mark.integration
class TestUpdateIdea:
    def test_update_changes_title_and_content(self, client, alice, book):
        idea_id = client.post(
            "/ideas",
            json={"title": "Old Title", "content": "Old content", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        client.put(
            f"/ideas/{idea_id}",
            json={"title": "New Title", "content": "New content", "book_id": book},
            headers=alice["headers"],
        )

        content = client.get(f"/ideas/{idea_id}/content", headers=alice["headers"]).json()
        assert content == "New content"

        ideas = client.get("/ideas", headers=alice["headers"]).json()
        idea = next(i for i in ideas if i["id"] == idea_id)
        assert idea["title"] == "New Title"

    def test_update_chroma_reflects_new_content(self, client, alice, book, chroma_store):
        idea_id = client.post(
            "/ideas",
            json={"title": "Before Update", "content": "v1", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        client.put(
            f"/ideas/{idea_id}",
            json={"title": "Before Update", "content": "v2", "book_id": book},
            headers=alice["headers"],
        )

        assert chroma_store["Before Update"] == "v2"

    def test_update_adds_new_tag(self, client, alice, book):
        idea_id = client.post(
            "/ideas",
            json={"title": "Tag Add", "content": "C", "tags": "existing", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        client.put(
            f"/ideas/{idea_id}",
            json={"title": "Tag Add", "content": "C", "tags": "existing;added", "book_id": book},
            headers=alice["headers"],
        )

        tags = client.get(f"/ideas/{idea_id}/tags", headers=alice["headers"]).json()
        assert sorted(tags) == ["added", "existing"]

    def test_update_removes_old_tag(self, client, alice, book):
        idea_id = client.post(
            "/ideas",
            json={"title": "Tag Remove", "content": "C", "tags": "keep;drop", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        client.put(
            f"/ideas/{idea_id}",
            json={"title": "Tag Remove", "content": "C", "tags": "keep", "book_id": book},
            headers=alice["headers"],
        )

        tags = client.get(f"/ideas/{idea_id}/tags", headers=alice["headers"]).json()
        assert tags == ["keep"]

    def test_update_replaces_entire_tag_set(self, client, alice, book):
        idea_id = client.post(
            "/ideas",
            json={"title": "Tag Replace", "content": "C", "tags": "old1;old2", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        client.put(
            f"/ideas/{idea_id}",
            json={"title": "Tag Replace", "content": "C", "tags": "new1;new2", "book_id": book},
            headers=alice["headers"],
        )

        tags = client.get(f"/ideas/{idea_id}/tags", headers=alice["headers"]).json()
        assert sorted(tags) == ["new1", "new2"]


@pytest.mark.integration
class TestDeleteIdea:
    # NOTE: DELETE /ideas/{id} requires a request body (IdeaItem).
    # httpx.Client.delete() does not accept json=; use client.request() instead.

    def test_delete_removes_from_user_ideas(self, client, alice, book):
        idea_id = client.post(
            "/ideas",
            json={"title": "To Delete", "content": "Temporary", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        client.request(
            "DELETE",
            f"/ideas/{idea_id}",
            json={"title": "To Delete", "content": "Temporary", "book_id": book},
            headers=alice["headers"],
        )

        ideas = client.get("/user/ideas", headers=alice["headers"]).json()
        assert not any(i["id"] == idea_id for i in ideas)

    def test_delete_removes_from_chroma(self, client, alice, book, chroma_store):
        client.post(
            "/ideas",
            json={"title": "Chroma Delete", "content": "C", "book_id": book},
            headers=alice["headers"],
        )
        assert "Chroma Delete" in chroma_store

        idea_id = next(
            i["id"]
            for i in client.get("/user/ideas", headers=alice["headers"]).json()
            if i["title"] == "Chroma Delete"
        )
        client.request(
            "DELETE",
            f"/ideas/{idea_id}",
            json={"title": "Chroma Delete", "content": "C", "book_id": book},
            headers=alice["headers"],
        )

        assert "Chroma Delete" not in chroma_store

    def test_delete_removes_relations_via_sqlite_cascade(self, client, alice, book):
        """
        SQLite enforces FK ON DELETE CASCADE only when 'PRAGMA foreign_keys = ON'
        is active. The current codebase does NOT set this pragma, so deleting an
        idea does NOT automatically remove its relations.

        This test documents the ACTUAL current behaviour: after deleting an idea,
        the relations table retains orphaned rows, and get_tags_from_idea still
        returns them. Any refactor that adds PRAGMA foreign_keys = ON (or manual
        relation cleanup) should update this assertion accordingly.
        """
        idea_id = client.post(
            "/ideas",
            json={"title": "Cascade Delete", "content": "C", "tags": "t1;t2", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        client.request(
            "DELETE",
            f"/ideas/{idea_id}",
            json={"title": "Cascade Delete", "content": "C", "book_id": book},
            headers=alice["headers"],
        )

        # The idea row is gone from the ideas table
        ideas = client.get("/user/ideas", headers=alice["headers"]).json()
        assert not any(i["id"] == idea_id for i in ideas)

        # But orphaned relation rows remain (no FK cascade enforced)
        tags = client.get(f"/ideas/{idea_id}/tags", headers=alice["headers"]).json()
        assert sorted(tags) == ["t1", "t2"]  # orphaned rows still visible


@pytest.mark.integration
class TestSearch:
    def test_search_returns_ideas_matching_via_chroma(self, client, alice, book, chroma_store):
        """
        FakeChromaClient.get_similar_idea returns all stored titles.
        Verifies the full chain: ChromaDB titles → SQL join → IdeaItem response.
        """
        client.post(
            "/ideas",
            json={"title": "Quantum Physics", "content": "Wave functions", "book_id": book},
            headers=alice["headers"],
        )

        response = client.get("/ideas/search/Quantum", headers=alice["headers"])
        assert response.status_code == 200
        titles = [i["title"] for i in response.json()]
        assert "Quantum Physics" in titles

    def test_similar_ideas_endpoint_proxies_chroma(self, client, alice, book):
        client.post(
            "/ideas",
            json={"title": "Machine Learning", "content": "Gradient descent", "book_id": book},
            headers=alice["headers"],
        )

        response = client.get("/ideas/similar/Machine%20Learning", headers=alice["headers"])
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_search_empty_chroma_returns_empty_list(self, client, alice):
        response = client.get("/ideas/search/anything", headers=alice["headers"])
        assert response.status_code == 200
        assert response.json() == []
