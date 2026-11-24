"""Unit tests for the integration action proxy client (#1221).

Pins the wire contract against campus.auth's
/auth/v1/integrations/{provider}/{integration}/users/{user_id}/{action}
endpoints: paths, payload shapes (None-dropped), and error propagation.
"""

import unittest

from tests.support import json_response, make_integrations


class TestIntegrationActions(unittest.TestCase):
    """Wire-contract tests for IntegrationActions."""

    def setUp(self):
        self.root, self.client = make_integrations()

    def _user_actions(self):
        return self.root["google.classroom"].with_user("student@nyjc.edu.sg")

    def test_getitem_returns_action_proxy(self):
        actions = self.root["google.classroom"]
        self.assertIsNotNone(actions)

    def test_getitem_rejects_unnamespaced_provider(self):
        with self.assertRaises(ValueError):
            self.root["classroom"]
        with self.assertRaises(ValueError):
            self.root["google."]

    def test_turn_in_posts_minimal_payload(self):
        actions = self._user_actions()
        self.client.post.return_value = json_response(
            {"action": "turn-in", "turned_in": True, "already": False},
        )
        body = actions.turn_in(course_id="c1", coursework_id="cw1")
        self.assertEqual(body["turned_in"], True)
        self.client.post.assert_called_once_with(
            "/auth/v1/integrations/google/classroom/users"
            "/student@nyjc.edu.sg/turn-in",
            json={"course_id": "c1", "coursework_id": "cw1"},
        )

    def test_turn_in_passes_submission_id_when_given(self):
        actions = self._user_actions()
        self.client.post.return_value = json_response({"action": "turn-in"})
        actions.turn_in(course_id="c1", coursework_id="cw1", submission_id="s1")
        self.client.post.assert_called_once_with(
            "/auth/v1/integrations/google/classroom/users"
            "/student@nyjc.edu.sg/turn-in",
            json={
                "course_id": "c1",
                "coursework_id": "cw1",
                "submission_id": "s1",
            },
        )

    def test_reclaim_posts_to_reclaim_path(self):
        actions = self._user_actions()
        self.client.post.return_value = json_response(
            {"action": "reclaim", "reclaimed": True},
        )
        actions.reclaim(course_id="c1", coursework_id="cw1")
        self.client.post.assert_called_once_with(
            "/auth/v1/integrations/google/classroom/users"
            "/student@nyjc.edu.sg/reclaim",
            json={"course_id": "c1", "coursework_id": "cw1"},
        )

    def test_modify_attachments_posts_attachment_list(self):
        actions = self._user_actions()
        self.client.post.return_value = json_response(
            {"action": "modify-attachments", "attached": 1},
        )
        attachments = [{"link": {"url": "https://example.test/review"}}]
        actions.modify_attachments(
            course_id="c1", coursework_id="cw1",
            submission_id="s1", attachments=attachments,
        )
        self.client.post.assert_called_once_with(
            "/auth/v1/integrations/google/classroom/users"
            "/student@nyjc.edu.sg/modify-attachments",
            json={
                "course_id": "c1",
                "coursework_id": "cw1",
                "submission_id": "s1",
                "attachments": attachments,
            },
        )

    def test_get_submission_sends_query(self):
        actions = self._user_actions()
        self.client.get.return_value = json_response(
            {"id": "s1", "state": "NEW"},
        )
        body = actions.get_submission(course_id="c1", coursework_id="cw1")
        self.assertEqual(body["id"], "s1")
        self.client.get.assert_called_once_with(
            "/auth/v1/integrations/google/classroom/users"
            "/student@nyjc.edu.sg/submission",
            query={"course_id": "c1", "coursework_id": "cw1"},
        )

    def test_errors_propagate_from_transport(self):
        actions = self._user_actions()
        self.client.post.return_value = json_response(
            {"error": {"message": "forbidden"}}, status_code=403,
        )
        from campus_python.errors import AccessDeniedError

        with self.assertRaises(AccessDeniedError):
            actions.turn_in(course_id="c1", coursework_id="cw1")


if __name__ == "__main__":
    unittest.main()
