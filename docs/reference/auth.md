# Auth (`campus.auth`)

The `/auth/v1` service: OAuth tokens and device flow, login sessions,
auth sessions, OAuth clients, user/credential management, vaults,
grants, connections, and the token broker. The lanes are described
narratively in [Authentication](../authentication.md).

`campus.model.*` types referenced here are documented in the
[campus repo](https://github.com/nyjc-computing/campus).

## AuthRoot (token facade)

::: campus_python.auth.v1.AuthRoot

## OAuth (device flow, revoke)

::: campus_python.auth.v1.oauth.OAuth

## LoginSessions

::: campus_python.auth.v1.logins.LoginSessions

## CampusSessions

::: campus_python.auth.v1.sessions.CampusSessions

## Clients

::: campus_python.auth.v1.clients.Clients

## Credentials

::: campus_python.auth.v1.credentials.Credentials

## Users

::: campus_python.auth.v1.users.Users

## Vaults

Vault values are addressed mapping-style: `vaults["mylabel"]["key"]`,
`vaults["mylabel"]["key"] = value`, `del vaults["mylabel"]["key"]`;
missing keys raise `KeyError`.

::: campus_python.auth.v1.vaults.Vaults

## Grants

The access-grant store: who can administer which vocabulary, and
vault bitflag access.

::: campus_python.auth.v1.grants.Grants

## Connections

The user-facing view of upstream provider connections (metadata
only — token values are broker-only).

::: campus_python.auth.v1.connections.Connections

## Broker

The sanctioned release path for upstream access tokens
(`token_bridge` clients).

::: campus_python.auth.v1.broker.Broker

## Root

Operator-facing root actions (token/client introspection).

::: campus_python.auth.v1.root.Root

## Session-id seam

The session-id resolver flask_campus installs; ids resolve explicit
argument > provider.

::: campus_python.auth.v1.sessionstore
    options:
      members:
        - set_session_id_provider
