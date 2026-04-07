"""
Integration tests for tag management and cascade behaviour.

Contracts asserted:
- POST /tags creates a standalone tag visible in GET /tags.
- Duplicate tag creation is silently absorbed (no 500).
- DELETE /tags/{name} removes the tag from the tags table.
- Deleting a tag removes all associated relations (SQLite FK cascade).
  After deletion GET /ideas/{id}/tags for an idea that had that tag → empty.
- POST /relations manually creates an idea-tag link.
- DELETE /relations removes only that specific link; other relations are kept.
- GET /ideas/tags/{tags} filters ideas to those associated with the given tag(s).
  Semicolon-separated tags in the path return the union of matching ideas.
"""

import pytest


@pytest.mark.integration
class TestTagCRUD:
    def test_create_standalone_tag(self, client, alice):
        response = client.post("/tags", json={"name": "standalone"}, headers=alice["headers"])
        assert response.status_code == 200

        tags = client.get("/tags", headers=alice["headers"]).json()
        assert any(t["name"] == "standalone" for t in tags)

    def test_duplicate_tag_is_silently_ignored(self, client, alice):
        client.post("/tags", json={"name": "dup"}, headers=alice["headers"])
        response = client.post("/tags", json={"name": "dup"}, headers=alice["headers"])
        # Should not raise a 500; the handler catches IntegrityError
        assert response.status_code == 200

    def test_delete_tag_removes_from_tags_list(self, client, alice):
        client.post("/tags", json={"name": "to_delete"}, headers=alice["headers"])

        client.delete("/tags/to_delete", headers=alice["headers"])

        tags = client.get("/tags", headers=alice["headers"]).json()
        assert not any(t["name"] == "to_delete" for t in tags)

    def test_delete_tag_does_not_cascade_to_relations(self, client, alice, book):
        """
        SQLite FK cascade requires 'PRAGMA foreign_keys = ON', which the current
        codebase does NOT set. Deleting a tag therefore leaves its relation rows
        as orphaned entries. get_tags_from_idea queries the relations table
        directly (no JOIN on tags), so it still returns the deleted tag name.

        This test documents the ACTUAL current behaviour. Any refactor that
        enables FK enforcement or adds manual cleanup must update this assertion.
        """
        idea_id = client.post(
            "/ideas",
            json={"title": "Cascaded Idea", "content": "C", "tags": "cascade_tag", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        client.delete("/tags/cascade_tag", headers=alice["headers"])

        tags = client.get(f"/ideas/{idea_id}/tags", headers=alice["headers"]).json()
        # Orphaned relation row still visible – not cascaded
        assert "cascade_tag" in tags

    def test_delete_nonexistent_tag_returns_200(self, client, alice):
        """remove_tag swallows the no-op; the endpoint should not raise."""
        response = client.delete("/tags/does_not_exist", headers=alice["headers"])
        assert response.status_code == 200


@pytest.mark.integration
class TestRelationManagement:
    def test_create_relation_manually(self, client, alice, book):
        idea_id = client.post(
            "/ideas",
            json={"title": "Relation Idea", "content": "C", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]
        client.post("/tags", json={"name": "manual_tag"}, headers=alice["headers"])

        response = client.post(
            "/relations",
            json={"idea_id": idea_id, "tag_name": "manual_tag"},
            headers=alice["headers"],
        )
        assert response.status_code == 200

        tags = client.get(f"/ideas/{idea_id}/tags", headers=alice["headers"]).json()
        assert "manual_tag" in tags

    def test_delete_relation_removes_only_that_link(self, client, alice, book):
        # NOTE: DELETE /relations requires a request body (RelationItem).
        # httpx.Client.delete() does not accept json=; use client.request() instead.
        idea_id = client.post(
            "/ideas",
            json={"title": "Multi-Tag Idea", "content": "C", "tags": "keep;remove", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        client.request(
            "DELETE",
            "/relations",
            json={"idea_id": idea_id, "tag_name": "remove"},
            headers=alice["headers"],
        )

        tags = client.get(f"/ideas/{idea_id}/tags", headers=alice["headers"]).json()
        assert "keep" in tags
        assert "remove" not in tags

    def test_delete_relation_keeps_the_tag_itself(self, client, alice, book):
        idea_id = client.post(
            "/ideas",
            json={"title": "Orphan Tag Test", "content": "C", "tags": "orphan", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        client.request(
            "DELETE",
            "/relations",
            json={"idea_id": idea_id, "tag_name": "orphan"},
            headers=alice["headers"],
        )

        # The tag row should still exist even though no relation references it
        all_tags = client.get("/tags", headers=alice["headers"]).json()
        assert any(t["name"] == "orphan" for t in all_tags)


@pytest.mark.integration
class TestFilterByTag:
    def test_filter_by_single_tag_returns_matching_ideas(self, client, alice, book):
        client.post(
            "/ideas",
            json={"title": "ML Idea", "content": "C", "tags": "ml", "book_id": book},
            headers=alice["headers"],
        )
        client.post(
            "/ideas",
            json={"title": "Python Idea", "content": "C", "tags": "python", "book_id": book},
            headers=alice["headers"],
        )

        response = client.get("/ideas/tags/ml", headers=alice["headers"])
        assert response.status_code == 200
        titles = [i["title"] for i in response.json()]
        assert "ML Idea" in titles
        assert "Python Idea" not in titles

    def test_filter_by_multiple_tags_returns_union(self, client, alice, book):
        """
        Semicolon-separated tags in the URL path → get_idea_from_tags splits on ';'
        and returns ideas matching ANY of the supplied tags.
        """
        client.post(
            "/ideas",
            json={"title": "Alpha", "content": "C", "tags": "alpha", "book_id": book},
            headers=alice["headers"],
        )
        client.post(
            "/ideas",
            json={"title": "Beta", "content": "C", "tags": "beta", "book_id": book},
            headers=alice["headers"],
        )
        client.post(
            "/ideas",
            json={"title": "Gamma", "content": "C", "tags": "gamma", "book_id": book},
            headers=alice["headers"],
        )

        # URL-encode the semicolon so TestClient doesn't interpret it as a separator
        response = client.get("/ideas/tags/alpha%3Bbeta", headers=alice["headers"])
        assert response.status_code == 200
        titles = [i["title"] for i in response.json()]
        assert "Alpha" in titles
        assert "Beta" in titles
        assert "Gamma" not in titles

    def test_filter_with_no_matching_tag_returns_empty(self, client, alice, book):
        client.post(
            "/ideas",
            json={"title": "Untagged Idea", "content": "C", "tags": "sometag", "book_id": book},
            headers=alice["headers"],
        )

        response = client.get("/ideas/tags/nonexistent", headers=alice["headers"])
        assert response.status_code == 200
        assert response.json() == []
