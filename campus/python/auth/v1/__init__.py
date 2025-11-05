"""campus.python.auth

Campus Auth resource.
"""

from ...interface import ResourceRoot
from . import (
    clients,
    credentials,
    logins,
    sessions,
    users,
    vaults,
)


class AuthRoot(ResourceRoot):
    """Campus Auth resource."""
    path: str = "/auth/v1"

    def __init__(self):
        self._clients = None
        self._credentials = None
        self._logins = None
        self._sessions = None
        self._users = None
        self._vaults = None

    @property
    def clients(self) -> clients.Clients:
        """Get the clients resource."""
        if not self._clients:
            self._clients = clients.Clients(root=self)
        return self._clients

    @property
    def credentials(self) -> credentials.Credentials:
        """Get the credentials resource."""
        if not self._credentials:
            self._credentials = credentials.Credentials(root=self)
        return self._credentials

    @property
    def logins(self) -> logins.Logins:
        """Get the logins resource."""
        if not self._logins:
            self._logins = logins.Logins(root=self)
        return self._logins

    @property
    def sessions(self) -> sessions.Sessions:
        """Get the sessions resource."""
        if not self._sessions:
            self._sessions = sessions.Sessions(root=self)
        return self._sessions

    @property
    def users(self) -> users.Users:
        """Get the users resource."""
        if not self._users:
            self._users = users.Users(root=self)
        return self._users

    @property
    def vaults(self) -> vaults.Vaults:
        """Get the vaults resource."""
        if not self._vaults:
            self._vaults = vaults.Vaults(root=self)
        return self._vaults
