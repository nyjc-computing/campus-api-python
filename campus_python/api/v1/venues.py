"""campus_python.api.v1.venues

Campus API venues resource (v1, campus#1099): bookable campus venues
stored as documents. The venue schema is deliberately fluid upstream —
freeform `metadata` carries the venue's facts (name, capacity,
location, ...) and `notes` carries freeform markdown — so the client
passes both through largely verbatim; stable metadata fields will be
hoisted upstream later.

Records deserialize to ``campus.model.Venue``.
"""

import campus.model

from ...interface import Resource, ResourceCollection


class Venues(ResourceCollection):
    """Campus API venues resource."""

    path = "venues"

    def _from_resource(self, record: dict) -> campus.model.Venue:
        return campus.model.Venue.from_resource(record)

    def __getitem__(self, venue_id: str) -> "Venues.Venue":
        """Address one venue by its ID."""
        return Venues.Venue(venue_id, parent=self)

    def create(
            self,
            metadata: dict | None = None,
            notes: str | None = None,
    ) -> campus.model.Venue:
        """Create a venue; returns the stored venue.

        Args:
            metadata: Freeform venue facts (name, type, capacity, ...).
                Stored verbatim; replaces nothing (venues start empty).
            notes: Freeform markdown notes.
        """
        body: dict = {}
        if metadata is not None:
            body["metadata"] = metadata
        if notes is not None:
            body["notes"] = notes
        return self._from_resource(
            self._post_json(self.make_path(), json=body)
        )

    def list(self) -> "list[campus.model.Venue]":
        """Every venue, unordered.

        Venue counts are small (a campus's rooms and spaces), so there
        is no pagination; callers filter client-side.
        """
        body = self._get_json(self.make_path())
        return [self._from_resource(record) for record in body["data"]]

    class Venue(Resource):
        """One venue."""

        def _from_resource(self, record: dict) -> campus.model.Venue:
            return campus.model.Venue.from_resource(record)

        def get(self) -> campus.model.Venue:
            """The venue (404 upstream when unknown)."""
            return self._from_resource(
                self._get_json(self.make_path())
            )

        def update(
                self,
                metadata: dict | None = None,
                notes: str | None = None,
                *,
                clear_notes: bool = False,
        ) -> campus.model.Venue:
            """Patch the venue; returns the updated venue.

            Args:
                metadata: Replacement metadata dict — upstream replaces
                    the whole dict, so read-modify-write is the
                    caller's job.
                notes: Replacement markdown notes.
                clear_notes: Send ``notes: null`` upstream, clearing
                    the note (``notes=None`` alone leaves it
                    unchanged).
            """
            body: dict = {}
            if metadata is not None:
                body["metadata"] = metadata
            if notes is not None:
                body["notes"] = notes
            if clear_notes:
                body["notes"] = None
            return self._from_resource(
                self._patch_json(self.make_path(), json=body)
            )

        def delete(self) -> None:
            """Delete the venue (404 upstream when unknown)."""
            self._delete_json(self.make_path())
