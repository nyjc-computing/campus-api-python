"""Unit tests for the files resource (issues #135 by-slug, #125 id).

By-slug routes are terminal upstream: the whole path tail after
``files/by-slug/`` is the slug, so slashes inside the slug must reach
the wire literally (upstream's ``<path:slug>`` converter expects them
unquoted). GET /files/ wraps records in a ``{"data": ...}`` envelope;
content responses are raw bytes. The id-based routes (``files[id]``)
are the management surface and never create.
"""

import os
import unittest
from unittest import mock

os.environ.setdefault("CLIENT_ID", "test-client-id")
os.environ.setdefault("CLIENT_SECRET", "test-client-secret")

import requests

from campus_python.json_client import CampusRequest, CampusResponse
from tests.support import make_api


class TestFilesList(unittest.TestCase):
    """Files.list() unwraps the API's data envelope, optionally filtered."""

    def setUp(self):
        self.api, self.client = make_api()

    def test_list_unwraps_data_envelope(self):
        records = [{"id": "uid-file-1", "slug": "apps/quest-dom"}]
        self.client.get.return_value.json.return_value = {"data": records}
        self.assertEqual(self.api.files.list(), records)
        self.client.get.assert_called_once_with("/api/v1/files/")

    def test_list_passes_prefix_filter(self):
        self.client.get.return_value.json.return_value = {"data": []}
        self.api.files.list(prefix="apps/")
        self.client.get.assert_called_once_with(
            "/api/v1/files/", query={"prefix": "apps/"}
        )

    def test_list_returns_empty_list_for_empty_envelope(self):
        self.client.get.return_value.json.return_value = {"data": []}
        self.assertEqual(self.api.files.list(), [])


class TestFilesBySlug(unittest.TestCase):
    """By-slug surface: literal slug tails, meta, bytes, upsert, delete."""

    def setUp(self):
        self.api, self.client = make_api()

    def test_slug_slashes_stay_literal_in_path(self):
        """Slashes in the slug are not quoted or collapsed."""
        self.client.get.return_value.json.return_value = {}
        self.api.files.get_meta("apps/quest-dom")
        self.client.get.assert_called_once_with(
            "/api/v1/files/by-slug/apps/quest-dom", query={"meta": "1"}
        )

    def test_get_meta_requests_metadata(self):
        meta = {
            "id": "uid-file-1",
            "slug": "apps/quest-dom",
            "content_type": "text/html",
        }
        self.client.get.return_value.json.return_value = meta
        self.assertEqual(self.api.files.get_meta("apps/quest-dom"), meta)
        self.client.get.assert_called_once_with(
            "/api/v1/files/by-slug/apps/quest-dom", query={"meta": "1"}
        )

    def test_get_content_returns_undecoded_bytes(self):
        content = b"<!DOCTYPE html><html><body></body></html>"
        self.client.get.return_value.content = content
        self.assertEqual(
            self.api.files.get_content("apps/quest-dom"), content
        )
        self.client.get.assert_called_once_with(
            "/api/v1/files/by-slug/apps/quest-dom"
        )

    def test_put_by_slug_sends_raw_body_with_content_type(self):
        record = {"id": "uid-file-1", "slug": "apps/quest-dom"}
        self.client.put_data.return_value.json.return_value = record
        result = self.api.files.put_by_slug(
            "apps/quest-dom", b"<html></html>", content_type="text/html"
        )
        self.assertEqual(result, record)
        self.client.put_data.assert_called_once_with(
            "/api/v1/files/by-slug/apps/quest-dom",
            b"<html></html>",
            content_type="text/html",
            query=None,
        )

    def test_put_by_slug_passes_display_name_as_query(self):
        """The optional display name rides upstream's PUT ?name= param."""
        self.client.put_data.return_value.json.return_value = {}
        self.api.files.put_by_slug(
            "apps/quest-dom", b"<html></html>",
            content_type="text/html", name="Quest DOM explorer",
        )
        self.client.put_data.assert_called_once_with(
            "/api/v1/files/by-slug/apps/quest-dom",
            b"<html></html>",
            content_type="text/html",
            query={"name": "Quest DOM explorer"},
        )

    def test_put_by_slug_without_content_type(self):
        self.client.put_data.return_value.json.return_value = {}
        self.api.files.put_by_slug("apps/quest-dom", b"<html></html>")
        self.client.put_data.assert_called_once_with(
            "/api/v1/files/by-slug/apps/quest-dom",
            b"<html></html>",
            content_type=None,
            query=None,
        )

    def test_delete_by_slug(self):
        self.api.files.delete_by_slug("apps/quest-dom")
        self.client.delete.assert_called_once_with(
            "/api/v1/files/by-slug/apps/quest-dom"
        )


