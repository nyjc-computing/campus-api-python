"""campus.python.api.v1.users

Campus API users resource (v1): the read-only directory facade plus
the inverted membership check.

Two surfaces live under /users:

- the **directory** (#1226): list/search the user base (staff get the
  full list via the staff:viewer baseline; callers without group-read
  are server-side scoped to the members of circles they can read) and
  fetch a single record (every authenticated user sees their own).
  Read-only by construction — identity mutation stays in campus.auth's
  management surface, which the SDK surfaces at auth.users;
- the circles-graph query "which roles does this user hold"
  (campus#1202), answered through the same shared resolver as the
  enforcement gate and the transitive membership probe.
"""

from ...interface import ResourceCollection


class Users(ResourceCollection):
    """Campus API Users resource (directory facade + roles query)."""
    path = "users"

    def list(
            self,
            q: str | None = None,
            limit: int | None = None,
            cursor: str | None = None,
    ) -> dict:
        """Search the user directory (read-only facade, #1226).

        Authorization is server-side: staff (staff:viewer baseline) get
        the full base; other authenticated callers get the members of
        circles they can read, plus their own record. Each directory
        record carries id (the email), name, and activated_at.

        Args:
            q: Case-insensitive substring over name and id.
            limit: Page size (server default 50, capped at 200).
            cursor: The previous page's next_cursor.

        Returns:
            The page:

                {
                    "users": [{id, email, name, activated_at}, ...],
                    "next_cursor": str | None,
                }
        """
        query: dict = {}
        if q:
            query["q"] = q
        if limit is not None:
            query["limit"] = limit
        if cursor is not None:
            query["cursor"] = cursor
        return self._get_json(self.make_path(), query=query or None)

    def get(self, user_id: str) -> dict:
        """Fetch one directory record.

        Every authenticated user may fetch their own record; other
        records need group-read on the users family or membership in
        the caller's circle-visible slice (an invisible record is
        indistinguishable from an absent one: 404 either way).

        Args:
            user_id: The user's ID (their email account).

        Returns:
            The directory record: {id, email, name, activated_at}.
        """
        return self._get_json(self.make_path(user_id))

    def roles(self, user_id: str) -> dict:
        """List the role circles a user holds, resolved transitively.

        The inverted membership check (campus#1202): instead of
        probing "is this user in this circle" one circle at a time,
        this enumerates every role circle (tag "role", e.g. the seeded
        "<resource>.admin" circles) the user is reachable from —
        including through member group circles — sorted by role circle
        name. Reads stay open (authentication required, no role).

        Args:
            user_id: The user's ID (their email account, naming their
                user circle). A user with no resolvable memberships
                yields an empty roles list, not an error.

        Returns:
            The server's roles dict:

                {
                    "user_id": str,
                    "roles": [
                        {
                            "circle_id": str,
                            "name": str,
                            "access_value": int,  # max across paths
                            "direct": bool,
                            "via": list[str],     # containment chain
                        },
                        ...,
                    ],
                }
        """
        # The API route carries no trailing slash; collection item
        # paths default to one, so strip it and append the sub-part.
        return self._get_json(
            f"{self.make_path(user_id, end_slash=False).rstrip('/')}/roles"
        )
