"""Regression tests for the submissions unsubmit contract (issue #74).

The server clears a submission's submitted_at only when the PATCH body
carries an explicit null (campus/api/resources/submission.py), which is
how campus-classroom submits its unsubmit. update() cannot express
that — its None means "omit the field" — so Submissions.unsubmit()
sends the explicit-null body itself.
"""

import unittest
from unittest.mock import Mock

from campus_python.api.v1 import ApiRoot


def make_api() -> tuple[ApiRoot, Mock]:
    """Create an ApiRoot backed by a mock JSON client."""
    client = Mock()
    return ApiRoot(json_client=client), client


class TestSubmissionsUnsubmit(unittest.TestCase):
    """unsubmit() must PATCH an explicit submitted_at null."""

    def setUp(self):
        self.api, self.client = make_api()

    def test_unsubmit_patches_explicit_null(self):
        self.api.submissions["sub-1"].unsubmit()
        self.client.patch.assert_called_once_with(
            "/api/v1/submissions/sub-1/",
            json={"submitted_at": None},
        )

    def test_update_still_requires_a_field(self):
        """update() keeps its "at least one field" contract."""
        with self.assertRaises(ValueError):
            self.api.submissions["sub-1"].update()
        self.client.patch.assert_not_called()

    def test_update_still_sets_timestamp(self):
        self.api.submissions["sub-1"].update(
            submitted_at="2026-10-04T01:02:03Z"
        )
        self.client.patch.assert_called_once_with(
            "/api/v1/submissions/sub-1/",
            json={"submitted_at": "2026-10-04T01:02:03Z"},
        )


if __name__ == "__main__":
    unittest.main()
