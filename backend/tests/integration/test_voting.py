"""
Integration tests for the idea voting feature.

Contracts asserted:
- GET /ideas/{idea_id}/votes returns score=0, count=0, user_vote=None when no votes exist.
- POST /ideas/{idea_id}/vote with value=1 registers an upvote and returns updated summary.
- POST /ideas/{idea_id}/vote with value=-1 registers a downvote.
- POST /ideas/{idea_id}/vote with an invalid value returns 422 (Pydantic) or 400.
- A second POST replaces the previous vote (upsert semantic).
- DELETE /ideas/{idea_id}/vote removes the vote and score returns to 0.
- DELETE is idempotent: deleting a non-existent vote succeeds.
- Multiple users can vote independently; score aggregates correctly.
- user_vote reflects only the requesting user's own vote.
- Unauthenticated requests to all three endpoints return 401.
"""

import pytest


@pytest.mark.integration
class TestGetVotes:
    def test_get_votes_no_votes(self, client, alice, book):
        idea_id = client.post(
            "/ideas",
            json={"title": "Vote Target", "content": "Content", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        response = client.get(f"/ideas/{idea_id}/votes", headers=alice["headers"])
        assert response.status_code == 200
        body = response.json()
        assert body["score"] == 0
        assert body["count"] == 0
        assert body["user_vote"] is None

    def test_get_votes_requires_auth(self, client, alice, book):
        idea_id = client.post(
            "/ideas",
            json={"title": "Auth Target", "content": "Content", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        response = client.get(f"/ideas/{idea_id}/votes")
        assert response.status_code == 401


@pytest.mark.integration
class TestCastVote:
    def test_upvote_returns_correct_summary(self, client, alice, book):
        idea_id = client.post(
            "/ideas",
            json={"title": "Upvoted Idea", "content": "Content", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        response = client.post(
            f"/ideas/{idea_id}/vote",
            json={"value": 1},
            headers=alice["headers"],
        )
        assert response.status_code == 200
        body = response.json()
        assert body["score"] == 1
        assert body["count"] == 1
        assert body["user_vote"] == 1

    def test_downvote_returns_correct_summary(self, client, alice, book):
        idea_id = client.post(
            "/ideas",
            json={"title": "Downvoted Idea", "content": "Content", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        response = client.post(
            f"/ideas/{idea_id}/vote",
            json={"value": -1},
            headers=alice["headers"],
        )
        assert response.status_code == 200
        body = response.json()
        assert body["score"] == -1
        assert body["count"] == 1
        assert body["user_vote"] == -1

    def test_invalid_value_rejected(self, client, alice, book):
        idea_id = client.post(
            "/ideas",
            json={"title": "Invalid Vote Idea", "content": "Content", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        response = client.post(
            f"/ideas/{idea_id}/vote",
            json={"value": 0},
            headers=alice["headers"],
        )
        assert response.status_code in (400, 422)

    def test_second_vote_replaces_first(self, client, alice, book):
        idea_id = client.post(
            "/ideas",
            json={"title": "Flip Vote Idea", "content": "Content", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        client.post(
            f"/ideas/{idea_id}/vote", json={"value": 1}, headers=alice["headers"]
        )
        response = client.post(
            f"/ideas/{idea_id}/vote", json={"value": -1}, headers=alice["headers"]
        )
        assert response.status_code == 200
        body = response.json()
        assert body["score"] == -1
        assert body["count"] == 1  # still only one row

    def test_vote_requires_auth(self, client, alice, book):
        idea_id = client.post(
            "/ideas",
            json={"title": "Auth Vote Idea", "content": "Content", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        response = client.post(f"/ideas/{idea_id}/vote", json={"value": 1})
        assert response.status_code == 401

    def test_get_votes_reflects_cast_vote(self, client, alice, book):
        idea_id = client.post(
            "/ideas",
            json={"title": "Reflect Idea", "content": "Content", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        client.post(
            f"/ideas/{idea_id}/vote", json={"value": 1}, headers=alice["headers"]
        )

        response = client.get(f"/ideas/{idea_id}/votes", headers=alice["headers"])
        body = response.json()
        assert body["score"] == 1
        assert body["user_vote"] == 1


@pytest.mark.integration
class TestDeleteVote:
    def test_delete_vote_removes_vote(self, client, alice, book):
        idea_id = client.post(
            "/ideas",
            json={"title": "Delete Vote Idea", "content": "Content", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        client.post(
            f"/ideas/{idea_id}/vote", json={"value": 1}, headers=alice["headers"]
        )

        response = client.delete(
            f"/ideas/{idea_id}/vote", headers=alice["headers"]
        )
        assert response.status_code == 200
        body = response.json()
        assert body["score"] == 0
        assert body["count"] == 0
        assert body["user_vote"] is None

    def test_delete_vote_is_idempotent(self, client, alice, book):
        idea_id = client.post(
            "/ideas",
            json={"title": "Idempotent Delete Idea", "content": "Content", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        # Delete without having voted first — should succeed
        response = client.delete(
            f"/ideas/{idea_id}/vote", headers=alice["headers"]
        )
        assert response.status_code == 200

    def test_delete_vote_requires_auth(self, client, alice, book):
        idea_id = client.post(
            "/ideas",
            json={"title": "Auth Delete Idea", "content": "Content", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        response = client.delete(f"/ideas/{idea_id}/vote")
        assert response.status_code == 401


@pytest.mark.integration
class TestMultiUserVoting:
    def test_multiple_users_vote_independently(self, client, alice, bob, book):
        idea_id = client.post(
            "/ideas",
            json={"title": "Multi-User Idea", "content": "Content", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        client.post(
            f"/ideas/{idea_id}/vote", json={"value": 1}, headers=alice["headers"]
        )
        client.post(
            f"/ideas/{idea_id}/vote", json={"value": 1}, headers=bob["headers"]
        )

        response = client.get(f"/ideas/{idea_id}/votes", headers=alice["headers"])
        body = response.json()
        assert body["score"] == 2
        assert body["count"] == 2

    def test_user_vote_field_is_per_user(self, client, alice, bob, book):
        idea_id = client.post(
            "/ideas",
            json={"title": "Per-User Vote Idea", "content": "Content", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        client.post(
            f"/ideas/{idea_id}/vote", json={"value": 1}, headers=alice["headers"]
        )
        client.post(
            f"/ideas/{idea_id}/vote", json={"value": -1}, headers=bob["headers"]
        )

        alice_view = client.get(
            f"/ideas/{idea_id}/votes", headers=alice["headers"]
        ).json()
        bob_view = client.get(
            f"/ideas/{idea_id}/votes", headers=bob["headers"]
        ).json()

        assert alice_view["user_vote"] == 1
        assert bob_view["user_vote"] == -1
        # Both see the same aggregate
        assert alice_view["score"] == bob_view["score"] == 0
        assert alice_view["count"] == bob_view["count"] == 2

    def test_score_after_one_user_removes_vote(self, client, alice, bob, book):
        idea_id = client.post(
            "/ideas",
            json={"title": "Remove One Vote Idea", "content": "Content", "book_id": book},
            headers=alice["headers"],
        ).json()["id"]

        client.post(
            f"/ideas/{idea_id}/vote", json={"value": 1}, headers=alice["headers"]
        )
        client.post(
            f"/ideas/{idea_id}/vote", json={"value": 1}, headers=bob["headers"]
        )
        client.delete(f"/ideas/{idea_id}/vote", headers=alice["headers"])

        response = client.get(f"/ideas/{idea_id}/votes", headers=alice["headers"])
        body = response.json()
        assert body["score"] == 1
        assert body["count"] == 1
        assert body["user_vote"] is None
