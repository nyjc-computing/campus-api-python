import unittest
from unittest.mock import Mock

from campus_python.interface import (
    Resource,
    ResourceCollection,
    ResourceRoot,
    payload,
    updates,
)


class TestResourceRootMakePath(unittest.TestCase):
    """Test ResourceRoot.make_path() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.mock_client.base_url = "https://api.example.com"

    def test_make_path_without_part(self):
        """Test make_path() returns correct path without part.

        Resource roots don't need trailing slashes in url_prefix, but the
        implementation should handle them correctly.
        """
        root = ResourceRoot(self.mock_client)
        root.url_prefix = "api/v1"
        self.assertEqual(root.make_path(), "/api/v1")

    def test_make_path_with_part(self):
        """Test make_path() returns correct path with part."""
        root = ResourceRoot(self.mock_client)
        root.url_prefix = "api/v1"
        self.assertEqual(root.make_path("users"), "/api/v1/users")

    def test_make_path_strips_leading_slash_from_prefix(self):
        """Test make_path() strips leading slash from url_prefix."""
        root = ResourceRoot(self.mock_client)
        root.url_prefix = "/api/v1"
        self.assertEqual(root.make_path(), "/api/v1")

    def test_make_path_strips_leading_slash_from_part(self):
        """Test make_path() strips leading slash from part."""
        root = ResourceRoot(self.mock_client)
        root.url_prefix = "api/v1"
        self.assertEqual(root.make_path("/users"), "/api/v1/users")

    def test_make_path_strips_both_leading_slashes(self):
        """Test make_path() strips leading slashes from both prefix and part."""
        root = ResourceRoot(self.mock_client)
        root.url_prefix = "/api/v1"
        self.assertEqual(root.make_path("/users"), "/api/v1/users")

    def test_make_path_with_trailing_slash_in_prefix(self):
        """Test make_path() with trailing slash in url_prefix.

        Resource roots can have trailing slashes which are preserved.
        """
        root = ResourceRoot(self.mock_client)
        root.url_prefix = "api/v1/"
        # Trailing slash in prefix is preserved
        self.assertEqual(root.make_path(), "/api/v1/")

    def test_make_path_with_trailing_slash_in_part(self):
        """Test make_path() with trailing slash in part.

        This tests adding a collection path which should have trailing slash
        according to API schema.
        """
        root = ResourceRoot(self.mock_client)
        root.url_prefix = "api/v1"
        # Trailing slash in part is preserved (collection path)
        self.assertEqual(root.make_path("users/"), "/api/v1/users/")


class TestResourceRootMakeUrl(unittest.TestCase):
    """Test ResourceRoot.make_url() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.mock_client.base_url = "https://api.example.com"

    def test_make_url_basic(self):
        """Test make_url() returns correct URL."""
        root = ResourceRoot(self.mock_client)
        root.url_prefix = "api/v1"
        self.assertEqual(root.make_url(), "https://api.example.com/api/v1")

    def test_make_url_strips_leading_slash_from_prefix(self):
        """Test make_url() strips leading slash from url_prefix."""
        root = ResourceRoot(self.mock_client)
        root.url_prefix = "/api/v1"
        self.assertEqual(root.make_url(), "https://api.example.com/api/v1")

    def test_make_url_with_trailing_slash_in_base_url(self):
        """Test make_url() with trailing slash in base_url."""
        self.mock_client.base_url = "https://api.example.com/"
        root = ResourceRoot(self.mock_client)
        root.url_prefix = "api/v1"
        # Results in double slash, which is expected behavior
        self.assertEqual(root.make_url(), "https://api.example.com//api/v1")

    def test_make_url_with_trailing_slash_in_prefix(self):
        """Test make_url() with trailing slash in url_prefix."""
        root = ResourceRoot(self.mock_client)
        root.url_prefix = "api/v1/"
        self.assertEqual(root.make_url(), "https://api.example.com/api/v1/")


