# Integrations registry (`campus.integrations`)

Read-only catalog of the first-party integrations Campus offers,
served by the auth service at `/integrations/v1`. The endpoint is
public — everything it returns is already observable by starting a
connect flow — so it works in both server and device modes without
extra authorization.

Records are `campus.model.Integration` instances (provider, slug,
title, description, scopes, `connectable`, authorize path). If
enable/disable flags are added server-side later, they surface behind
this same resource.

```python
for integration in campus.integrations.list():
    print(integration.provider, integration.connectable)
```

::: campus_python.integrations.v1.IntegrationsRoot

## Integration action proxies (#1221)

Admin-authorized verbs campus.auth performs on a **target user's**
stored integration credential — the backfill path for user-bound
upstream actions (e.g. Classroom `turnIn`) that can only run on the
owning student's OAuth token. The provider's tokens never cross the
service boundary: responses carry action outcomes only.

Requires a caller token holding the per-integration management scope
(`integrations.<provider>:admin`) plus vault access to the
integration's label; see the campus repo's
`docs/integration-actions.md` for the full gate and the operator
bootstrap.

```python
actions = campus.integrations["google.classroom"].with_user(
    "student@nyjc.edu.sg"
)
actions.turn_in(course_id="828477607889", coursework_id="891474284211")
actions.reclaim(course_id="...", coursework_id="...")
actions.modify_attachments(
    course_id="...", coursework_id="...", submission_id="...",
    attachments=[{"link": {"url": "https://..."}}],
)
actions.get_submission(course_id="...", coursework_id="...")
```

::: campus_python.integrations.v1.IntegrationActions
::: campus_python.integrations.v1.IntegrationUserActions
