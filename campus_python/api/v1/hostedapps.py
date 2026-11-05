"""campus_python.api.v1.hostedapps

Campus API hosted-apps resource (v1).

HostedApps are single-file HTML apps published to Campus app hosting
(campus-apphost, classroom#81). Bytes are content-addressed server-side
(sha256 bucket keys) — the slug is the app's stable address, so
replacing content under a slug keeps the address while serving the new
version. Records deserialize to ``campus.model.HostedApp``.

Unlike files, hosted-app content defaults to text/html upstream when
no content_type is given.
"""

import campus.model

from .byslug import BySlugCollection


class HostedApps(BySlugCollection[campus.model.HostedApp]):
    """Campus API hosted-apps resource (consumer-facing by-slug surface)."""
    path = "hostedapps"

    def _from_resource(self, record: dict) -> campus.model.HostedApp:
        return campus.model.HostedApp.from_resource(record)