class TestResourceCollectionMakePath(unittest.TestCase):
    """Test ResourceCollection.make_path() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.mock_client.base_url = "https://api.example.com"
        self.root = ResourceRoot(self.mock_client)
        self.root.url_prefix = "api/v1"

    def test_make_path_without_part(self):
        """Test make_path() returns correct path without part.

        According to API schema, collections always have trailing slashes.
        """
        collection = ResourceCollection(self.mock_client, root=self.root)
        collection.path = "users"
        self.assertEqual(collection.make_path(), "/api/v1/users/")

    def test_make_path_with_part(self):
        """Test make_path() returns correct path with part.

        According to API schema, single resources in collections have trailing slashes.
        """
        collection = ResourceCollection(self.mock_client, root=self.root)
        collection.path = "users"
        self.assertEqual(collection.make_path("123"), "/api/v1/users/123/")

    def test_make_path_strips_leading_slash_from_path(self):
        """Test make_path() strips leading slash from collection path.

        According to API schema, collections always have trailing slashes.
        """
        collection = ResourceCollection(self.mock_client, root=self.root)
        collection.path = "/users"
        self.assertEqual(collection.make_path(), "/api/v1/users/")

    def test_make_path_strips_leading_slash_from_part(self):
        """Test make_path() strips leading slash from part.

        According to API schema, single resources in collections have trailing slashes.
        """
        collection = ResourceCollection(self.mock_client, root=self.root)
        collection.path = "users"
        self.assertEqual(collection.make_path("/123"), "/api/v1/users/123/")

    def test_make_path_strips_trailing_slash_from_root_path(self):
        """Test make_path() preserves trailing slash from collection path.

        According to API schema, collection paths should have trailing slashes.
        """
        collection = ResourceCollection(self.mock_client, root=self.root)
        collection.path = "users/"
        # Collection paths with trailing slashes are preserved and normalized
        self.assertEqual(collection.make_path("123"), "/api/v1/users/123/")

    def test_make_path_with_nested_path(self):
        """Test make_path() with nested collection path.

        According to API schema, all collection paths have trailing slashes.
        """
        collection = ResourceCollection(self.mock_client, root=self.root)
        collection.path = "users/groups"
        self.assertEqual(collection.make_path(), "/api/v1/users/groups/")
        self.assertEqual(collection.make_path("456"), "/api/v1/users/groups/456/")


class TestResourceCollectionMakeUrl(unittest.TestCase):
    """Test ResourceCollection.make_url() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.mock_client.base_url = "https://api.example.com"
        self.root = ResourceRoot(self.mock_client)
        self.root.url_prefix = "api/v1"

    def test_make_url_without_part(self):
        """Test make_url() returns correct URL without part.

        According to API schema, collections have trailing slashes.
        The URL is base_url + make_path(), with the root prefix
        appearing exactly once.
        """
        collection = ResourceCollection(self.mock_client, root=self.root)
        collection.path = "users"
        self.assertEqual(
            collection.make_url(),
            "https://api.example.com/api/v1/users/"
        )

    def test_make_url_with_part(self):
        """Test make_url() returns correct URL with part.

        According to API schema, single resources have trailing slashes.
        """
        collection = ResourceCollection(self.mock_client, root=self.root)
        collection.path = "users"
        self.assertEqual(
            collection.make_url("123"),
            "https://api.example.com/api/v1/users/123/"
        )


