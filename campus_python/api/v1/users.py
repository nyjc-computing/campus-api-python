"""campus.python.api.v1.users

Campus API users resource (v1): the inverted membership check.

There is no users resource family in campus.api — this collection only
surfaces the circles-graph query "which roles does this user hold"
(campus#1202), answered through the same shared resolver as the
enforcement gate and the transitive membership probe.
"""

from ...interface import ResourceCollection


class Users(ResourceCollection):
    """Campus API Users resource (membership queries only)."""
    path = "users"

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
