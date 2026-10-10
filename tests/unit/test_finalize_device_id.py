"""Unit tests for finalize()'s device-id handling (#825).

campus.auth observes the stable campus_device cookie at /authorize and
records the id on the auth session; finalize() copies it onto the login
session it creates, so re-logins from the same browser profile land on
the same device id. A minted fallback keeps non-cookie flows working.
"""

import os
import re
import unittest
from unittest.mock import MagicMock, Mock, patch

import campus.model
import flask

from campus_python.auth.v1 import AuthRoot

SESSION_ID = "auth-session-1"
STABLE_DEVICE_ID = "uid-device-9f3c2a1e-8b4d"
TOKEN_RESOURCE = {
    "id": "token-1",
    "created_at": "2026-10-05T00:00:00+00:00",
    "expires_at": "2026-10-12T00:00:00+00:00",
    "expires_in": 604800,
    "token_type": "Bearer",
    "refresh_token": "refresh-1",
    "scope": "campus.profile",
    "user_id": "user-1",
}


def make_auth_session(device_id: str | None) -> campus.model.AuthSession:
    """An auth session as /sessions/campus/authorization_code returns it."""
    resource = {
        "id": SESSION_ID,
        "created_at": "2026-10-05T00:00:00+00:00",
        "expires_at": "2026-11-01T00:00:00+00:00",
        "provider": "campus",
        "client_id": "client-1",
        "user_id": "user-1",
        "redirect_uri": "https://app.example.org/finalize_login",
        "scopes": ["campus.profile"],
        "state": SESSION_ID,
    }
    if device_id is not None:
        resource["device_id"] = device_id
    return campus.model.AuthSession.from_resource(resource)


def run_finalize(auth: AuthRoot, device_id: str | None) -> dict:
    """Drive finalize() with mocks and return the logins.new kwargs."""
    sessions = MagicMock()
    sessions.from_code.return_value = make_auth_session(device_id)
    sessions[SESSION_ID].finalize.return_value = (
        "https://app.example.org/landing",
        None,
    )
    auth._sessions = sessions
    auth._users = MagicMock()
    logins = MagicMock()
    auth._logins = logins
    # _exchange_code_for_token POSTs to /auth/v1/token
    token_response = Mock()
    token_response.json.return_value = TOKEN_RESOURCE
    auth.client.post.return_value = token_response

    app = flask.Flask(__name__)
    app.secret_key = "test-secret"
    with app.test_request_context(
            "/finalize_login", headers={"User-Agent": "pytest"}):
        auth.finalize(
            state=SESSION_ID, code="code-1", scope="campus.profile"
        )

    assert logins.new.call_count == 1
    return logins.new.call_args.kwargs


class TestFinalizeDeviceId(unittest.TestCase):
    """finalize() copies the auth session's device id onto the login."""

    def setUp(self):
        self.auth, self.client = AuthRoot(json_client=Mock()), Mock()

    def test_session_device_id_is_reused(self):
        """A device id observed by campus.auth rides through unchanged."""
        with patch.dict(os.environ, {"CLIENT_ID": "cid", "CLIENT_SECRET": "sec"}):
            kwargs = run_finalize(self.auth, STABLE_DEVICE_ID)

        self.assertEqual(kwargs["device_id"], STABLE_DEVICE_ID)

    def test_missing_device_id_is_minted(self):
        """No session device id (pre-#825 server, non-cookie flow) mints."""
        with patch.dict(os.environ, {"CLIENT_ID": "cid", "CLIENT_SECRET": "sec"}):
            kwargs = run_finalize(self.auth, None)

        self.assertRegex(kwargs["device_id"], r"^uid-device-")

    def test_minted_and_stable_ids_have_the_same_shape(self):
        """Both paths produce uid-device-* ids of the same form."""
        envvars = {"CLIENT_ID": "cid", "CLIENT_SECRET": "sec"}
        with patch.dict(os.environ, envvars):
            reused = run_finalize(
                AuthRoot(json_client=Mock()), STABLE_DEVICE_ID
            )
            minted = run_finalize(AuthRoot(json_client=Mock()), None)

        shape = re.compile(r"^uid-device-[0-9a-f-]+$")
        self.assertTrue(shape.match(reused["device_id"]))
        self.assertTrue(shape.match(minted["device_id"]))


if __name__ == "__main__":
    unittest.main()
