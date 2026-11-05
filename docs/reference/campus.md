# Campus facade

`campus_python.Campus` is the unified entry point. It resolves one
[`JsonClient`][campus_python.json_client.interface.JsonClient] per
service from the environment (see
[Getting started › Configuration](../getting-started.md#configuration))
and exposes the four service roots plus the token/session managers.

Modes: `"server"` (default — requires `CLIENT_ID`/`CLIENT_SECRET`)
and `"device"` (public clients, no credentials). Service base URLs
resolve per service via the campus-common registry;
[`audit`][campus_python.Campus.audit] always carries its own client
authenticated with `AUDIT_API_KEY` (the audit service rejects
client-secret Basic auth), and
[`integrations`][campus_python.Campus.integrations] shares the auth
client so it works in device mode too.

::: campus_python.Campus
