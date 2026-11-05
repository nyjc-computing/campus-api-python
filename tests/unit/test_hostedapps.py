"""Unit tests for the hostedapps resource (#141).

By-slug routes are terminal upstream: the whole path tail after
``hostedapps/by-slug/`` is the slug, so slashes inside the slug must
reach the wire literally. GET /hostedapps wraps records in a
``{"data": ...}`` envelope; content responses are raw bytes; records
deserialize to ``campus.model.HostedApp``.
"""

import os
import unittest
from unittest import mock

os.environ.setdefault("CLIENT_ID", "test-client-id")
os.environ.setdefault("CLIENT_SECRET", "test-client-secret")

from campus.model import HostedApp

from campus_python.api.v1 import ApiRoot


def make_api() -> tuple[ApiRoot, mock.Mock]:
    """Create an ApiRoot backed by a mock JSON client."""
    client = mock.Mock()
    return ApiRoot(json_client=client), client


def record() -> dict:
    return {
        "id": "uid-hostedapp-1",
        "slug": "quest-dom",
        "name": "Quest DOM",
        "content_hash": "a" * 64,
        "size": 1234,
        "content_type": "text/html",
        "status": "published",
    }


class TestHostedAppsList(unittest.TestCase):
    """HostedApps.list() unwraps the envelope and returns models."""

    def setUp(self):
        self.api, self.client = make_api()

    def test_list_unwraps_data_envelope(self):
        self.client.get.return_value.json.return_value = {"data": [record()]}
        apps = self.api.hostedapps.list()
        self.assertEqual(len(apps), 1)
        self.assertIsInstance(apps[0], HostedApp)
        self.assertEqual(apps[0].slug, "quest-dom")
        self.client.get.assert_called_once_with(
            "/api/v1/hostedapps/", query=None
        )

    def test_list_passes_prefix_filter(self):
        self.client.get.return_value.json.return_value = {"data": []}
        self.api.hostedapps.list(prefix="apps/")
        self.client.get.assert_called_once_with(
            "/api/v1/hostedapps/", query={"prefix": "apps/"}
        )


class TestHostedAppsBySlug(unittest.TestCase):
    """By-slug surface: literal slug tails, meta, bytes, upsert, delete."""

    def setUp(self):
        self.api, self.client = make_api()

    def test_slug_slashes_stay_literal_in_path(self):
        """Slashes in the slug are not quoted or collapsed."""
        self.client.get.return_value.json.return_value = record()
        self.api.hostedapps.get_meta("games/quest-dom")
        self.client.get.assert_called_once_with(
            "/api/v1/hostedapps/by-slug/games/quest-dom",
            query={"meta": "1"},
        )

    def test_get_meta_returns_model(self):
        self.client.get.return_value.json.return_value = record()
        app = self.api.hostedapps.get_meta("quest-dom")
        self.assertIsInstance(app, HostedApp)
        self.assertEqual(app.name, "Quest DOM")

    def test_get_content_returns_undecoded_bytes(self):
        content = b"<!DOCTYPE html><html><body></body></html>"
        self.client.get.return_value.content = content
        self.assertEqual(
            self.api.hostedapps.get_content("quest-dom"), content
        )
        self.client.get.assert_called_once_with(
            "/api/v1/hostedapps/by-slug/quest-dom"
        )

    def test_put_by_slug_sends_raw_body_with_content_type(self):
        self.client.put_data.return_value.json.return_value = record()
        app = self.api.hostedapps.put_by_slug(
            "quest-dom", b"<html></html>", content_type="text/html"
        )
        self.assertIsInstance(app, HostedApp)
        self.client.put_data.assert_called_once_with(
            "/api/v1/hostedapps/by-slug/quest-dom",
            b"<html></html>",
            content_type="text/html",
            query=None,
        )

    def test_put_by_slug_passes_display_name_as_query(self):
        """The optional display name rides upstream's PUT ?name= param."""
        self.client.put_data.return_value.json.return_value = record()
        self.api.hostedapps.put_by_slug(
            "quest-dom", b"<html></html>", name="Quest DOM explorer"
        )
        self.client.put_data.assert_called_once_with(
            "/api/v1/hostedapps/by-slug/quest-dom",
            b"<html></html>",
            content_type=None,
            query={"name": "Quest DOM explorer"},
        )

    def test_delete_by_slug(self):
        self.api.hostedapps.delete_by_slug("quest-dom")
        self.client.delete.assert_called_once_with(
            "/api/v1/hostedapps/by-slug/quest-dom"
        )


if __name__ == "__main__":
    unittest.main()
