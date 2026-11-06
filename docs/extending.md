# Extending the SDK

New resources and endpoints follow one pattern: a module in the
service's `v1/` package defines a `ResourceCollection` (the URL
collection), a nested `Resource` (a single item), and thin methods
that send one request each. This page is the toolkit + conventions;
the reference for every base class is embedded below.

## The three-line method

Endpoint methods send through the [`Transport`][campus_python.interface.ResourceRoot]
verb helpers, keep the envelope key inline, and map records to models
at the call site:

```python
class Circles(ResourceCollection):
    path = "circles"

    def list(self) -> "list[campus.model.Circle]":
        body = self._get_json(self.make_path())          # GET; raises on 4xx/5xx
        return [campus.model.Circle.from_resource(item) for item in body["data"]]

    def new(self, *, name: str, tag: str, ...) -> campus.model.Circle:
        return campus.model.Circle.from_resource(self._post_json(
            self.make_path(),
            json=payload(name=name, tag=tag, description=description, parents=parents),
        ))
```

Helpers available on every resource class:

- `_get_json` / `_post_json` / `_put_json` / `_patch_json` /
  `_delete_json` — send one verb, raise the mapped
  [`APIError`][campus_python.errors.APIError] on 4xx/5xx, return the
  parsed body. `None` query/`json` kwargs are omitted from the wire call.
- [`payload(**fields)`][campus_python.interface.payload] — request
  body dropping `None` fields (provided falsy values survive).
- [`updates(**fields)`][campus_python.interface.updates] — same, plus
  the non-empty guard PATCH routes require. **Neither helper can send
  an explicit `null`** — build bodies like `{"submitted_at": null}` by
  hand (see `Submissions.unsubmit`).
- When a method must inspect the raw response first (map 404 →
  `KeyError`, shape a 400 error, observe rate-limit headers), skip the
  helpers and call `self.client.<verb>()` + `raise_for_status()`
  directly — see `vaults.Vault.__getitem__`, `oauth.poll_for_token`,
  `traces.ingest`.

## Request bodies

```python
json=payload(title=title, description=description, questions=questions)
```

- An omitted (`None`) field is left unchanged upstream — the
  convention across Campus write routes.
- Convert only methods where *None means omit*. Deliberate exceptions
  in the codebase: `unsubmit` (explicit null), `timetable.new` (nested
  `metadata`/`data` body), `sessions.new` (`str()` coercion), and
  required-only literals where the helper adds nothing.
- `Clients.update` uses `payload()` **without** `updates()` — the auth
  server accepts its empty PATCHes; don't add guards the server
  doesn't have.

## Paths

- Collections end with a trailing slash (`make_path` default); item
  routes carry one too; dead-end action/sub-resource parts (`submit`,
  `add`, `revoke`, `entries`) do **not** — mirror the upstream Flask
  route rules (`strict_slashes` makes these load-bearing).
- Collection `path` attrs carry no slashes (`path = "circles"`).
- [`join_path(*parts)`][campus_python.interface.join_path] strips
  ends and single-slashes the join; inner slashes survive — by-slug
  tails rely on that. Don't build paths by raw f-string; go through
  `make_path`.
- Nested sub-resources are addressed by `__getitem__` (id) and
  properties (fixed segment): `Circles.Circle.CircleMembers("members", parent=self)`.

## Response envelopes

Envelope keys (`data`, `value`, `timetable`, `entries`, `users`,
`clients`, `connections`, `grant`, `spans`, `key`, `secret`,
`swept_count`, ...) are **upstream-driven and stay inline** at each
method — no hidden unwrap layer. A wrong key is a `KeyError` right in
the method that owns it; the unit tests pin every shape.

## By-slug surfaces

Resources whose records are addressed by a terminal slug path tail
(files, hosted apps) subclass
[`BySlugCollection`][campus_python.api.v1.byslug.BySlugCollection]
instead, parameterized by record type. The raw-tail rule (slugs ride
unquoted — the whole tail after `by-slug/` is the slug) and the
`list`/`get_meta`/`get_content`/`put_by_slug`/`delete_by_slug`
surface are defined once:

```python
class HostedApps(BySlugCollection[campus.model.HostedApp]):
    path = "hostedapps"

    def _from_resource(self, record: dict) -> campus.model.HostedApp:
        return campus.model.HostedApp.from_resource(record)
```

Dict-returning surfaces (`Files(BySlugCollection[dict])`) need no
override at all.

## Testing it

Unit tests drive a Mock client through the shared factories and pin
exact recorded calls:

```python
from tests.support import json_response, make_api

def test_list_unwraps_data_envelope(self):
    api, client = make_api()
    client.get.return_value = json_response({"data": [CIRCLE_RESOURCE]})
    circles = api.circles.list()
    client.get.assert_called_once_with("/api/v1/circles/")
    self.assertEqual(len(circles), 1)
```

`json_response(body, status_code=400)` raises the mapped APIError from
`raise_for_status()` — use it for error-path tests.

## Base-class reference

::: campus_python.interface
    options:
      members:
        - ResourceRoot
        - ResourceCollection
        - Resource
        - join_path
        - payload
        - updates
      filters:
        - "!^__repr__$"
        - "!^__str__$"

::: campus_python.api.v1.byslug
    options:
      members:
        - BySlugCollection