class TestFilesById(unittest.TestCase):
    """Id-based management surface (files[id]): never creates, 404s on
    unknown ids upstream. Collection routes keep trailing slashes to
    match the Flask routes."""

    def setUp(self):
        self.api, self.client = make_api()

    def test_get_returns_record_from_id_route(self):
        record = {"id": "uid-file-1", "slug": "apps/quest-dom"}
        self.client.get.return_value.json.return_value = record
        result = self.api.files["uid-file-1"].get()
        self.assertEqual(result, record)
        self.client.get.assert_called_once_with("/api/v1/files/uid-file-1/")

    def test_get_content_returns_undecoded_bytes(self):
        content = b"\x89PNG-bytes"
        self.client.get.return_value.content = content
        self.assertEqual(
            self.api.files["uid-file-1"].get_content(), content
        )
        self.client.get.assert_called_once_with(
            "/api/v1/files/uid-file-1/content/"
        )

    def test_put_content_sends_raw_body_with_content_type(self):
        record = {"id": "uid-file-1", "slug": "apps/quest-dom"}
        self.client.put_data.return_value.json.return_value = record
        result = self.api.files["uid-file-1"].put_content(
            b"<html></html>", content_type="text/html"
        )
        self.assertEqual(result, record)
        self.client.put_data.assert_called_once_with(
            "/api/v1/files/uid-file-1/content/",
            b"<html></html>",
            content_type="text/html",
            query=None,
        )

    def test_put_content_passes_display_name_as_query(self):
        """The optional new display name rides upstream's PUT ?name=."""
        self.client.put_data.return_value.json.return_value = {}
        self.api.files["uid-file-1"].put_content(
            b"<html></html>", content_type="text/html", name="Renamed"
        )
        self.client.put_data.assert_called_once_with(
            "/api/v1/files/uid-file-1/content/",
            b"<html></html>",
            content_type="text/html",
            query={"name": "Renamed"},
        )

    def test_delete_hits_id_route(self):
        self.api.files["uid-file-1"].delete()
        self.client.delete.assert_called_once_with("/api/v1/files/uid-file-1/")


class TestPutDataRawBody(unittest.TestCase):
    """CampusRequest.put_data rides the session with data=, not json=."""

    def setUp(self):
        self.client = CampusRequest(
            base_url="https://api.example.test", mode="device"
        )

    def test_put_data_sends_raw_bytes_and_content_type(self):
        with mock.patch.object(
                self.client._session, "request",
                return_value=mock.Mock(status_code=200)) as request:
            self.client.put_data(
                "/api/v1/files/by-slug/apps/quest-dom",
                b"<html></html>",
                content_type="text/html",
            )
        args, kwargs = request.call_args
        self.assertEqual(args[0], "PUT")
        self.assertEqual(
            args[1], "https://api.example.test/api/v1/files/by-slug/apps/quest-dom"
        )
        self.assertEqual(kwargs["data"], b"<html></html>")
        self.assertEqual(kwargs["headers"], {"Content-Type": "text/html"})
        self.assertIsNone(kwargs["params"])
        self.assertNotIn("json", kwargs)

    def test_put_data_without_content_type_leaves_header_unset(self):
        with mock.patch.object(
                self.client._session, "request",
                return_value=mock.Mock(status_code=200)) as request:
            self.client.put_data("/some/path", b"raw-bytes")
        self.assertIsNone(request.call_args.kwargs["headers"])


class TestCampusResponseContent(unittest.TestCase):
    """CampusResponse.content wraps the transport's undecoded bytes."""

    def test_content_returns_bytes(self):
        response = requests.Response()
        response.status_code = 200
        response._content = b"\x89PNG-bytes"
        wrapped = CampusResponse(response)
        self.assertEqual(wrapped.content, b"\x89PNG-bytes")


if __name__ == "__main__":
    unittest.main()
