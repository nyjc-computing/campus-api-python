"""campus_python.audit

Client library for the Campus audit service: span ingest, trace and
journey queries, API-key administration, and the named role catalogue.

Consolidated from the flask-campus dist's campus.audit.{client,http,roles}
portions (flask-campus#31): one audit client, shipped with the SDK so
Flask apps (via the campus.flask_campus audit middleware), the suite
services, and non-Flask clients (campus-cli) all share one
implementation.

The audit service authenticates with a dedicated audit API key
(`audit_v1_...`) sent as a Bearer token — not CLIENT_ID/CLIENT_SECRET
(whose basic-auth fallback exists only for test harnesses).

Example:
    from campus_python.audit import AuditClient

    client = AuditClient()
    client.traces.new(span_data)
"""

__all__ = [
    "AuditClient",
    "roles",
]

from . import roles
from .client import AuditClient
