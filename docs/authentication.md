# Authentication

The SDK speaks to Campus Auth for every token concern and holds no
session state of its own. Pick the lane that matches your host:

| Lane | Who | What you use |
|---|---|---|
| [Server mode](#server-mode) | backend services | `CLIENT_ID`/`CLIENT_SECRET` Basic auth; [`with_app_session()`][campus_python.Campus.with_app_session] for app-identity calls |
| [Device flow](#device-flow-public-clients) | CLIs, public clients | [`oauth.request_device_code()`][campus_python.auth.v1.oauth.OAuth.request_device_code] + [`wait_for_token()`][campus_python.auth.v1.oauth.OAuth.wait_for_token] |
| [User sessions](#user-sessions) | Flask apps acting as the logged-in user | [`with_user_session()`][campus_python.Campus.with_user_session] (401 auto-refresh on by default) |
| [Token release](#upstream-tokens-broker) | confidential clients needing upstream tokens | [`broker.token()`][campus_python.auth.v1.broker.Broker.token] (`token_bridge` clients) |

## Server mode

Server-to-server calls authenticate with the OAuth client's Basic
credentials (`CLIENT_ID` / `CLIENT_SECRET`). You can drive tokens
manually — [`auth.token()`][campus_python.auth.v1.AuthRoot.token] for a
`client_credentials` grant, then
[`use_token()`][campus_python.Campus.use_token] — or wrap the work in
the app-session context manager, which acquires and releases the token
for you:

```python
with campus.with_app_session() as client:
    campus.api.timetable.set_current(timetable_id)
# Authorization is cleared on exit
```

## Device flow (public clients)

Public clients (the CLI, desktop tools) have no secret. The RFC 8628
flow walks the user through a verification page:

```python
from campus_python import Campus, errors

campus = Campus(mode="device")

code = campus.auth.oauth.request_device_code(client_id="campus-cli")
print("Enter this code:", code["user_code"], "at", code["verification_uri"])

token = campus.auth.oauth.wait_for_token(
    client_id="campus-cli",
    device_code=code["device_code"],
    interval=code.get("interval"),
    on_pending=lambda: print(".", end=""),   # progress hook per poll
)
campus.use_token(token)
```

`wait_for_token()` implements the full polling loop: `authorization_pending`
keeps polling, `slow_down` raises the interval by 5s for the rest of
the flow, network/5xx failures retry until the final attempt, and
every other error is fatal. Error responses are normalized to
[`AuthenticationError`][campus_python.errors.AuthenticationError] with
the OAuth error code readable via `.oauth_error`, across all three
shapes the auth server emits (dev envelope, production
details-stripped envelope, flat RFC 6749).

Refresh-token grants rotate server-side: present a stored token once
via [`auth.refresh(stored)`][campus_python.auth.v1.AuthRoot.refresh]
and **persist the returned pair before reusing the stale one**.
Revoke with [`oauth.revoke()`][campus_python.auth.v1.oauth.OAuth.revoke]
(RFC 7009 — the server answers 200 whether or not the token existed).

## User sessions

A login session (created by the browser flow in `campus.flask_campus`
via [`logins.new()`][campus_python.auth.v1.logins.LoginSessions.new])
lets server code act as that user. Inside the session context manager
every call carries the user's bearer, and an expired bearer is
re-acquired once automatically:

```python
with campus.with_user_session() as client:            # 401 auto-refresh ON
    campus.api.submissions["sub_ab12"].unsubmit()

with campus.with_user_session(refresh_on_401=False) as client:  # legacy behaviour
    ...
```

How the pieces work:

- The session id resolves **explicit argument > installed provider**
  ([`set_session_id_provider()`][campus_python.auth.v1.sessionstore.set_session_id_provider];
  flask_campus installs one). With neither, methods raise
  `AuthenticationError` naming the seam.
- [`auth.get_token()`][campus_python.auth.v1.AuthRoot.get_token] /
  [`logins.token()`][campus_python.auth.v1.logins.LoginSessions.token]
  re-acquire the session user's bearer via
  `POST /auth/v1/logins/<session_id>/token` — one Basic-authenticated
  call; an expired grant token is rotated server-side, a missing one
  raises `invalid_grant` (re-login required).
- The 401 hook retries the original request once with the fresh
  bearer. It cannot double-execute work: Campus authenticates in a
  `before_request` hook before any handler runs, so a 401 means no
  handler executed.

## Manual bearer control

Any client can be pointed at a token you obtained elsewhere (e.g. a
CLI storing tokens in a keyring):

```python
campus.api.client.set_bearer_authorization(access_token)
campus.auth.client.set_bearer_authorization(access_token)
# ...
campus.revoke_session()   # clear Authorization on both
```

[`use_token()`][campus_python.Campus.use_token] sets both roots in one
call. Raw `CampusRequest` users (public clients driving
`auth.refresh`) can install their own 401 hook:

```python
client.set_unauthorized_hook(
    lambda: campus.auth.refresh(stored, client_id="campus-cli").access_token
)
```

## Upstream tokens (broker)

Confidential clients flagged `token_bridge` can release the bearer's
upstream access tokens (never refresh tokens) for Google and other
connected providers:

```python
token = campus.auth.broker.token("google", integration="classroom",
                                 min_scopes=["classroom.rosters.read"])
```

Denials are typed: 403 carries `details.missing_scopes`, 401 maps to
`AuthenticationError`. Users inspect and revoke their own grants via
[`connections`][campus_python.auth.v1.connections.Connections]
(`connections["google"].delete(user_id=...)` — disconnecting the
campus provider itself is logout and is rejected server-side).

## Hosting in a Flask app

The SDK owns transport and tokens; the `campus.flask_campus`
middleware (in the [campus repo](https://github.com/nyjc-computing/campus))
owns the browser login flow and client-side session storage. The two
layers join through injectable providers:

| Concern | Owner | How the SDK sees it |
|---|---|---|
| Login flow (authorize / code exchange / logout) | `campus.flask_campus.context` | orchestrates this SDK's pure API calls (`sessions.new`, `exchange_code_for_token`, `logins.new`, ...) |
| Session-id storage (browser session keys) | `campus.flask_campus.context` | [`set_session_id_provider()`][campus_python.auth.v1.sessionstore.set_session_id_provider] — ids resolve explicit argument > provider |
| Request-context trace headers | `campus.flask_campus.propagation` | [`tracing.set_request_context_provider()`][campus_python.tracing.set_request_context_provider] — see [Tracing](tracing.md) |
| User-session token lane | this SDK | [`with_user_session()`](#user-sessions) — pure orchestration; the session id arrives via the provider above |

Non-Flask hosts need none of this: the CLI authenticates via device
flow, stores tokens in its own keyring, and sets bearers directly.
