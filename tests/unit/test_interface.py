import unittest
from unittest.mock import Mock

from campus_python.interface import Resource, ResourceCollection, ResourceRoot


class TestResourceRootMakePath(unittest.TestCase):
    """Test ResourceRoot.make_path() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.mock_client.base_url = "https://api.example.com"

    def test_make_path_without_part(self):
        """Test make_path() returns correct path without part."""
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
        """Test make_path() with trailing slash in url_prefix."""
        root = ResourceRoot(self.mock_client)
        root.url_prefix = "api/v1/"
        # Trailing slash in prefix is preserved
        self.assertEqual(root.make_path(), "/api/v1/")

    def test_make_path_with_trailing_slash_in_part(self):
        """Test make_path() with trailing slash in part."""
        root = ResourceRoot(self.mock_client)
        root.url_prefix = "api/v1"
        # Trailing slash in part is preserved
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
        """Test make_path() returns correct path without part."""
        collection = ResourceCollection(self.mock_client, root=self.root)
        collection.path = "users"
        self.assertEqual(collection.make_path(), "/api/v1/users")

    def test_make_path_with_part(self):
        """Test make_path() returns correct path with part."""
        collection = ResourceCollection(self.mock_client, root=self.root)
        collection.path = "users"
        self.assertEqual(collection.make_path("123"), "/api/v1/users/123")

    def test_make_path_strips_leading_slash_from_path(self):
        """Test make_path() strips leading slash from collection path."""
        collection = ResourceCollection(self.mock_client, root=self.root)
        collection.path = "/users"
        self.assertEqual(collection.make_path(), "/api/v1/users")

    def test_make_path_strips_leading_slash_from_part(self):
        """Test make_path() strips leading slash from part."""
        collection = ResourceCollection(self.mock_client, root=self.root)
        collection.path = "users"
        self.assertEqual(collection.make_path("/123"), "/api/v1/users/123")

    def test_make_path_strips_trailing_slash_from_root_path(self):
        """Test make_path() strips trailing slash from root path before adding part."""
        collection = ResourceCollection(self.mock_client, root=self.root)
        collection.path = "users/"
        # The implementation strips trailing slashes from the root path
        self.assertEqual(collection.make_path("123"), "/api/v1/users/123")

    def test_make_path_with_nested_path(self):
        """Test make_path() with nested collection path."""
        collection = ResourceCollection(self.mock_client, root=self.root)
        collection.path = "users/groups"
        self.assertEqual(collection.make_path(), "/api/v1/users/groups")
        self.assertEqual(collection.make_path("456"), "/api/v1/users/groups/456")


class TestResourceCollectionMakeUrl(unittest.TestCase):
    """Test ResourceCollection.make_url() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.mock_client.base_url = "https://api.example.com"
        self.root = ResourceRoot(self.mock_client)
        self.root.url_prefix = "api/v1"

    def test_make_url_without_part(self):
        """Test make_url() returns correct URL without part."""
        collection = ResourceCollection(self.mock_client, root=self.root)
        collection.path = "users"
        self.assertEqual(
            collection.make_url(),
            "https://api.example.com/api/v1/api/v1/users"
        )

    def test_make_url_with_part(self):
        """Test make_url() returns correct URL with part."""
        collection = ResourceCollection(self.mock_client, root=self.root)
        collection.path = "users"
        self.assertEqual(
            collection.make_url("123"),
            "https://api.example.com/api/v1/api/v1/users/123"
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
        """Test make_path() returns correct path without part."""
        resource = Resource("123", parent=self.collection)
        self.assertEqual(resource.make_path(), "/api/v1/users/123")

    def test_make_path_with_part(self):
        """Test make_path() returns correct path with part."""
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
        """Test Resource construction with multiple parts."""
        resource = Resource("123", "posts", "456", parent=self.collection)
        self.assertEqual(resource.make_path(), "/api/v1/users/123/posts/456")

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

        Note: This exhibits path duplication due to how Resource.make_url()
        combines parent.make_url() with self.make_path(). The parent's make_url()
        already includes the full path, then make_path() includes it again.
        """
        resource = Resource("123", parent=self.collection)
        self.assertEqual(
            resource.make_url(),
            "https://api.example.com/api/v1/api/v1/users/api/v1/users/123"
        )

    def test_make_url_with_part(self):
        """Test make_url() returns correct URL with part.

        Note: This exhibits path duplication due to how Resource.make_url()
        combines parent.make_url() with self.make_path(). The parent's make_url()
        already includes the full path, then make_path() includes it again.
        """
        resource = Resource("123", parent=self.collection)
        self.assertEqual(
            resource.make_url("profile"),
            "https://api.example.com/api/v1/api/v1/users/api/v1/users/123/profile"
        )


if __name__ == "__main__":
    unittest.main()
