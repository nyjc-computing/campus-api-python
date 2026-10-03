"""Unit test for Campus._get_token_from_session token rotation.

After exchanging the refresh token, the refreshed token must be the one
returned — the credentials resource still holds the pre-refresh access
token, and refresh-token grants rotate (single-use) on the server.
"""

import os
import unittest
from unittest.mock import MagicMock, Mock, patch

from campus_python import Campus


class TestGetTokenFromSession(unittest.TestCase):
    """The refreshed token, not the stale credentials token, is returned."""

    def test_returns_refreshed_token_after_refresh(self):
        with patch.dict(os.environ, {"CLIENT_ID": "cid", "CLIENT_SECRET": "sec"}):
            campus = Campus(timeout=5)
            auth = campus.auth

            old_token = Mock()
            old_token.is_expired.return_value = True
            new_token = Mock()

            auth._logins = Mock()
            auth._logins.from_session.return_value = Mock(user_id="user1")

            creds_resource = Mock()
            creds_resource.get.return_value = Mock(token=old_token)
            provider = MagicMock()
            provider.__getitem__.return_value = creds_resource
            creds_collection = MagicMock()
            creds_collection.__getitem__.return_value = provider
            auth._credentials = creds_collection

            with patch.object(
                    type(auth), "token", return_value=new_token
            ) as token_mock:
                result = campus._get_token_from_session(force_refresh=True)

            self.assertIs(result, new_token)
            token_mock.assert_called_once_with(
                grant_type="refresh_token",
                refresh_token=old_token.refresh_token,
            )
            creds_resource.update.assert_called_once_with(token=new_token)


if __name__ == "__main__":
    unittest.main()
