"""campus.python.auth.oauth

OAuth 2.0 Device Authorization Flow (RFC 8628) support.

This module provides methods for the device authorization flow,
which is used by CLI and other device applications.

Device-flow parity (issue #87)
------------------------------

The error mapping and polling semantics implemented here pin the
behaviour campus-cli's device flow (campus_cli/auth/login.py) relies
on, so the CLI can retire its raw `requests` copies and drive this
resource instead. Parity table:

| Server response (RFC 8628 §3.5)      | Library behaviour                    |
|--------------------------------------|--------------------------------------|
| authorization_pending                | wait_for_token() invokes on_pending() and keeps polling at the current interval |
| slow_down                            | wait_for_token() raises the poll interval by 5s and the raised interval persists for the remainder of the flow (not just the next attempt) |
| expired_token                        | fatal: AuthenticationError with oauth_error="expired_token" |
| access_denied                        | fatal: AuthenticationError with oauth_error="access_denied" |
| any other 400                        | fatal: AuthenticationError carrying the server's OAuth error code |
| network failure / 5xx                | retried at the current interval on non-final attempts, then ServerError propagates |
| max_attempts exhausted               | fatal: AuthenticationError (timeout) |

The auth server emits token-endpoint errors as the Campus envelope
{"error": {code, message, details.oauth_error}} (dev/staging), the same
envelope with details stripped in production, or the flat RFC 6749 form
{"error": ..., "error_description": ...}; poll_for_token() accepts all
three and normalizes them to AuthenticationError with the OAuth error
code in details (APIError.oauth_error).
"""

import time
from collections.abc import Callable
from typing import Literal

from ... import errors
from ...interface import ResourceRoot

# Fallback poll interval (seconds) when the server omits interval from
# the device_authorize response (RFC 8628 §3.2 default is 5).
DEFAULT_POLL_INTERVAL = 5

# RFC 8628 §3.5: the interval adjustment requested by slow_down.
SLOW_DOWN_ADJUSTMENT = 5


def _parse_oauth_error(payload: dict) -> "tuple[str | None, str]":
    """Extract the OAuth error code and message from a token-endpoint
    error payload.

    Handles the three shapes the auth server emits:

    - flat RFC 6749: {"error": "authorization_pending", ...}
    - Campus envelope (dev/staging): {"error": {"code": "AUTH_...",
      "message": ..., "details": {"oauth_error": ...}}}
    - Campus envelope with details stripped (production): the OAuth
      error is recovered from the AUTH_* code

    Returns:
        (oauth_error, message); oauth_error is None when the payload
        carries neither a details.oauth_error key nor a recoverable
        AUTH_* code.
    """
    error = payload.get("error", "")
    if isinstance(error, str):
        # Flat RFC 6749 format
        return (error or None, payload.get("error_description", ""))

    oauth_error = (error.get("details") or {}).get("oauth_error")
    if not oauth_error:
        oauth_error = errors.oauth_error_from_code(error.get("code", ""))
    return (oauth_error, error.get("message", ""))


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
            oauth_error, message = _parse_oauth_error(resp.json())

            # Map RFC 8628 errors to AuthenticationError; the OAuth error
            # code travels in details so callers can read it back via the
            # APIError.oauth_error property.
            descriptions = {
                "authorization_pending": "Authorization pending",
                "slow_down": "Slow down",
                "expired_token": "Device code has expired",
                "access_denied": "Access denied by user",
            }
            raise errors.AuthenticationError(
                status_code=400,
                error_description=(
                    descriptions.get(oauth_error)
                    or message
                    or "Unknown error"
                ),
                details={"oauth_error": oauth_error},
            )

        resp.raise_for_status()
        return resp.json()

    def wait_for_token(
            self,
            client_id: str,
            device_code: str,
            *,
            interval: int | None = None,
            max_attempts: int = 60,
            on_pending: Callable[[], None] | None = None,
            sleep: Callable[[float], None] = time.sleep,
    ) -> dict:
        """Poll the token endpoint until the device is authorized.

        Implements the polling loop RFC 8628 §3.5 clients must run on
        top of poll_for_token(): authorization_pending keeps polling,
        slow_down raises the interval by SLOW_DOWN_ADJUSTMENT seconds
        with the raised interval persisting for the remainder of the
        flow, network failures are retried on non-final attempts, and
        every other error (expired_token, access_denied, unknown) is
        fatal. See the parity table in this module's docstring.

        Args:
            client_id: The OAuth client ID (e.g., "campus-cli")
            device_code: The device code from request_device_code()
            interval: Minimum seconds between poll attempts, from the
                request_device_code() response. Defaults to
                DEFAULT_POLL_INTERVAL when absent or zero.
            max_attempts: Maximum number of poll attempts; callers
                typically derive this from the device code's expires_in.
            on_pending: Invoked after each authorization_pending response,
                for progress reporting (e.g. printing a dot per poll).
            sleep: The sleep function; injectable for tests.

        Returns:
            The token response dict (access_token, refresh_token, ...),
            as returned by poll_for_token().

        Raises:
            AuthenticationError: On fatal OAuth errors or when
                max_attempts is exhausted without authorization.
            errors.ServerError: When the final attempt fails at the
                network/5xx level.
        """
        poll_interval = (
            max(1, int(interval)) if interval else DEFAULT_POLL_INTERVAL
        )
        last_attempt = max_attempts - 1

        for attempt in range(max_attempts):
            try:
                return self.poll_for_token(
                    client_id=client_id, device_code=device_code
                )
            except errors.AuthenticationError as err:
                if err.oauth_error == "authorization_pending":
                    if on_pending is not None:
                        on_pending()
                    sleep(poll_interval)
                elif err.oauth_error == "slow_down":
                    # RFC 8628 §3.5: the raised interval persists for
                    # the remainder of the flow, not just the next
                    # attempt.
                    poll_interval += SLOW_DOWN_ADJUSTMENT
                    sleep(poll_interval)
                else:
                    raise
            except errors.ServerError:
                # Network failure: retry on non-final attempts only
                if attempt == last_attempt:
                    raise
                sleep(poll_interval)

        raise errors.AuthenticationError(
            error_description=(
                "Device authorization timed out after "
                f"{max_attempts} poll attempts; restart the flow."
            )
        )

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

    def revoke(
            self,
            token: str,
            client_id: str,
            token_type_hint: "str | None" = None,
    ) -> None:
        """Revoke an access or refresh token (RFC 7009).

        Args:
            token: The access or refresh token to revoke
            client_id: The OAuth client the token was issued to
            token_type_hint: Optional "access_token" or "refresh_token"

        Per RFC 7009 section 2.2 the server returns 200 regardless of
        whether the token was found or already revoked, so callers
        cannot use this endpoint to confirm a token's validity.
        """
        json_body: dict = {
            "token": token,
            "client_id": client_id,
        }
        if token_type_hint is not None:
            json_body["token_type_hint"] = token_type_hint
        resp = self.client.post(self.make_path("revoke"), json=json_body)
        resp.raise_for_status()
        return None
