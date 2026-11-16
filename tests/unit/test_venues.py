"""Unit tests for the venues resource (campus#1099, SDK slice).

Path/method contracts against the mock JSON client: POST create, list
envelope unwrap, per-venue get/update/delete. Item routes carry
trailing slashes upstream, so the collection's default end_slash paths
align with no rstrip. Records deserialize to ``campus.model.Venue``.
"""

import unittest

from campus.model import Venue

from tests.support import make_api


def record(**overrides) -> dict:
    return {
        "id": "uid-venue-abcd1234",
        "metadata": {"name": "B1-01", "capacity": 40},
        "notes": "Projector **broken**.",
        "created_at": "2026-11-16T00:00:00Z",
        "updated_at": None,
        **overrides,
    }


class TestVenuesCreate(unittest.TestCase):
    def setUp(self):
        self.api, self.client = make_api()

    def test_create_posts_body_and_returns_model(self):
        self.client.post.return_value.json.return_value = record()
        venue = self.api.venues.create(
            metadata={"name": "B1-01"}, notes="Projector **broken**."
        )
        self.client.post.assert_called_once_with(
            "/api/v1/venues/",
            json={"metadata": {"name": "B1-01"}, "notes": "Projector **broken**."},
        )
        self.assertIsInstance(venue, Venue)
        self.assertEqual(venue.metadata["name"], "B1-01")

    def test_create_omits_unset_fields(self):
        self.client.post.return_value.json.return_value = record()
        self.api.venues.create()
        self.client.post.assert_called_once_with(
            "/api/v1/venues/", json={}
        )


class TestVenuesList(unittest.TestCase):
    def setUp(self):
        self.api, self.client = make_api()

    def test_list_unwraps_data_envelope(self):
        self.client.get.return_value.json.return_value = {
            "data": [record(), record(id="uid-venue-eeee1111")]
        }
        venues = self.api.venues.list()
        self.client.get.assert_called_once_with("/api/v1/venues/")
        self.assertEqual(len(venues), 2)
        self.assertIsInstance(venues[0], Venue)
        self.assertEqual(venues[1].id, "uid-venue-eeee1111")


class TestVenueItem(unittest.TestCase):
    def setUp(self):
        self.api, self.client = make_api()
        self.venue = self.api.venues["uid-venue-abcd1234"]

    def test_get_item_path_with_trailing_slash(self):
        self.client.get.return_value.json.return_value = record()
        venue = self.venue.get()
        self.client.get.assert_called_once_with(
            "/api/v1/venues/uid-venue-abcd1234/"
        )
        self.assertIsInstance(venue, Venue)
        self.assertEqual(venue.id, "uid-venue-abcd1234")

    def test_update_patches_given_fields_only(self):
        self.client.patch.return_value.json.return_value = record()
        self.venue.update(metadata={"name": "B1-02"})
        self.client.patch.assert_called_once_with(
            "/api/v1/venues/uid-venue-abcd1234/",
            json={"metadata": {"name": "B1-02"}},
        )

    def test_update_clear_notes_sends_null(self):
        """clear_notes is the only way to send notes: null upstream;
        notes=None alone must leave the note unchanged."""
        self.client.patch.return_value.json.return_value = record()
        self.venue.update(notes=None)
        self.client.patch.assert_called_once_with(
            "/api/v1/venues/uid-venue-abcd1234/", json={}
        )
        self.client.patch.reset_mock()
        self.venue.update(clear_notes=True)
        self.client.patch.assert_called_once_with(
            "/api/v1/venues/uid-venue-abcd1234/", json={"notes": None}
        )

    def test_delete(self):
        self.venue.delete()
        self.client.delete.assert_called_once_with(
            "/api/v1/venues/uid-venue-abcd1234/"
        )


if __name__ == "__main__":
    unittest.main()
