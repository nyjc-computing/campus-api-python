"""campus_python.api.v1.files

Campus API files resource (v1).

Files are binary blobs addressed by a stable slug (consumer-facing,
e.g. ``apps/quest-dom``) or by id (management). This client covers
both surfaces: listing and the by-slug routes, plus the id-based
management routes (``files[id]`` — metadata, content replace, delete;
these never create).

Records are validated dicts upstream, not campus.model classes —
list()/get_meta()/put_by_slug()/file.get() return plain dicts.
"""

from ...interface import Resource
from .byslug import BySlugCollection


class Files(BySlugCollection[dict]):
    """Campus API files resource (by-slug + id-based management)."""
    path = "files"

    def __getitem__(self, file_id: str) -> "Files.File":
        """Get a file record's management surface by id."""
        return Files.File(file_id, parent=self)

    class File(Resource):
        """A single file record addressed by id (management surface).

        Unlike the by-slug upsert, these routes never create —
        replacing or reading content targets an existing record only
        (404 for an unknown id).
        """

        def get(self) -> dict:
            """Get this file's metadata record."""
            return self._get_json(self.make_path(end_slash=True))

        def get_content(self) -> bytes:
            """Get this file's bytes — the CURRENT version.

            Responses carry an ETag and a short max-age cache header.
            Content is returned undecoded — callers decode.
            """
            resp = self.client.get(self.make_path("content", end_slash=True))
            resp.raise_for_status()
            return resp.content

        def put_content(
                self,
                data: bytes | str,
                content_type: str | None = None,
                name: str | None = None,
        ) -> dict:
            """Replace this file's content (never creates).

            Args:
                data: Raw content (the request body).
                content_type: MIME type to store and serve back (e.g.
                    "text/html"); defaults to the transport's choice and
                    upstream stores application/octet-stream when absent.
                name: Optional new display name (upstream's PUT ?name=
                    parameter).

            Returns:
                The updated metadata record.
            """
            query = {"name": name} if name else None
            resp = self.client.put_data(
                self.make_path("content", end_slash=True),
                data,
                content_type=content_type,
                query=query,
            )
            resp.raise_for_status()
            return resp.json()

        def delete(self) -> None:
            """Delete this file (its metadata and content)."""
            self._delete_json(self.make_path(end_slash=True))
            return None
