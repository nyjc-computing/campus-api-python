"""campus_python.api.v1.files

Campus API files resource (v1).

Files are binary blobs addressed by a stable slug (consumer-facing,
e.g. ``apps/quest-dom``) or by id (management). This client covers the
consumer-facing surface: listing and the by-slug routes. By-slug
routes are terminal upstream — the whole path tail after
``files/by-slug/`` is the slug — so slugs are passed as raw path
tails, never quoted or collapsed (#135).
"""

from ...interface import ResourceCollection


class Files(ResourceCollection):
    """Campus API files resource (consumer-facing by-slug surface)."""
    path = "files"

    def list(self, prefix: str | None = None) -> list[dict]:
        """List file records, optionally under a slug prefix.

        Args:
            prefix: Only include files whose slug starts with this
                prefix (e.g. "apps/").

        Returns:
            File metadata records as plain dicts — records are
            validated dicts upstream, not campus.model classes.
        """
        query = {"prefix": prefix} if prefix else None
        resp = self.client.get(self.make_path(), query=query)
        resp.raise_for_status()
        # GET /files/ wraps the records in a {"data": [...]} envelope.
        return resp.json()["data"]

    def get_meta(self, slug: str) -> dict:
        """Get a file's metadata record by slug.

        Args:
            slug: The file's stable slug, e.g. "apps/quest-dom".

        Returns:
            The file metadata resource (id, slug, content_type, size,
            timestamps, attribution).
        """
        resp = self.client.get(self._by_slug_path(slug), query={"meta": "1"})
        resp.raise_for_status()
        return resp.json()

    def get_content(self, slug: str) -> bytes:
        """Get a file's bytes by slug.

        Responses carry an ETag and a short max-age cache header;
        raise_for_status() semantics are unchanged. Content is
        returned undecoded — files are binary blobs, HTML callers
        decode.

        Args:
            slug: The file's stable slug.

        Returns:
            The file content, as stored at serve time. Replacing a
            slug's content in place keeps the slug's URL stable, so
            the bytes returned are always the current version.
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
    ) -> dict:
        """Create or replace a file's content by slug (upsert).

        Replacing an existing slug keeps its URL stable — consumers
        rely on this for in-place app updates. Attribution
        (uploaded_by_client_id/user_id) is server-side from the
        bearer; user-session calls attribute to the user
        automatically.

        Args:
            slug: The stable slug to create or replace.
            data: Raw file content (the request body).
            content_type: MIME type to store and serve back (e.g.
                "text/html"); defaults to the transport's choice and
                upstream stores application/octet-stream when absent.
            name: Optional display name, stored on the record for new
                files (upstream's PUT ?name= parameter).

        Returns:
            The file metadata resource (201 shape on create, 200
            shape on replace; identical dict fields).
        """
        resp = self.client.put_data(
            self._by_slug_path(slug), data, content_type=content_type,
            query={"name": name} if name else None,
        )
        resp.raise_for_status()
        return resp.json()

    def delete_by_slug(self, slug: str) -> None:
        """Delete a file (record and content) by slug.

        Args:
            slug: The slug to delete.
        """
        resp = self.client.delete(self._by_slug_path(slug))
        resp.raise_for_status()
        return None

    def _by_slug_path(self, slug: str) -> str:
        """Path for a by-slug route.

        The slug is a path tail — slashes are part of the slug and
        upstream's ``<path:slug>`` converter expects them literal — so
        it is concatenated unquoted; make_path only trims a
        leading/trailing slash.
        """
        return self.make_path(f"by-slug/{slug}", end_slash=False)
