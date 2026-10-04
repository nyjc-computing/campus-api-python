"""Contract tests for the audit service client (issue #77).

Routes mirror campus/audit/routes/ (campus weekly, via the trailing-
slash create_blueprint registrations under /audit/v1):
- /audit/v1/apikeys/... (collection/item slash rules, regenerate leaf)
- /audit/v1/traces/... (collection slash, /search leaf, spans nesting)

Bool query values must reach the server as lowercase literals
(flask_campus _BOOL_LITERALS accepts true/false/1/0 only).
"""

import os
import unittest
from unittest.mock import Mock, patch

from campus_python import Campus
from campus_python.audit.v1 import AuditRoot

API_KEY_RESOURCE = {
    "id": "akm123",
    "created_at": "2026-10-04T00:00:00+00:00",
    "name": "ci-ingest",
    "owner_id": "user1",
    "scopes": "traces:write",
    "rate_limit": 100,
    "revoked": False,
}

TRACE_SUMMARY = {
    "trace_id": "a" * 32,
    "root_span_id": "b" * 16,
    "path": "/api/v1/timetable/",
    "status_code": 200,
}


def make_audit() -> tuple[AuditRoot, Mock]:
    """Create an AuditRoot backed by a mock JSON client."""
    client = Mock()
    return AuditRoot(json_client=client), client


class TestAPIKeys(unittest.TestCase):
    """API key management routes under /audit/v1/apikeys."""

    def setUp(self):
        self.audit, self.client = make_audit()

    def test_new_posts_required_and_optional_fields(self):
        self.client.post.return_value.json.return_value = {
            **API_KEY_RESOURCE,
            "api_key": "audit_v1_abc",
        }
        record = self.audit.apikeys.new(
            name="ci-ingest",
            owner_id="user1",
            scopes=["traces:write"],
            rate_limit=100,
        )
        self.client.post.assert_called_once_with(
            "/audit/v1/apikeys/",
            json={
                "name": "ci-ingest",
                "owner_id": "user1",
                "scopes": ["traces:write"],
                "rate_limit": 100,
            },
        )
        self.assertEqual(record["api_key"], "audit_v1_abc")

    def test_list_sends_lowercase_active_only(self):
        self.client.get.return_value.json.return_value = {
            "api_keys": [API_KEY_RESOURCE], "count": 1
        }
        result = self.audit.apikeys.list(owner_id="user1", active_only=False)
        self.client.get.assert_called_once_with(
            "/audit/v1/apikeys/",
            query={"owner_id": "user1", "active_only": "false"},
        )
        self.assertEqual(result["count"], 1)

    def test_get_uses_trailing_slash(self):
        self.client.get.return_value.json.return_value = API_KEY_RESOURCE
        self.audit.apikeys["akm123"].get()
        self.client.get.assert_called_once_with("/audit/v1/apikeys/akm123/")

    def test_update_requires_a_field(self):
        with self.assertRaises(ValueError):
            self.audit.apikeys["akm123"].update()
        self.client.patch.assert_not_called()

    def test_update_patches_mutable_fields(self):
        self.client.patch.return_value.json.return_value = API_KEY_RESOURCE
        self.audit.apikeys["akm123"].update(scopes=["traces:read"])
        self.client.patch.assert_called_once_with(
            "/audit/v1/apikeys/akm123/",
            json={"scopes": ["traces:read"]},
        )

    def test_revoke_deletes_trailing_slash(self):
        self.audit.apikeys["akm123"].revoke()
        self.client.delete.assert_called_once_with("/audit/v1/apikeys/akm123/")

    def test_regenerate_returns_new_plaintext(self):
        self.client.post.return_value.json.return_value = {
            "key": "audit_v1_new"
        }
        key = self.audit.apikeys["akm123"].regenerate()
        self.client.post.assert_called_once_with(
            "/audit/v1/apikeys/akm123/regenerate"
        )
        self.assertEqual(key, "audit_v1_new")


class TestTraces(unittest.TestCase):
    """Trace ingest/query routes under /audit/v1/traces."""

    def setUp(self):
        self.audit, self.client = make_audit()

    def test_ingest_wraps_spans(self):
        self.client.post.return_value.json.return_value = {
            "created": ["b" * 16]
        }
        spans = [{"trace_id": "a" * 32, "span_id": "b" * 16}]
        result = self.audit.traces.ingest(spans)
        self.client.post.assert_called_once_with(
            "/audit/v1/traces/", json={"spans": spans}
        )
        self.assertEqual(result["created"], ["b" * 16])

    def test_list_passes_pagination_query(self):
        self.client.get.return_value.json.return_value = {
            "traces": [TRACE_SUMMARY],
            "cursor": {"next": "cur2", "has_more": True},
        }
        result = self.audit.traces.list(since="2026-10-01T00:00:00Z", limit=10)
        self.client.get.assert_called_once_with(
            "/audit/v1/traces/",
            query={"since": "2026-10-01T00:00:00Z", "limit": 10},
        )
        self.assertTrue(result["cursor"]["has_more"])

    def test_search_gets_leaf_route_with_filters(self):
        self.client.get.return_value.json.return_value = {
            "traces": [], "cursor": {"next": None, "has_more": False}
        }
        self.audit.traces.search(path="/api/v1/timetable/", status=404)
        self.client.get.assert_called_once_with(
            "/audit/v1/traces/search",
            query={"path": "/api/v1/timetable/", "status": 404},
        )

    def test_trace_get_returns_tree_envelope(self):
        self.client.get.return_value.json.return_value = {
            "trace_id": "a" * 32,
            "root_span": {"span_id": "b" * 16, "children": []},
        }
        result = self.audit.traces["a" * 32].get()
        self.client.get.assert_called_once_with(f"/audit/v1/traces/{'a' * 32}/")
        self.assertIn("root_span", result)

    def test_spans_list_uses_trailing_slash(self):
        self.client.get.return_value.json.return_value = {"spans": []}
        self.audit.traces["a" * 32].spans.list()
        self.client.get.assert_called_once_with(
            f"/audit/v1/traces/{'a' * 32}/spans/"
        )

    def test_span_get_uses_trailing_slash(self):
        self.client.get.return_value.json.return_value = {"span_id": "b" * 16}
        self.audit.traces["a" * 32].spans["b" * 16].get()
        self.client.get.assert_called_once_with(
            f"/audit/v1/traces/{'a' * 32}/spans/{'b' * 16}/"
        )


class TestCampusAuditWiring(unittest.TestCase):
    """Campus.audit resolves its own URL and Bearer-auths the API key."""

    def test_audit_root_uses_audit_url_and_key(self):
        with patch.dict("os.environ", {
            "CAMPUS_AUDIT_URL": "https://audit.example.test",
            "AUDIT_API_KEY": "audit_v1_testkey",
        }):
            campus = Campus(timeout=5, mode="device")
            audit = campus.audit
        self.assertEqual(audit.base_url, "https://audit.example.test")
        self.assertEqual(
            audit.client._session.headers["Authorization"],
            "Bearer audit_v1_testkey",
        )
        self.assertEqual(audit.url_prefix, "/audit/v1")

    def test_audit_requires_api_key(self):
        environ = dict(os.environ)
        environ["CAMPUS_AUDIT_URL"] = "https://audit.example.test"
        environ.pop("AUDIT_API_KEY", None)
        with patch("os.environ", environ):
            campus = Campus(timeout=5, mode="device")
            with self.assertRaises(OSError):
                campus.audit


if __name__ == "__main__":
    unittest.main()
