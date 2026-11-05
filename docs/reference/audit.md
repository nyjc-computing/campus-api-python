# Audit (`campus.audit`)

The `/audit/v1` service: trace ingestion and queries, plus management
of the audit service's own API keys. The audit root authenticates with
an `audit_v1_...` key (`AUDIT_API_KEY`) as its Bearer — client-secret
Basic auth is rejected by the service.

Ingestion feeds the client-side circuit breaker before raising: a 429
trips the bucket (Retry-After honored), 2xx clears expired trips, and
a breaker failure never breaks ingestion. See
[Tracing](../tracing.md) for how spans attribute to journeys.

`campus.model.*` types referenced here are documented in the
[campus repo](https://github.com/nyjc-computing/campus).

## Traces

::: campus_python.audit.v1.traces.Traces

## APIKeys

::: campus_python.audit.v1.apikeys.APIKeys

## AuditRoot

::: campus_python.audit.v1.AuditRoot
