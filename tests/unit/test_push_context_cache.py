"""Unit tests for the push_context user cache (issue #57).

push_context() runs as an app-wide before_request hook, so a
session-carrying browser paid 1-2 upstream auth calls before every
route. The resolved user is now cached in-process per session for
user_cache_ttl seconds: warm requests make zero upstream calls, and
logout() and stale sessions evict immediately.
"""

import unittest
from unittest.mock import Mock

import flask

from campus_python import errors
from campus_python.auth.v1 import AuthRoot

USER_RESOURCE = {
    "id": "user-1",
    "created_at": "2026-10-01T00:00:00+00:00",
    "email": "student@nyjc.edu.sg",
    "name": "Test Student",
}

AUTH_SESSION = {
    "id": "auth-session-1",
    "created_at": "2026-10-01T00:00:00+00:00",
    "expires_at": "2026-11-01T00:00:00+00:00",
    "provider": "campus",
    "client_id": "client-1",
    "user_id": "user-1",
    "redirect_uri": "https://app.example.org/finalize_login",
    "scopes": [],
}

LOGIN_SESSION = {
    "id": "login-1",
    "created_at": "2026-10-01T00:00:00+00:00",
    "expires_at": "2026-11-01T00:00:00+00:00",
    "client_id": "client-1",
    "user_id": "user-1",
    "device_id": "device-1",
    "agent_string": "pytest",
}


def make_auth() -> tuple[AuthRoot, Mock]:
    """Create an AuthRoot backed by a mock JSON client."""
    client = Mock()
    return AuthRoot(json_client=client), client


def session_context():
    """A Flask request context with a writable session."""
    app = flask.Flask(__name__)
    app.secret_key = "test-secret"
    return app.test_request_context()


def ok_response(body: dict) -> Mock:
    response = Mock()
    response.json.return_value = body
    return response


def not_found_response() -> Mock:
    response = Mock()
    response.raise_for_status.side_effect = errors.NotFoundError(
        error_description="not found"
    )
    return response


def route_gets(client: Mock, **routes: Mock) -> None:
    """Route client.get calls to responses by path substring."""
    def get(path, *_args, **_kwargs):
        for fragment, response in routes.items():
            if fragment in path:
                return response
        raise AssertionError(f"unexpected GET path: {path}")
    client.get.side_effect = get


class TestSessionBranchCache(unittest.TestCase):
    """The auth-session branch caches under ("session", id)."""

    def setUp(self):
        self.auth, self.client = make_auth()

    def push(self):
        with session_context():
            flask.session["campus_session_id"] = "auth-session-1"
            route_gets(
                self.client,
                **{
                    "sessions/campus": ok_response(AUTH_SESSION),
                    "users/": ok_response(USER_RESOURCE),
                },
            )
            self.auth.push_context()
            return flask.g.user, flask.g.device

    def test_first_request_resolves_via_two_calls(self):
        user, device = self.push()
        self.assertEqual(user.email, USER_RESOURCE["email"])
        self.assertIsNone(device)
        self.assertEqual(self.client.get.call_count, 2)

    def test_warm_request_makes_no_upstream_calls(self):
        self.push()
        calls_after_warm = self.client.get.call_count
        user, _ = self.push()
        self.assertEqual(self.client.get.call_count, calls_after_warm)
        self.assertEqual(user.name, USER_RESOURCE["name"])

    def test_ttl_zero_forces_refetch_every_request(self):
        self.auth.user_cache_ttl = 0
        self.push()
        calls_first = self.client.get.call_count
        self.push()
        self.assertGreater(self.client.get.call_count, calls_first)

    def test_mutating_g_user_does_not_poison_cache(self):
        user, _ = self.push()
        user.name = "tampered"
        user_again, _ = self.push()
        self.assertEqual(user_again.name, USER_RESOURCE["name"])


class TestLoginBranchCache(unittest.TestCase):
    """The login-session branch caches under ("login", id) with device."""

    def setUp(self):
        self.auth, self.client = make_auth()

    def push(self):
        with session_context():
            flask.session["logins_login_id"] = "login-1"
            route_gets(
                self.client,
                **{
                    "logins/": ok_response(LOGIN_SESSION),
                    "users/": ok_response(USER_RESOURCE),
                },
            )
            self.auth.push_context()
            return flask.g.user, flask.g.device

    def test_first_request_resolves_user_and_device(self):
        user, device = self.push()
        self.assertEqual(user.id, USER_RESOURCE["id"])
        self.assertEqual(device, "device-1")
        self.assertEqual(self.client.get.call_count, 2)

    def test_warm_request_makes_no_upstream_calls(self):
        self.push()
        calls_after_warm = self.client.get.call_count
        user, device = self.push()
        self.assertEqual(self.client.get.call_count, calls_after_warm)
        self.assertEqual(device, "device-1")

    def test_logout_evicts_the_cached_user(self):
        self.push()
        self.client.delete.return_value = ok_response({})
        with session_context():
            flask.session["logins_login_id"] = "login-1"
            self.auth.logout()
        self.push()
        # from_session + revoke used get/delete after logout; the
        # re-resolve adds two more GETs on top of the login lookup.
        self.assertGreaterEqual(self.client.get.call_count, 4)


class TestStaleSessionEviction(unittest.TestCase):
    """A session the auth service no longer knows is evicted."""

    def test_stale_auth_session_clears_cookie_and_cache(self):
        auth, client = make_auth()
        with session_context():
            flask.session["campus_session_id"] = "auth-session-1"
            route_gets(
                client,
                **{"sessions/campus": not_found_response()},
            )
            auth.push_context()
            self.assertIsNone(flask.g.user)
            self.assertNotIn("campus_session_id", flask.session)
            # A later valid session re-resolves instead of trusting cache
            flask.session["campus_session_id"] = "auth-session-2"
            route_gets(
                client,
                **{
                    "sessions/campus": ok_response(AUTH_SESSION),
                    "users/": ok_response(USER_RESOURCE),
                },
            )
            auth.push_context()
            self.assertEqual(flask.g.user.email, USER_RESOURCE["email"])
            self.assertEqual(client.get.call_count, 3)

    def test_stale_login_session_clears_cookie(self):
        auth, client = make_auth()
        with session_context():
            flask.session["logins_login_id"] = "login-1"
            route_gets(client, **{"logins/": not_found_response()})
            auth.push_context()
            self.assertIsNone(flask.g.user)
            self.assertNotIn("logins_login_id", flask.session)


if __name__ == "__main__":
    unittest.main()
