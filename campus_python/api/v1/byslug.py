"""campus_python.api.v1.byslug

Shared base for by-slug consumer surfaces (files #135, hosted apps #141).

By-slug routes are terminal upstream — the whole path tail after
``<resource>/by-slug/`` is the slug — so slugs ride as raw path tails,
never quoted or collapsed. Surfaces differ only in what their records
deserialize to, which is the `_from_resource` hook.
"""

from typing import Any, Generic, TypeVar

from ...interface import ResourceCollection

R = TypeVar("R")


class BySlugCollection(ResourceCollection, Generic[R]):
    """Collection whose records are addressed by a terminal by-slug tail.

    Subclasses set `path` and, when records deserialize into a
    campus.model class, override `_from_resource` (the default passes
    the raw record dict through). Parameterize the subclass with the
    record type (`BySlugCollection[dict]`, `BySlugCollection[HostedApp]`)
    so the inherited methods return precise types.
    """

    def _from_resource(self, record: dict) -> Any:
        """Map a raw record dict to this surface's record type.

        Default: pass the record through unchanged (dict-returning
        surfaces). Model-backed surfaces override this, e.g. with
        ``campus.model.HostedApp.from_resource``.
        """
        return record

    def list(self, prefix: str | None = None) -> "list[R]":
        """List records, optionally under a slug prefix.

        Args:
            prefix: Only include records whose slug starts with this
                prefix.

        Returns:
            The records under the ``{"data": [...]}`` envelope, each
            mapped through _from_resource.
        """
        query = {"prefix": prefix} if prefix else None
        body = self._get_json(self.make_path(), query=query)
        return [self._from_resource(record) for record in body["data"]]

    def get_meta(self, slug: str) -> R:
        """Get a record's metadata by slug (upstream's ?meta=1 query).

        Args:
            slug: The record's stable slug, e.g. "apps/quest-dom".

        Returns:
            The record mapped through _from_resource.
        """
        body = self._get_json(self._by_slug_path(slug), query={"meta": "1"})
        return self._from_resource(body)

    def get_content(self, slug: str) -> bytes:
        """Get a record's bytes by slug — the CURRENT version.

        Responses carry an ETag and a short max-age cache header.
        Content is returned undecoded — callers decode.

        Args:
            slug: The record's stable slug.

        Returns:
            The content, as stored at serve time.
        """
        # Raw bytes, not JSON: this one keeps the raw response.
        resp = self.client.get(self._by_slug_path(slug))
        resp.raise_for_status()
        return resp.content

    def put_by_slug(
            self,
            slug: str,
            data: bytes | str,
            content_type: str | None = None,
            name: str | None = None,
    ) -> R:
        """Create or replace a record's content by slug (upsert).

        Replacing an existing slug keeps its address stable — consumers
        rely on this for in-place updates. Attribution
        (uploaded_by_client_id/user_id) is server-side from the
        bearer; user-session calls attribute to the user
        automatically.

        Args:
            slug: The stable slug to create or replace.
            data: Raw content (the request body).
            content_type: MIME type to store and serve back (e.g.
                "text/html"); defaults to the transport's choice and
                upstream stores application/octet-stream when absent.
            name: Optional display name, stored on the record for new
                records (upstream's PUT ?name= parameter).

        Returns:
            The record mapped through _from_resource (201 shape on
            create, 200 shape on replace; identical dict fields).
        """
        query = {"name": name} if name else None
        # Raw request body, not JSON: this one keeps the raw call.
        resp = self.client.put_data(
            self._by_slug_path(slug), data, content_type=content_type,
            query=query,
        )
        resp.raise_for_status()
        return self._from_resource(resp.json())

    def delete_by_slug(self, slug: str) -> None:
        """Delete a record (its metadata and content) by slug.

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
