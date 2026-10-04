"""Tests for client-side request guards mirroring server validation (#75).

Three payloads the weekly server always rejects used to pass through
the client and fail with surprise 4xx responses:
- PATCH /circles/<id>/ requires `name`
- PATCH /assignments/<id>/ rejects an empty body
- POST /timetable/ requires the key `lessongroups` in `data`
The client now validates these locally (and exposes the members PATCH
upsert the server provides).
"""

import unittest
from unittest.mock import Mock

from campus_python.api.v1 import ApiRoot


def make_api() -> tuple[ApiRoot, Mock]:
    """Create an ApiRoot backed by a mock JSON client."""
    client = Mock()
    return ApiRoot(json_client=client), client


class TestCirclesUpdateGuard(unittest.TestCase):
    """Circle.update() must always send the server-required name."""

    def setUp(self):
        self.api, self.client = make_api()

    def test_update_requires_name(self):
        with self.assertRaises(TypeError):
            self.api.circles["cir-1"].update()
        self.client.patch.assert_not_called()

    def test_update_sends_name(self):
        self.api.circles["cir-1"].update(name="Design Team")
        self.client.patch.assert_called_once_with(
            "/api/v1/circles/cir-1/",
            json={"name": "Design Team"},
        )

    def test_update_sends_name_and_description(self):
        self.api.circles["cir-1"].update(
            name="Design Team", description="d"
        )
        self.assertEqual(
            self.client.patch.call_args.kwargs["json"],
            {"name": "Design Team", "description": "d"},
        )

    def test_members_set_patches_members_collection(self):
        """members.set() upserts access via PATCH /members/."""
        self.api.circles["cir-1"].members.set(member_id="cir-2", access_value=7)
        self.client.patch.assert_called_once_with(
            "/api/v1/circles/cir-1/members/",
            json={"member_id": "cir-2", "access_value": 7},
        )


class TestAssignmentsUpdateGuard(unittest.TestCase):
    """Assignment.update() must refuse the empty body the server 400s."""

    def setUp(self):
        self.api, self.client = make_api()

    def test_update_requires_at_least_one_field(self):
        with self.assertRaises(ValueError):
            self.api.assignments["asg-1"].update()
        self.client.patch.assert_not_called()

    def test_update_sends_provided_fields(self):
        self.api.assignments["asg-1"].update(title="New title")
        self.client.patch.assert_called_once_with(
            "/api/v1/assignments/asg-1/",
            json={"title": "New title"},
        )


class TestTimetableNewGuard(unittest.TestCase):
    """Timetables.new() must require the lessongroups data key."""

    def setUp(self):
        self.api, self.client = make_api()

    def test_new_requires_lessongroups_key(self):
        with self.assertRaises(ValueError):
            self.api.timetable.new(
                {"start_date": "2026-01-01", "end_date": "2026-02-01"},
                {"entries": []},
            )
        self.client.post.assert_not_called()

    def test_new_suggests_rename_for_lesson_groups(self):
        with self.assertRaises(ValueError) as ctx:
            self.api.timetable.new({}, {"lesson_groups": []})
        self.assertIn("rename", str(ctx.exception))
        self.client.post.assert_not_called()

    def test_new_passes_lessongroups_through(self):
        self.client.post.return_value.json.return_value = {"data": {}}
        data = {"lessongroups": [], "entries": []}
        self.api.timetable.new(
            {"start_date": "2026-01-01", "end_date": "2026-02-01"}, data
        )
        self.client.post.assert_called_once_with(
            "/api/v1/timetable/",
            json={
                "metadata": {"start_date": "2026-01-01", "end_date": "2026-02-01"},
                "data": data,
            },
        )


if __name__ == "__main__":
    unittest.main()
