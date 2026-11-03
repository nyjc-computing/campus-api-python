"""Unit tests for the flask-lane deprecations (0.4.0, removal 0.5.0).

The browser login flow (authorize/finalize/logout/push_context), the
legacy flask.session id reads, and the built-in propagation reader all
warn on use — flask_campus (the supported middleware) never touches
any of them, so production hosts with it installed are silent.
"""

import os
import unittest
from unittest.mock import Mock

import flask

from campus_python import tracing
from campus_python.auth.v1 import AuthRoot, set_session_id_provider


def make_auth() -> tuple[AuthRoot, Mock]:
    client = Mock()
    client.base_url = "https://auth.test"
    client.authorization = None
    return AuthRoot(json_client=client), client


def request_context():
    app = flask.Flask(__name__)
    app.secret_key = "test-secret"
    return app.test_request_context()


class TestAuthFlowDeprecations(unittest.TestCase):
    """The four flask-coupled flow methods warn unconditionally."""

    def setUp(self):
        self.auth, self.client = make_auth()
        # The warning fires before any flow logic; sessions.new is
        # stubbed only so a successful authorize reaches its redirect
        # (which reads CLIENT_ID for the authorize URL params).
        self.auth.sessions.new = Mock(
            return_value=Mock(id="state-1", redirect_uri="u", device_id="d")
        )
        self.saved_client_id = os.environ.get("CLIENT_ID")
        os.environ["CLIENT_ID"] = "uid-client-test"
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        if self.saved_client_id is None:
            os.environ.pop("CLIENT_ID", None)
        else:
            os.environ["CLIENT_ID"] = self.saved_client_id

    def test_authorize_warns(self):
        with request_context(), self.assertWarns(DeprecationWarning):
            self.auth.authorize(target="https://app.test/cb")

    def test_push_context_warns(self):
        with request_context(), self.assertWarns(DeprecationWarning):
            self.auth.push_context()

    def test_logout_warns(self):
        with request_context(), self.assertWarns(DeprecationWarning):
            self.auth.logout()

    def test_finalize_warns_before_rejection(self):
        """The warning fires before the flow's API calls: even a
        rejected code (from_code raising) warns first."""
        self.auth.sessions.from_code = Mock(
            side_effect=RuntimeError("stop here")
        )
        with request_context(), self.assertWarns(DeprecationWarning):
            with self.assertRaises(RuntimeError):
                self.auth.finalize(state="s", code="c", scope="x")


class TestLegacyLaneReadDeprecations(unittest.TestCase):
    """Legacy flask.session id reads warn only when no provider is
    installed (the supported path — provider or explicit id — never
    warns)."""

    def setUp(self):
        self.auth, self.client = make_auth()
        self.addCleanup(set_session_id_provider, None)

    def test_logins_has_session_warns_without_provider(self):
        with request_context(), self.assertWarns(DeprecationWarning):
            flask.session["logins_login_id"] = "login-1"
            self.assertTrue(self.auth.logins.has_session())

    def test_logins_token_via_provider_does_not_warn(self):
        """The supported lane: provider-resolved id, zero warnings."""
        set_session_id_provider(
            lambda kind: "login-1" if kind == "login" else None
        )
        self.client.post.return_value = Mock()
        self.client.post.return_value.json.return_value = {
            "access_token": "tok",
            "token_type": "Bearer",
            "expires_in": 432000,
            "scope": "campus.profile",
            "user_id": "user1",
        }
        with request_context():
            import warnings as _warnings

            with _warnings.catch_warnings(record=True) as caught:
                _warnings.simplefilter("always")
                self.auth.logins.token()
        deprecations = [
            w for w in caught
            if issubclass(w.category, DeprecationWarning)
        ]
        self.assertEqual(deprecations, [])

    def test_sessions_has_session_warns_without_provider(self):
        with request_context(), self.assertWarns(DeprecationWarning):
            flask.session["campus_session_id"] = "sess-1"
            self.assertTrue(self.auth.sessions.has_session())


class TestBuiltinReaderDeprecation(unittest.TestCase):
    """The built-in propagation reader warns only for in-request
    reads; the out-of-request path (boot journey) stays silent."""

    def tearDown(self):
        tracing.set_request_context_provider(None)

    def test_in_request_read_warns_without_provider(self):
        app = flask.Flask(__name__)
        with app.test_request_context("/"):
            flask.g.trace_id = "a" * 32
            flask.g.span_id = "b" * 16
            with self.assertWarns(DeprecationWarning):
                tracing.propagation_headers()

    def test_provider_installed_does_not_warn(self):
        tracing.set_request_context_provider(lambda: {})
        app = flask.Flask(__name__)
        with app.test_request_context("/"):
            import warnings as _warnings

            with _warnings.catch_warnings(record=True) as caught:
                _warnings.simplefilter("always")
                tracing.propagation_headers()
        deprecations = [
            w for w in caught
            if issubclass(w.category, DeprecationWarning)
        ]
        self.assertEqual(deprecations, [])

    def test_out_of_request_does_not_warn(self):
        import warnings as _warnings

        with _warnings.catch_warnings(record=True) as caught:
            _warnings.simplefilter("always")
            tracing.propagation_headers()
        deprecations = [
            w for w in caught
            if issubclass(w.category, DeprecationWarning)
        ]
        self.assertEqual(deprecations, [])


if __name__ == "__main__":
    unittest.main()
