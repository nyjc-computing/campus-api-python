# Custom clients

The SDK talks to Campus through two abstract interfaces in
`campus_python.json_client`. The default implementation is
[`CampusRequest`][campus_python.json_client.CampusRequest]
(requests-based, with trace propagation and the optional 401
auto-refresh hook), but any host can bring its own transport — the
interfaces were designed to wrap `flask.testing.FlaskClient` as much
as `requests`.

## The `JsonClient` contract

A client must implement:

- the six verbs — [`get`][campus_python.json_client.interface.JsonClient.get],
  [`post`][campus_python.json_client.interface.JsonClient.post],
  [`put`][campus_python.json_client.interface.JsonClient.put],
  [`put_data`][campus_python.json_client.interface.JsonClient.put_data]
  (raw, non-JSON body — file/hosted-app uploads),
  [`delete`][campus_python.json_client.interface.JsonClient.delete],
  [`patch`][campus_python.json_client.interface.JsonClient.patch] —
  each returning a `JsonResponse`;
- authorization control: the
  [`authorization`][campus_python.json_client.interface.JsonClient.authorization]
  property plus
  [`set_basic_authorization()`][campus_python.json_client.interface.JsonClient.set_basic_authorization],
  [`set_bearer_authorization()`][campus_python.json_client.interface.JsonClient.set_bearer_authorization],
  and [`reset_authorization()`][campus_python.json_client.interface.JsonClient.reset_authorization]
  (the session managers swap tokens through these);
- a `base_url`.

::: campus_python.json_client.interface.JsonClient

## The `JsonResponse` contract

Responses expose `status_code`, `headers`, `text`, `content` (bytes —
file content is binary; callers decode), and `json()`. Implement
`raise_for_status()` by delegating to the base-class mapping: it
parses the Campus error envelope (and the legacy `error_code` form)
into the right [`APIError`][campus_python.errors.APIError] subclass,
recovering OAuth errors from `AUTH_*` codes when production strips
envelope details.

::: campus_python.json_client.interface.JsonResponse

## Optional capabilities

Two capabilities are deliberately **not** part of the ABC. Feature-detect
them instead of assuming:

- **Default headers** — `client.set_default_header(name, value)` (#837).
  The ABC default raises `NotImplementedError`, so a client that cannot
  carry default headers refuses loudly rather than dropping them.
- **401 auto-refresh hook** — `client.set_unauthorized_hook(fn)` (#89).
  Present on `CampusRequest` (and used by
  [`with_user_session()`][campus_python.Campus.with_user_session],
  which feature-detects via `isinstance`). The hook runs at most once
  per request: return the new bearer token to retry with, or `None` to
  surface the original 401.

## The default transport

[`CampusRequest`][campus_python.json_client.CampusRequest] is the
requests-based client the facade builds; its optional capabilities
(`set_default_header`, `set_unauthorized_hook`) are what custom
clients may mirror.

::: campus_python.json_client.CampusRequest

## Building one

The interfaces exist so hosts can point the SDK at an in-process WSGI
app (unit/integration tests without a network) or an exotic transport.
The shape:

```python
from campus_python.json_client.interface import JsonClient, JsonResponse

class FlaskTestClientResponse(JsonResponse):
    def __init__(self, response):
        self._response = response          # werkzeug.test.TestResponse
    # implement status_code / headers / text / content / json()
    # and reuse JsonResponse.raise_for_status (do not override)

class FlaskTestClient(JsonClient):
    def __init__(self, test_client, base_url="https://campus.test"):
        self.base_url = base_url
        self._client = test_client
    # implement the six verbs as test_client.open(...) calls,
    # plus the authorization methods
```

Then construct the service roots directly against it:

```python
from campus_python.api.v1 import ApiRoot

api = ApiRoot(json_client=FlaskTestClient(flask_app.test_client()))
api.assignments.list()
```

The repo's own test suite stays one level simpler: resource unit tests
drive Mock clients through the shared factories in `tests/support.py`
(`make_api`, `make_auth`, `json_response`), pinning recorded calls
rather than running a real WSGI stack.
