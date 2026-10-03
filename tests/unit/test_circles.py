"""Unit tests for the circles collection client (issue #55).

Circles.list() must unwrap the ``{"data": [...]}`` envelope the API
sends (it looked up a ``"circles"`` key the API never sends), and
Circles.new() must carry ``tag``/``parents`` in the POST payload
instead of silently dropping them. The expected shapes mirror the
campus-suite routes on branch ``weekly``.
"""

import unittest
from unittest.mock import Mock

import campus.model

from campus_python.api.v1 import ApiRoot


def make_api() -> tuple[ApiRoot, Mock]:
    """Create an ApiRoot backed by a mock JSON client."""
    client = Mock()
    return ApiRoot(json_client=client), client


CIRCLE_RESOURCE = {
    "id": "circle_ab12cd34",
    "name": "Design Team",
    "description": "Handles UI/UX",
    "tag": "project",
    "members": {},
    "sources": {},
}


class TestCirclesList(unittest.TestCase):
    """Circles.list() must unwrap the API's data envelope."""

    def setUp(self):
        self.api, self.client = make_api()

    def test_list_unwraps_data_envelope(self):
        self.client.get.return_value.json.return_value = {
            "data": [dict(CIRCLE_RESOURCE)]
        }
        circles = self.api.circles.list()
        self.client.get.assert_called_once_with("/api/v1/circles/")
        self.assertEqual(len(circles), 1)
        self.assertIsInstance(circles[0], campus.model.Circle)
        self.assertEqual(circles[0].name, "Design Team")

    def test_list_returns_empty_list_for_empty_envelope(self):
        self.client.get.return_value.json.return_value = {"data": []}
        self.assertEqual(self.api.circles.list(), [])


class TestCirclesNew(unittest.TestCase):
    """Circles.new() must send tag/parents instead of dropping them."""

    def setUp(self):
        self.api, self.client = make_api()

    def test_new_sends_all_fields(self):
        self.client.post.return_value.json.return_value = dict(CIRCLE_RESOURCE)
        circle = self.api.circles.new(
            name="Design Team",
            tag="project",
            description="Handles UI/UX",
            parents={"circle_parent01": 15},
        )
        self.client.post.assert_called_once_with(
            "/api/v1/circles/",
            json={
                "name": "Design Team",
                "tag": "project",
                "description": "Handles UI/UX",
                "parents": {"circle_parent01": 15},
            },
        )
        self.assertIsInstance(circle, campus.model.Circle)
        self.assertEqual(circle.id, "circle_ab12cd34")

    def test_new_defaults_description_and_omits_parents(self):
        self.client.post.return_value.json.return_value = dict(CIRCLE_RESOURCE)
        self.api.circles.new(name="Design Team", tag="project")
        self.client.post.assert_called_once_with(
            "/api/v1/circles/",
            json={
                "name": "Design Team",
                "tag": "project",
                "description": "",
            },
        )


if __name__ == "__main__":
    unittest.main()
