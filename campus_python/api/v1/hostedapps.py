"""campus_python.api.v1.hostedapps

Campus API hosted-apps resource (v1).

HostedApps are single-file HTML apps published to Campus app hosting
(campus-apphost, classroom#81). Bytes are content-addressed server-side
(sha256 bucket keys) — the slug is the app's stable address, so
replacing content under a slug keeps the address while serving the new
version. Records deserialize to ``campus.model.HostedApp``.

By-slug routes are terminal upstream — the whole path tail after
``hostedapps/by-slug/`` is the slug — so slugs are passed as raw path
tails, never quoted or collapsed (#141).
"""

import campus.model
from ...interface import ResourceCollection


class HostedApps(ResourceCollection):
    """Campus API hosted-apps resource (consumer-facing by-slug surface)."""
    path = "hostedapps"

    def list(self, prefix: str | None = None) -> list[campus.model.HostedApp]:
        """List hosted apps, optionally under a slug prefix.

        Args:
            prefix: Only include apps whose slug starts with this
                prefix.

        Returns:
            Hosted app models.
        """
        query = {"prefix": prefix} if prefix else None
        body = self._get_json(self.make_path(), query=query)
        return [
            campus.model.HostedApp.from_resource(record)
            for record in body["data"]
        ]

    def get_meta(self, slug: str) -> campus.model.HostedApp:
        """Get a hosted app's record by slug.

        Args:
            slug: The app's stable slug, e.g. "quest-dom".

        Returns:
            The hosted app model.
        """
        body = self._get_json(self._by_slug_path(slug), query={"meta": "1"})
        return campus.model.HostedApp.from_resource(body)

    def get_content(self, slug: str) -> bytes:
        """Get a hosted app's bytes by slug — the CURRENT version.

        The bytes are served from content-addressed storage and
        verified server-side against the record's content hash.
        Responses carry an ETag and a short max-age cache header;
        raise_for_status() semantics are unchanged.

        Args:
            slug: The app's stable slug.

        Returns:
            The app content, undecoded — apps are HTML documents,
            callers decode.
        """
        resp = self.client.get(self._by_slug_path(slug))
        resp.raise_for_status()
        return resp.content

    def put_by_slug(
            self,
            slug: str,
            data: bytes | str,
            content_type: str | None = None,
            name: str | None = None,
    ) -> campus.model.HostedApp:
        """Create or replace a hosted app by slug (upsert).

        Replacing an app keeps its address while serving the new
        content — consumers referencing the slug (document questions)
        pick up the new version automatically. Attribution
        (uploaded_by_client_id/user_id) is server-side from the
        bearer; user-session calls attribute to the user
        automatically.

        Args:
            slug: The stable slug to create or replace.
            data: The single-file app content (raw request body).
            content_type: MIME type to store and serve back (e.g.
                "text/html"); upstream defaults to text/html for this
                resource and stores application/octet-stream when
                absent.
            name: Optional display name, stored on the record for new
                apps (upstream's PUT ?name= parameter).

        Returns:
            The hosted app model (201 shape on create, 200 shape on
            replace; identical fields).
        """
        query = {"name": name} if name else None
        resp = self.client.put_data(
            self._by_slug_path(slug), data, content_type=content_type,
            query=query,
        )
        resp.raise_for_status()
        return campus.model.HostedApp.from_resource(resp.json())

    def delete_by_slug(self, slug: str) -> None:
        """Delete a hosted app (record and content) by slug.

        Args:
            slug: The slug to delete.
        """
        self._delete_json(self._by_slug_path(slug))
        return None

    def _by_slug_path(self, slug: str) -> str:
        """Path for a by-slug route.

        The slug is a path tail — slashes are part of the slug and
        upstream's ``<path:slug>`` converter expects them literal — so
        it is concatenated unquoted; make_path only trims a
        leading/trailing slash.
        """
        return self.make_path(f"by-slug/{slug}", end_slash=False)
