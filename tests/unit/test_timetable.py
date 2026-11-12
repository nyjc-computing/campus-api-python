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

from campus_python import errors
from tests.support import json_response, make_api


class TestTimetablesList(unittest.TestCase):
    """Timetables.list() must unwrap the API's data envelope."""

    def setUp(self):
        self.api, self.client = make_api()

    def test_list_metadata_unwraps_data_envelope(self):
        metadata = [{"id": "uid-timetable-1", "start_date": "2026-01-01"}]
        self.client.get.return_value.json.return_value = {"data": metadata}
        with patch.object(
            campus.model.TimetableMetadata, "from_resource", return_value=Mock()
        ) as from_resource:
            self.api.timetable.list_metadata()
        self.client.get.assert_called_once_with("/api/v1/timetable/metadata/")
        from_resource.assert_called_once_with(metadata[0])

    def test_list_metadata_returns_empty_list_for_empty_envelope(self):
        self.client.get.return_value.json.return_value = {"data": []}
        self.assertEqual(self.api.timetable.list_metadata(), [])


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
    """Metadata.get() parses a TimetableMetadata; update() PATCHes the
    subset it is given (label and/or dates, campus-model 0.1.7)."""

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
        self.client.patch.return_value.json.return_value = {"id": "tt-1"}
        with patch.object(
            campus.model.TimetableMetadata, "from_resource", return_value=Mock()
        ) as from_resource:
            self.api.timetable["tt-1"].metadata.update(
                start_date="2026-01-01", end_date="2026-12-31"
            )
        self.client.patch.assert_called_once_with(
            "/api/v1/timetable/tt-1/metadata",
            json={"start_date": "2026-01-01", "end_date": "2026-12-31"},
        )
        from_resource.assert_called_once_with({"id": "tt-1"})

    def test_update_patches_label_only(self):
        """A rename touches only the label — dates stay untouched."""
        self.client.patch.return_value.json.return_value = {
            "id": "tt-1",
            "filename": "2026.xml",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "label": "2026 Term 1",
        }
        self.api.timetable["tt-1"].metadata.update(label="2026 Term 1")
        self.client.patch.assert_called_once_with(
            "/api/v1/timetable/tt-1/metadata",
            json={"label": "2026 Term 1"},
        )

    def test_update_without_fields_raises(self):
        """An empty update is a client-side error, not a wasted call."""
        with self.assertRaises(ValueError):
            self.api.timetable["tt-1"].metadata.update()
        self.client.patch.assert_not_called()

    def test_clear_label_patches_null(self):
        """Clearing the label is spelled label=null (never omitted)."""
        self.client.patch.return_value.json.return_value = {
            "id": "tt-1",
            "filename": "2026.xml",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "label": None,
        }
        self.api.timetable["tt-1"].metadata.clear_label()
        self.client.patch.assert_called_once_with(
            "/api/v1/timetable/tt-1/metadata",
            json={"label": None},
        )


class TestTimetableAttachments(unittest.TestCase):
    """Attachments: list/upload/content/delete against the
    /timetable/<id>/attachments surface."""

    def setUp(self):
        self.api, self.client = make_api()
        self.attachments = self.api.timetable["tt-1"].attachments

    def test_list_unwraps_data_envelope(self):
        records = [{"id": "uid-file-1", "name": "breaks.pdf"}]
        self.client.get.return_value.json.return_value = {"data": records}
        self.assertEqual(self.attachments.list(), records)
        self.client.get.assert_called_once_with("/api/v1/timetable/tt-1/attachments/")

    def test_upload_posts_raw_bytes_with_filename_query(self):
        record = {"id": "uid-file-1", "name": "breaks.pdf"}
        self.client.post_data.return_value.json.return_value = record
        result = self.attachments.upload(
            b"%PDF-1.4", "breaks.pdf", content_type="application/pdf"
        )
        self.client.post_data.assert_called_once_with(
            "/api/v1/timetable/tt-1/attachments/",
            b"%PDF-1.4",
            content_type="application/pdf",
            query={"filename": "breaks.pdf"},
        )
        self.assertEqual(result, record)

    def test_upload_requires_status_ok(self):
        self.client.post_data.return_value = json_response({}, status_code=422)
        with self.assertRaises(errors.APIError):
            self.attachments.upload(b"%PDF-1.4", "breaks.pdf")

    def test_get_content_returns_bytes(self):
        self.client.get.return_value.content = b"%PDF-1.4"
        self.assertEqual(self.attachments.get_content("uid-file-1"), b"%PDF-1.4")
        self.client.get.assert_called_once_with(
            "/api/v1/timetable/tt-1/attachments/uid-file-1/content/"
        )

    def test_delete_removes_by_attachment_id(self):
        self.attachments.delete("uid-file-1")
        self.client.delete.assert_called_once_with(
            "/api/v1/timetable/tt-1/attachments/uid-file-1/"
        )


if __name__ == "__main__":
    unittest.main()
