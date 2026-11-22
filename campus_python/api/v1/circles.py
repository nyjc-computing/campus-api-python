"""campus.python.api.v1.circles

Campus API circles resource (v1).
"""

from typing import Any

import campus.model

from ...interface import Resource, ResourceCollection, payload


class Circles(ResourceCollection):
    """Campus API Circles resource."""
    path = "circles"

    def __getitem__(self, circle_id: str) -> "Circles.Circle":
        """Get a specific circle resource by ID."""
        return Circles.Circle(circle_id, parent=self)

    def list(self) -> "list[campus.model.Circle]":
        """List all circles.

        Returns:
            List of Circle objects.
        """
        body = self._get_json(self.make_path())
        return [
            campus.model.Circle.from_resource(item)
            for item in body["data"]
        ]

    def new(
            self,
            *,
            name: str,
            tag: str,
            description: str = "",
            parents: dict[str, int] | None = None,
    ) -> campus.model.Circle:
        """Create a new circle.

        The server rejects a name that collides with an existing
        circle (409).

        Args:
            name: Circle name (unique across Campus).
            tag: Circle tag (e.g. "project").
            description: Circle description.
            parents: Parent circle ids mapped to access values.

        Returns:
            The created Circle.
        """
        return campus.model.Circle.from_resource(self._post_json(
            self.make_path(),
            json=payload(name=name, tag=tag, description=description, parents=parents)
        ))

    class Circle(Resource):
        """Single campus API circle resource."""

        @property
        def members(self) -> "Circles.Circle.CircleMembers":
            """Get the members resource for this circle."""
            return Circles.Circle.CircleMembers("members", parent=self)

        def delete(self) -> None:
            """Delete this circle."""
            self._delete_json(self.make_path(end_slash=True))

        def get(self) -> campus.model.Circle:
            """Get this circle.

            Returns:
                The Circle.
            """
            body = self._get_json(self.make_path(end_slash=True))
            return campus.model.Circle.from_resource(body)

        def update(
                self,
                *,
                name: str,
                description: "str | None" = None,
        ) -> None:
            """Update this circle.

            The server requires name on every circle PATCH and returns
            422 without it, so it is a required parameter here.
            Description is unchanged when omitted.

            Args:
                name: New circle name (must not collide with an
                    existing circle's name)
                description: New description; omitted leaves it unchanged
            """
            payload: dict[str, Any] = {"name": name}
            if description is not None:
                payload["description"] = description
            self._patch_json(self.make_path(end_slash=True), json=payload)
            return None

        class CircleMembers(Resource):
            """Campus API Circle Members resource."""

            def list(self) -> dict[str, int]:
                """Return the circle's {member_id: access_value} mapping."""
                return self._get_json(self.make_path(end_slash=True))

            def get(self, member_id: str) -> int | None:
                """Probe one direct membership; None when absent.

                The direct-only membership probe: 404 is the expected
                negative answer (absent member), not an error. A
                missing circle still raises (409 ConflictError, per
                the circles family contract); any other non-2XX
                raises as usual.

                This answers the direct members dict only — it can
                disagree with campus.api's enforcement gate for a
                member reachable only through group circles. Use
                resolve() to ask the gate's question (campus#1202).

                Returns:
                    The member's direct access value in the circle, or
                    None if the circle has no such member.
                """
                resp = self.client.get(self.make_path(member_id, end_slash=True))
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()["access_value"]

            def resolve(
                    self,
                    member_id: str,
                    *,
                    transitive: bool = True,
            ) -> "dict | None":
                """Resolve one membership through the server's shared
                resolver; None when unreachable.

                The gate-parity membership check (campus#1202): the
                same question campus.api's enforcement gate answers,
                through the same server implementation — the resolver
                walk is cycle-safe and stale keys fail closed per key.
                404 (unreachable under the requested mode) is the
                expected negative answer, not an error; a missing
                circle still raises (409 ConflictError).

                Args:
                    member_id: The member identifier as stored (a
                        circle UID or the email name of a user circle).
                    transitive: Follow member group circles beyond the
                        direct members dict (the default — the gate's
                        semantics). False answers the direct-only
                        question.

                Returns:
                    None if the member is not reachable, otherwise the
                    server's resolution dict:

                        {
                            "member_id": str,
                            "access_value": int,  # max across paths
                            "direct": bool,
                            "via": list[str],     # containment chain
                        }
                """
                query = {"resolve": "transitive"} if transitive else None
                resp = self.client.get(
                    self.make_path(member_id, end_slash=True), query=query
                )
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()

            def add(self, member_id: str, access_value: int) -> None:
                """Add a member with an access value.

                Targets the /members/add action route; adding an
                existing member re-errors server-side. Use set() for
                upsert semantics.
                """
                self._post_json(
                    self.make_path("add"),
                    json={"member_id": member_id, "access_value": access_value}
                )

            def remove(self, member_id: str) -> None:
                """Remove a member.

                Targets the /members/remove action route.
                """
                self._delete_json(
                    self.make_path("remove"),
                    json={"member_id": member_id}
                )

            def set(self, member_id: str, access_value: int) -> None:
                """Create or update a member's access value (upsert).

                Unlike add()/remove(), which target the /members/add and
                /members/remove action routes, this PATCHes the members
                collection directly — the server's set semantics apply
                (no error when the access value is unchanged).
                """
                self._patch_json(
                    self.make_path(end_slash=True),
                    json={"member_id": member_id, "access_value": access_value}
                )
                return None
