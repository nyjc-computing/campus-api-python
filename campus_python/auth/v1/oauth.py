"""campus.python.auth.oauth

OAuth 2.0 Device Authorization Flow (RFC 8628) support.

This module provides methods for the device authorization flow,
which is used by CLI and other device applications.
"""

from typing import Literal

from ... import errors
from ...interface import ResourceRoot


class OAuth(ResourceRoot):
    """OAuth 2.0 Device Authorization Flow resource.

    Provides methods for device authorization flow used by CLI
    and other applications with limited input capabilities.

    Reference: https://datatracker.ietf.org/doc/html/rfc8628
    """

    # All OAuth endpoints live under /auth/v1/oauth (campus/auth/routes/
    # oauth.py); the auth app enables strict_slashes, so the slash-less
    # relative paths built here must match the route rules exactly.
    url_prefix = "/auth/v1/oauth"

    def __init__(self, root: ResourceRoot):
        super().__init__(json_client=root.client)
        self._root = root

    def request_device_code(
            self,
            client_id: str,
    ) -> dict:
        """Request a device code for the device authorization flow.

        Args:
            client_id: The OAuth client ID (e.g., "campus-cli")

        Returns:
            Dict containing:
            - device_code: The device code for polling
            - user_code: The code the user must enter
            - verification_uri: The URI where the user enters the code
            - verification_uri_complete: The URI with user_code pre-filled
            - expires_in: Seconds until the device code expires
            - interval: Minimum seconds between polling attempts

        Raises:
            AuthenticationError: If client_id is invalid
        """
        json_body = {
            "client_id": client_id,
        }
        resp = self.client.post(self.make_path("device_authorize"), json=json_body)
        resp.raise_for_status()
        return resp.json()

    def poll_for_token(
            self,
            client_id: str,
            device_code: str,
    ) -> dict:
        """Poll the token endpoint for an access token.

        Args:
            client_id: The OAuth client ID
            device_code: The device code received from request_device_code()

        Returns:
            Dict containing:
            - access_token: The access token
            - token_type: Token type (usually "Bearer")
            - expires_in: Seconds until token expires
            - refresh_token: The refresh token
            - scope: Granted scopes

        Raises:
            AuthenticationError: With specific error codes:
            - authorization_pending: User hasn't completed auth yet
            - slow_down: Client is polling too fast
            - expired_token: Device code has expired
            - access_denied: User denied the authorization
        """
        json_body = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": client_id,
            "device_code": device_code,
        }
        resp = self.client.post(self.make_path("token"), json=json_body)

        # Handle OAuth error responses
        if resp.status_code == 400:
            error_data = resp.json()
            error = error_data.get("error", "")

            # Map RFC 8628 errors to AuthenticationError; the OAuth error
            # code travels in details so callers can read it back via the
            # APIError.oauth_error property.
            if error == "authorization_pending":
                raise errors.AuthenticationError(
                    error_description="Authorization pending",
                    details={"oauth_error": "authorization_pending"}
                )
            elif error == "slow_down":
                raise errors.AuthenticationError(
                    error_description="Slow down",
                    details={"oauth_error": "slow_down"}
                )
            elif error == "expired_token":
                raise errors.AuthenticationError(
                    error_description="Device code has expired",
                    details={"oauth_error": "expired_token"}
                )
            elif error == "access_denied":
                raise errors.AuthenticationError(
                    error_description="Access denied by user",
                    details={"oauth_error": "access_denied"}
                )
            else:
                raise errors.AuthenticationError(
                    error_description=error_data.get("error_description", "Unknown error"),
                    details={"oauth_error": error}
                )

        resp.raise_for_status()
        return resp.json()

    def authorize_device(
            self,
            user_code: str,
            user_id: str,
    ) -> dict:
        """Authorize a device code with a user ID.

        This is called by the verification page when a user submits
        their user code.

        Args:
            user_code: The user code from the CLI
            user_id: The user ID of the authorizing user

        Returns:
            Dict with success status

        Raises:
            NotFoundError: If user_code is invalid or expired
            ConflictError: If user_code is already authorized/denied
        """
        json_body = {
            "user_code": user_code,
            "user_id": user_id,
        }
        resp = self.client.post(
            self.make_path("device/authorize"), json=json_body
        )
        resp.raise_for_status()
        return resp.json()
