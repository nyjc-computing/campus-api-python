"""campus.python.integrations.v1

Campus integrations resources (v1).

Two surfaces on the auth service:

- The read-only service catalog (`list()`, GET /integrations/v1/#688,
  #56). Public — everything it returns is already observable by
  starting a connect flow — so it works in both server and device
  modes without extra authorization.
- Integration action proxies (#1221,
  `integrations["google.classroom"].with_user(<user_id>)`): admin-
  authorized verbs campus.auth performs on a TARGET user's stored
  integration credential (e.g. Classroom turnIn backfills). The
  provider's tokens never cross the service boundary — responses
  carry action outcomes only. Requires a caller token holding the
  per-integration management scope (`integrations.<provider>:admin`)
  plus vault access to the integration's label; see
  docs/integration-actions.md on the campus repo.
"""

import campus.model

from ...interface import JsonDict, ResourceRoot, Transport, payload


class IntegrationsRoot(ResourceRoot):
    """Campus integrations registry resource (auth service, v1).

    Usage:
        client.integrations.list()  # -> list[campus.model.Integration]
        client.integrations["google.classroom"].with_user(u).turn_in(...)
    """

    # Trailing slash matches the Flask route (GET /integrations/v1/);
    # make_path() preserves it verbatim.
    url_prefix: str = "/integrations/v1/"

    def list(self) -> "list[campus.model.Integration]":
        """List the first-party integrations Campus offers.

        Returns:
            list[campus.model.Integration]: Registry entries with
            public catalog metadata only (no secrets). If
            enable/disable flags are added server-side later, they
            surface behind this same resource.
        """
        body = self._get_json(self.make_path())
        return [
            campus.model.Integration.from_resource(item)
            for item in body.get("integrations", [])
        ]

    def __getitem__(self, provider: str) -> "IntegrationActions":
        """Action proxies for one integration (campus#1221).

        Args:
            provider: The namespaced integration provider, e.g.
                "google.classroom" (base provider + slug).

        Returns:
            IntegrationActions: call .with_user(<user_id>) to scope
            the actions to a target user.
        """
        return IntegrationActions(provider, client=self.client)


class IntegrationActions(Transport):
    """Action proxies for one integration (#1221).

    Admin-authorized (the caller's token must carry
    `integrations.<provider>:admin` and vault access to the
    integration's label); every verb acts on a target user's stored
    credential and returns action outcomes — never token material.
    """

    def __init__(self, provider: str, *, client) -> None:
        base, _, slug = provider.partition(".")
        if not base or not slug:
            raise ValueError(
                "provider must be namespaced as '<base>.<slug>' "
                f'(e.g. "google.classroom"); got {provider!r}'
            )
        self.provider = provider
        # Shares the auth service's JsonClient (the endpoints live on
        # /auth/v1), so the caller's bearer/basic authorization applies.
        self._client = client
        self._prefix = f"/auth/v1/integrations/{base}/{slug}/users"

    @property
    def client(self):
        """The auth service's JsonClient (overrides Transport's stub)."""
        return self._client

    def with_user(self, user_id: str) -> "IntegrationUserActions":
        """Scope the actions to a target user's stored credential."""
        return IntegrationUserActions(self._prefix, user_id, client=self.client)


class IntegrationUserActions(Transport):
    """Target-user-scoped integration verbs (#1221)."""

    def __init__(self, prefix: str, user_id: str, *, client) -> None:
        self._client = client
        self._path = f"{prefix}/{user_id}"

    @property
    def client(self):
        """The auth service's JsonClient (overrides Transport's stub)."""
        return self._client

    def turn_in(
            self,
            course_id: str,
            coursework_id: str,
            submission_id: "str | None" = None,
    ) -> JsonDict:
        """Turn the user's submission in on a CourseWork.

        No-op success (`already: true`) when already TURNED_IN.
        """
        return self._post_json(
            f"{self._path}/turn-in",
            json=payload(
                course_id=course_id,
                coursework_id=coursework_id,
                submission_id=submission_id,
            ),
        )

    def reclaim(
            self,
            course_id: str,
            coursework_id: str,
            submission_id: "str | None" = None,
    ) -> JsonDict:
        """Reclaim the user's turned-in submission.

        Google's FAILED_PRECONDITION (nothing to reclaim) counts as
        success (`already: true`).
        """
        return self._post_json(
            f"{self._path}/reclaim",
            json=payload(
                course_id=course_id,
                coursework_id=coursework_id,
                submission_id=submission_id,
            ),
        )

    def modify_attachments(
            self,
            course_id: str,
            coursework_id: str,
            submission_id: str,
            attachments: "list[JsonDict]",
    ) -> JsonDict:
        """Add link attachments to the user's submission.

        `attachments` items are Google's addAttachments shape, e.g.
        {"link": {"url": "https://..."}}.
        """
        return self._post_json(
            f"{self._path}/modify-attachments",
            json=payload(
                course_id=course_id,
                coursework_id=coursework_id,
                submission_id=submission_id,
                attachments=attachments,
            ),
        )

    def get_submission(
            self,
            course_id: str,
            coursework_id: str,
            submission_id: "str | None" = None,
    ) -> JsonDict:
        """Read the user's submission (state + attachments metadata)."""
        query = payload(
            course_id=course_id,
            coursework_id=coursework_id,
            submission_id=submission_id,
        )
        return self._get_json(f"{self._path}/submission", query=query or None)
