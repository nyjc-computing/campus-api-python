"""campus_python.api.v1.files

Campus API files resource (v1).

Files are binary blobs addressed by a stable slug (consumer-facing,
e.g. ``apps/quest-dom``) or by id (management). This client covers the
consumer-facing surface: listing and the by-slug routes.

Records are validated dicts upstream, not campus.model classes —
list()/get_meta()/put_by_slug() return plain dicts.
"""

from .byslug import BySlugCollection


class Files(BySlugCollection[dict]):
    """Campus API files resource (consumer-facing by-slug surface)."""
    path = "files"