class TestResourceMakePath(unittest.TestCase):
    """Test Resource.make_path() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.mock_client.base_url = "https://api.example.com"
        self.root = ResourceRoot(self.mock_client)
        self.root.url_prefix = "api/v1"
        self.collection = ResourceCollection(self.mock_client, root=self.root)
        self.collection.path = "users"

    def test_make_path_without_part(self):
        """Test make_path() returns correct path without part.

        According to API schema, single resources should have trailing slashes.
        The Resource implementation now correctly adds trailing slashes by default.
        """
        resource = Resource("123", parent=self.collection)
        self.assertEqual(resource.make_path(), "/api/v1/users/123/")

    def test_make_path_without_part_with_trailing_slash(self):
        """Test make_path() with end_slash=True follows API schema.

        According to API schema, single resources should have trailing slashes.
        """
        resource = Resource("123", parent=self.collection)
        self.assertEqual(resource.make_path(end_slash=True), "/api/v1/users/123/")

    def test_make_path_with_part(self):
        """Test make_path() returns correct path with part.

        This tests dead-end subresources/actions which should NOT have trailing slashes
        according to API schema.
        """
        resource = Resource("123", parent=self.collection)
        self.assertEqual(resource.make_path("profile"), "/api/v1/users/123/profile")

    def test_make_path_strips_leading_slash_from_part(self):
        """Test make_path() strips leading slash from part."""
        resource = Resource("123", parent=self.collection)
        self.assertEqual(resource.make_path("/profile"), "/api/v1/users/123/profile")

    def test_make_path_strips_trailing_slash_from_part(self):
        """Test make_path() strips trailing slash from part."""
        resource = Resource("123", parent=self.collection)
        self.assertEqual(resource.make_path("profile/"), "/api/v1/users/123/profile")

    def test_make_path_with_multiple_parts_in_constructor(self):
        """Test Resource construction with multiple parts.

        According to API schema, nested resources should have trailing slashes.
        """
        resource = Resource("123", "posts", "456", parent=self.collection)
        self.assertEqual(resource.make_path(), "/api/v1/users/123/posts/456/")

    def test_make_path_with_slashes_in_parts(self):
        """Test make_path() with leading/trailing slashes in constructor parts."""
        resource = Resource("/123/", "/posts/", parent=self.collection)
        # The constructor joins parts with '/', leading slashes in first part get stripped
        # by parent.make_path(), trailing slashes are preserved
        expected = "/api/v1/users/123///posts/"
        self.assertEqual(resource.make_path(), expected)


class TestResourceMakeUrl(unittest.TestCase):
    """Test Resource.make_url() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.mock_client.base_url = "https://api.example.com"
        self.root = ResourceRoot(self.mock_client)
        self.root.url_prefix = "api/v1"
        self.collection = ResourceCollection(self.mock_client, root=self.root)
        self.collection.path = "users"

    def test_make_url_without_part(self):
        """Test make_url() returns correct URL without part.

        The URL is base_url + make_path(): the item path as
        constructed, trailing slash included, with the root prefix
        appearing exactly once.
        """
        resource = Resource("123", parent=self.collection)
        self.assertEqual(
            resource.make_url(),
            "https://api.example.com/api/v1/users/123/"
        )

    def test_make_url_with_part(self):
        """Test make_url() returns correct URL with part."""
        resource = Resource("123", parent=self.collection)
        self.assertEqual(
            resource.make_url("profile"),
            "https://api.example.com/api/v1/users/123/profile"
        )


class TestPayloadHelpers(unittest.TestCase):
    """payload()/updates(): omit-None body builders shared by write routes."""

    def test_payload_drops_none_fields(self):
        self.assertEqual(
            payload(title="T", description=None, questions=None),
            {"title": "T"},
        )

    def test_payload_keeps_falsy_non_none_fields(self):
        # Falsy values are "provided" and must survive: is_public=False,
        # an empty-string description, a zero rate limit.
        self.assertEqual(
            payload(is_public=False, description="", rate_limit=0),
            {"is_public": False, "description": "", "rate_limit": 0},
        )

    def test_payload_empty_when_everything_is_none(self):
        self.assertEqual(payload(name=None, tag=None), {})

    def test_updates_passes_fields_through(self):
        self.assertEqual(
            updates(name="n", scopes=["traces:read"]),
            {"name": "n", "scopes": ["traces:read"]},
        )

    def test_updates_raises_when_every_field_is_none(self):
        # Campus PATCH routes reject an empty body outright.
        with self.assertRaises(ValueError) as ctx:
            updates(name=None, description=None)
        self.assertEqual(
            str(ctx.exception), "At least one field must be provided for update"
        )


if __name__ == "__main__":
    unittest.main()
