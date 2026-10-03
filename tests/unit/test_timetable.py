"""Unit tests for the timetable resource (issue #54).

The api service wraps timetable list/create responses in a
``{"data": ...}`` envelope and the by-id GET in ``{"timetable": ...}``
(campus/api/routes/timetable.py, branch ``weekly``); the client must
unwrap them instead of returning the envelope (or, for list(), crashing
while iterating it).
"""

import unittest
from unittest.mock import Mock, patch

import campus.model

from campus_python.api.v1 import ApiRoot


def make_api() -> tuple[ApiRoot, Mock]:
    """Create an ApiRoot backed by a mock JSON client."""
    client = Mock()
    return ApiRoot(json_client=client), client


class TestTimetablesList(unittest.TestCase):
    """Timetables.list() must unwrap the API's data envelope."""

    def setUp(self):
        self.api, self.client = make_api()

    def test_list_unwraps_data_envelope(self):
        metadata = [{"id": "uid-timetable-1", "start_date": "2026-01-01"}]
        self.client.get.return_value.json.return_value = {"data": metadata}
        with patch.object(
            campus.model.TimetableMetadata, "from_resource", return_value=Mock()
        ) as from_resource:
            self.api.timetable.list()
        self.client.get.assert_called_once_with("/api/v1/timetable/", query=None)
        from_resource.assert_called_once_with(metadata[0])

    def test_list_returns_empty_list_for_empty_envelope(self):
        self.client.get.return_value.json.return_value = {"data": []}
        self.assertEqual(self.api.timetable.list(), [])


class TestTimetablesNew(unittest.TestCase):
    """Timetables.new() must unwrap the created resource."""

    def setUp(self):
        self.api, self.client = make_api()

    def test_new_unwraps_data_envelope(self):
        resource = {"id": "uid-timetable-1"}
        self.client.post.return_value.json.return_value = {"data": resource}
        result = self.api.timetable.new(metadata={}, data={"lessongroups": {}})
        self.client.post.assert_called_once_with(
            "/api/v1/timetable/",
            json={"metadata": {}, "data": {"lessongroups": {}}},
        )
        self.assertEqual(result, resource)


class TestTimetableGet(unittest.TestCase):
    """Timetables.Timetable.get() must unwrap the timetable envelope."""

    def setUp(self):
        self.api, self.client = make_api()

    def test_get_unwraps_timetable_envelope(self):
        resource = {"id": "uid-timetable-1"}
        self.client.get.return_value.json.return_value = {"timetable": resource}
        with patch.object(
            campus.model.Timetable, "from_resource", return_value=Mock()
        ) as from_resource:
            self.api.timetable["tt-1"].get()
        self.client.get.assert_called_once_with("/api/v1/timetable/tt-1/")
        from_resource.assert_called_once_with(resource)


class TestTimetableMetadata(unittest.TestCase):
    """Metadata.get() parses a TimetableMetadata; update() PATCHes both dates."""

    def setUp(self):
        self.api, self.client = make_api()

    def test_get_parses_timetable_metadata(self):
        resource = {"id": "uid-timetable-1", "start_date": "2026-01-01"}
        self.client.get.return_value.json.return_value = dict(resource)
        with patch.object(
            campus.model.TimetableMetadata, "from_resource", return_value=Mock()
        ) as from_resource:
            self.api.timetable["tt-1"].metadata.get()
        from_resource.assert_called_once_with(resource)

    def test_update_patches_both_dates(self):
        """The API requires start_date and end_date together."""
        self.api.timetable["tt-1"].metadata.update(
            start_date="2026-01-01", end_date="2026-12-31"
        )
        self.client.patch.assert_called_once_with(
            "/api/v1/timetable/tt-1/metadata",
            json={"start_date": "2026-01-01", "end_date": "2026-12-31"},
        )


if __name__ == "__main__":
    unittest.main()
