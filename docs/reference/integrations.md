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
