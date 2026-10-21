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
not import the server-side audit client stack just to emit headers —
keep the two in lockstep; W3C traceparent interop would extend both.

Boot journeys (#114): every SDK call is a user request, whether that
user is human or agent — so calls made outside any request context
(startup, background threads) carry a process journey, one
uid-journey-… per process boot, plus a process device tag (default:
RAILWAY_DEPLOYMENT_ID) so boot spans attribute to the deploy that
produced them. Inside a request the caller's own journey always wins;
strict fallback only fills the out-of-request gap (campus-api-python#114
ruling, 2026-10-21). Set CAMPUS_PROCESS_JOURNEY=off to suppress (tests,
operators); set_process_journey()/set_process_device() override in code.
"""

import os
import threading
import typing
import uuid

import requests

# Same headers as campus.audit.middleware.tracing (#794): X-Request-ID
# carries the host request's trace id; X-Parent-Span-ID carries its span
# id so the receiving campus service records the call as a child span.
TRACE_ID_HEADER = "X-Request-ID"
PARENT_SPAN_ID_HEADER = "X-Parent-Span-ID"

# Mirror of campus.audit.middleware.journeys.ACTION_JOURNEY_HEADER
# (campus#828): forwarded so a child service's span joins the caller's
# action journey. Keep the two in lockstep.
JOURNEY_ID_HEADER = "X-Journey-ID"

# Mirror of campus.audit.middleware.journeys.ACTION_JOURNEY_NAME_HEADER
# (campus#952): forwarded with the id so a child service's spans tag
# the same human label (tags.journey_name) and journey cards show it
# end to end. Keep the two in lockstep.
JOURNEY_NAME_HEADER = "X-Journey-Name"

# Environment for the boot journey (#114): off/false/0/no disables it
# (tests, operators), any other non-empty value pins an explicit
# uid-journey-… id. Unset: auto-mint one per process boot.
PROCESS_JOURNEY_ENV = "CAMPUS_PROCESS_JOURNEY"
_PROCESS_JOURNEY_OFF = frozenset({"off", "false", "0", "no"})

# Railway injects the deployment id into every container: the default
# process device tag (#114), so boot spans attribute to the deploy that
# produced them (receiver-side preference is unchanged, campus#837).
PROCESS_DEVICE_ENV = "RAILWAY_DEPLOYMENT_ID"

# Boot-journey state (#114): None until first consultation, then fixed
# for the process's lifetime. A lock guards init/mint; reads take the
# fast path (initialized flag) lock-free.
_process_lock = threading.Lock()
_process_state: dict = {
    "initialized": False,
    "disabled": False,
    "journey_id": None,
    "journey_name": None,
    "device_id": None,
}


def _mint_journey_id() -> str:
    """uid-journey-… matching campus.common.utils.uid.generate_category_uid
    (first 16 chars of the hyphenated uuid4 string) — replicated rather
    than imported so the SDK stays decoupled from the server package."""
    return f"uid-journey-{str(uuid.uuid4())[:16]}"


def _init_process_state() -> None:
    """Initialize from the environment once (caller holds the lock)."""
    raw = (os.environ.get(PROCESS_JOURNEY_ENV) or "").strip()
    if raw.lower() in _PROCESS_JOURNEY_OFF:
        _process_state["disabled"] = True
    elif raw:
        _process_state["journey_id"] = raw
    _process_state["device_id"] = os.environ.get(PROCESS_DEVICE_ENV) or None
    _process_state["initialized"] = True


def _process_device() -> str | None:
    """The process device tag after lazy env init (no journey minting)."""
    if not _process_state["initialized"]:
        with _process_lock:
            if not _process_state["initialized"]:
                _init_process_state()
    return _process_state["device_id"]


def _process_snapshot() -> tuple[str | None, str | None, str | None]:
    """(journey_id, journey_name, device_id) after lazy init and mint.

    The boot journey mints on first use and stays fixed for the
    process's lifetime (one journey per boot, #114). Hosts that only
    read the device (in-request gap-fill) never mint via
    _process_device().
    """
    if not _process_state["initialized"]:
        with _process_lock:
            if not _process_state["initialized"]:
                _init_process_state()
    if _process_state["journey_id"] is None and not _process_state["disabled"]:
        with _process_lock:
            if _process_state["journey_id"] is None:
                _process_state["journey_id"] = _mint_journey_id()
    return (
        _process_state["journey_id"],
        _process_state["journey_name"],
        _process_state["device_id"],
    )


def set_process_journey(
        journey_id: str | None = None,
        *,
        name: str | None = None,
) -> str:
    """Set this process's boot journey explicitly (#114).

    Overrides CAMPUS_PROCESS_JOURNEY and re-enables journeys after
    disable_process_journey(). Mints a uid-journey-… when journey_id is
    omitted (keeping any previously minted/explicit id on later calls);
    a name labels the journey's cards (forwarded as X-Journey-Name,
    campus#952).

    Returns:
        The process journey id now in effect.
    """
    with _process_lock:
        if not _process_state["initialized"]:
            _init_process_state()
        _process_state["disabled"] = False
        if _process_state["journey_id"] is None:
            _process_state["journey_id"] = journey_id or _mint_journey_id()
        elif journey_id is not None:
            _process_state["journey_id"] = journey_id
        if name is not None:
            _process_state["journey_name"] = name
        return _process_state["journey_id"]


def disable_process_journey() -> None:
    """Suppress the boot journey on out-of-request calls (#114).

    For tests and operators who don't want the correlation; the process
    device tag is unaffected. set_process_journey() re-enables.
    """
    with _process_lock:
        if not _process_state["initialized"]:
            _init_process_state()
        _process_state["disabled"] = True


def set_process_device(device_id: str) -> None:
    """Override this process's device tag (default: RAILWAY_DEPLOYMENT_ID).

    Used as a fallback only — a request context with its own stashed
    device keeps it (campus#825/#837 semantics are unchanged).
    """
    with _process_lock:
        if not _process_state["initialized"]:
            _init_process_state()
        _process_state["device_id"] = device_id


def _reset_process_journey() -> None:
    """Reset all boot-journey state (test hook; also re-reads env)."""
    with _process_lock:
        _process_state.update(
            initialized=False,
            disabled=False,
            journey_id=None,
            journey_name=None,
            device_id=None,
        )

# Mirror of campus.config.DEVICE_ID_HEADER (campus#837): forwarded so a
# child service's span carries the caller's device identity when the
# host stashed one (flask_campus's push_context sets g.device from the
# login session). The receiving middleware reads it only when it knows
# nothing better (g.device absent, no campus_device cookie). Keep the
# two in lockstep.
DEVICE_ID_HEADER = "X-Campus-Device"

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
    """Headers to attach to an outbound SDK call from the active context.

    Empty outside a request context until #114 — now: out-of-request
    calls carry the process boot journey (X-Journey-ID/X-Journey-Name)
    and the process device (X-Campus-Device, default RAILWAY_DEPLOYMENT_ID),
    so startup and background calls correlate under one journey per boot.
    Inside a request, the caller's own journey always wins — a journey-less
    request stays unjourneyed (strict MVP: the trace waterfall already
    correlates the chain) — and the process device only fills the gap
    when the request stashed none. The receiving campus service's
    tracing middleware turns the trace headers into a child span of the
    caller's span (#794, campus#816); the journeys middleware adopts
    X-Journey-ID so the child span joins the caller's action journey
    (campus#828), with X-Journey-Name carrying its human label
    (campus#952); the tracing middleware adopts X-Campus-Device for the
    child span's device tag when it knows nothing better (campus#837).
    """
    headers: dict[str, str] = {}
    try:
        import flask
    except ImportError:  # pragma: no cover - host without flask
        flask = None
    in_request = flask is not None and flask.has_request_context()

    if in_request:
        trace_id = getattr(flask.g, "trace_id", None)
        span_id = getattr(flask.g, "span_id", None)
        if trace_id and span_id:
            headers[TRACE_ID_HEADER] = trace_id
            headers[PARENT_SPAN_ID_HEADER] = span_id
        journey_id = getattr(flask.g, "journey_id", None)
        if journey_id:
            headers[JOURNEY_ID_HEADER] = journey_id
        journey_name = getattr(flask.g, "journey_name", None)
        if journey_name:
            headers[JOURNEY_NAME_HEADER] = journey_name
        device_id = getattr(flask.g, "device", None)
        if not device_id:
            # Gap-fill only: a request with its own device keeps it.
            device_id = _process_device()
        if device_id:
            headers[DEVICE_ID_HEADER] = str(device_id)
        return headers

    # Out of any request context (startup, background threads): the
    # boot journey and process device are the only correlation there is.
    journey_id, journey_name, device_id = _process_snapshot()
    if journey_id:
        headers[JOURNEY_ID_HEADER] = journey_id
    if journey_name:
        headers[JOURNEY_NAME_HEADER] = journey_name
    if device_id:
        headers[DEVICE_ID_HEADER] = device_id
    return headers


def instrument_requests_session(session: requests.Session) -> bool:
    """Wrap a requests.Session so its calls carry campus trace context.

    Headers are computed at call time from the host's active request
    context, so a shared session stays correct under concurrent requests.
    Calls outside a request context (startup, background threads) carry
    the process boot journey and device (#114); calls inside a request
    never inherit it (the caller's journey, or none, wins).

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
