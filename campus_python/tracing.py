"""campus_python.tracing

Trace-context propagation for SDK HTTP calls (campus-api-python#92,
parent campus#816 item 1).

When the host application is itself traced — its Flask app wired with
campus.audit.middleware.init_app — every request it handles becomes an
audit span. SDK calls made while handling that request should land as
child spans of it, so the audit waterfall shows which host route fired
each campus call.

This module mirrors the propagation half of
campus.audit.middleware.tracing (campus service repo): same header
names, same flask.g contract (trace_id / span_id stashed by the
middleware's before_request hook, and the same _campus_trace_instrumented
idempotency marker). It is deliberately self-contained so the SDK does
not import the server-side audit client stack just to emit two headers —
keep the two in lockstep; W3C traceparent interop would extend both.
"""

import typing

import requests

# Same headers as campus.audit.middleware.tracing (#794): X-Request-ID
# carries the host request's trace id; X-Parent-Span-ID carries its span
# id so the receiving campus service records the call as a child span.
TRACE_ID_HEADER = "X-Request-ID"
PARENT_SPAN_ID_HEADER = "X-Parent-Span-ID"

# Same marker attribute as campus.audit.middleware.tracing so a session
# instrumented by either implementation is left alone by the other.
_INSTRUMENTED_ATTR = "_campus_trace_instrumented"


def current_context() -> tuple[str, str] | None:
    """Return the (trace_id, span_id) of the host's active traced request.

    Reads the flask.g values stashed by campus.audit.middleware's
    before_request hook. Returns None when flask is unavailable, outside
    a request context, or when the request carries no active span
    (tracing disabled or middleware not installed) — such calls stay
    unparented.
    """
    try:
        import flask
    except ImportError:  # pragma: no cover - host without flask
        return None
    if not flask.has_request_context():
        return None
    trace_id = getattr(flask.g, "trace_id", None)
    span_id = getattr(flask.g, "span_id", None)
    if trace_id and span_id:
        return trace_id, span_id
    return None


def propagation_headers() -> dict[str, str]:
    """Headers to attach to an outbound SDK call from the active request.

    Empty outside a traced host request. The receiving campus service's
    tracing middleware turns these into a child span of the caller's
    span (#794, campus#816).
    """
    context = current_context()
    if context is None:
        return {}
    return {
        TRACE_ID_HEADER: context[0],
        PARENT_SPAN_ID_HEADER: context[1],
    }


def instrument_requests_session(session: requests.Session) -> bool:
    """Wrap a requests.Session so its calls carry campus trace context.

    Headers are computed at call time from the host's active request
    context, so a shared session stays correct under concurrent requests,
    and calls made outside a traced request (startup, background threads)
    are left untouched.

    Idempotent: re-instrumenting a session is a no-op.

    Args:
        session: The requests.Session to instrument.

    Returns:
        True if the session was instrumented now, False if already done.
    """
    if getattr(session, _INSTRUMENTED_ATTR, False):
        return False

    original_request = session.request

    def request(method, url, **kwargs):
        extra = propagation_headers()
        if extra:
            headers = dict(kwargs.get("headers") or {})
            for name, value in extra.items():
                headers.setdefault(name, value)
            kwargs["headers"] = headers
        return original_request(method, url, **kwargs)

    # Instance-level override of the bound method: every requests verb
    # funnels through Session.request, so one wrap covers all calls.
    typing.cast(typing.Any, session).request = request
    setattr(session, _INSTRUMENTED_ATTR, True)
    return True
