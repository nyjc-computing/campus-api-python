"""Unit tests for the users collection client (campus#1202).

Users.roles() is the inverted membership check: GET /users/{id}/roles
answers which role circles a user holds, resolved transitively. The
expected shape mirrors the campus-suite route on branch ``weekly``.
"""

import unittest

from tests.support import make_api

ROLES_BODY = {
    "user_id": "teacher@campus.test",
    "roles": [
        {
            "circle_id": "circle_ab12cd34",
            "name": "timetable.admin",
            "access_value": 15,
            "direct": False,
            "via": ["staff"],
        },
    ],
}


class TestUsersRoles(unittest.TestCase):
    """Users.roles() hits the roles route and returns the dict."""

    def setUp(self):
        self.api, self.client = make_api()

    def test_roles_returns_roles_dict(self):
        self.client.get.return_value.json.return_value = dict(ROLES_BODY)
        result = self.api.users.roles("teacher@campus.test")
        self.client.get.assert_called_once_with(
            "/api/v1/users/teacher@campus.test/roles"
        )
        self.assertEqual(result, ROLES_BODY)
        self.assertEqual(result["roles"][0]["name"], "timetable.admin")
        self.assertEqual(result["roles"][0]["via"], ["staff"])

    def test_roles_for_unknown_user_returns_empty(self):
        """A user with no memberships answers an empty list, not 404."""
        self.client.get.return_value.json.return_value = {
            "user_id": "nobody@campus.test",
            "roles": [],
        }
        result = self.api.users.roles("nobody@campus.test")
        self.assertEqual(result["roles"], [])


if __name__ == "__main__":
    unittest.main()
