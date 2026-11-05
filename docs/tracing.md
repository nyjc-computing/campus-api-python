# Tracing

Every SDK call propagates audit trace context — trace, journey, and
device headers — so the Campus Audit waterfall shows which host route
(or which process boot) fired each campus call. The machinery lives in
[`campus_python.tracing`](#reference) and is on by default; hosts only
touch it to install providers or override journey attribution.

## In-request calls

When the host application is itself traced — its Flask app wired with
`campus.audit.middleware.init_app` — every request it handles becomes
an audit span. SDK calls made while handling that request land as
child spans of it: the middleware's propagation module installs a
request-context provider via
[`set_request_context_provider()`][campus_python.tracing.set_request_context_provider],
and its output (span/journey/device headers) is attached verbatim to
outbound SDK calls.

The SDK itself is framework-free: with **no provider installed**, calls
are treated as out-of-request and carry only the boot journey below.

## Boot journeys

Every SDK call is a user request, whether that user is human or agent.
Calls made outside any request context — startup, background threads —
carry a **process journey** (one `uid-journey-...` per process boot)
plus a process device tag so boot spans attribute to the deploy that
produced them:

- Device id defaults to `RAILWAY_DEPLOYMENT_ID` when present.
- Inside a request, the caller's own journey always wins; the strict
  fallback only fills the out-of-request gap.

Overrides:

```python
import campus_python.tracing as tracing

tracing.set_process_journey("uid-journey-migration-run")   # attribute to a named journey
tracing.set_process_device("worker-3")                     # override the device tag
tracing.disable_process_journey()                          # or suppress entirely
```

`CAMPUS_PROCESS_JOURNEY=off` (also `false`/`0`/`no`) suppresses the
boot journey via the environment — useful for tests and operators.
[`propagation_headers()`][campus_python.tracing.propagation_headers]
returns what the next SDK call would send, which is handy for
assertions in tests.

## Instrumenting a custom transport

The propagation headers are attached by the default
[`CampusRequest`][campus_python.json_client.CampusRequest] transport.
If you bring your own [`JsonClient`][campus_python.json_client.interface.JsonClient]
(see [Custom clients](custom-clients.md)), call
[`instrument_requests_session(session)`][campus_python.tracing.instrument_requests_session]
on the underlying `requests.Session` to get the same header
propagation, or attach [`propagation_headers()`][campus_python.tracing.propagation_headers]
to each request yourself.

## Related seam: session ids

Session-id resolution (login/auth-session lanes) is a separate
injectable provider — see
[Authentication › User sessions](authentication.md#user-sessions) and
[`set_session_id_provider()`][campus_python.auth.v1.sessionstore.set_session_id_provider].

## Reference

::: campus_python.tracing
    options:
      members:
        - set_request_context_provider
        - set_process_journey
        - disable_process_journey
        - set_process_device
        - process_device
        - propagation_headers
        - instrument_requests_session
        - PROCESS_JOURNEY_ENV
        - PROCESS_DEVICE_ENV
