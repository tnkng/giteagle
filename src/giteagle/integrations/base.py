"""Base class for platform integrations."""

from abc import ABC, abstractmethod
from datetime import datetime

from giteagle.core.models import Activity, Repository


class PlatformClient(ABC):
    """Abstract base class for platform-specific API clients."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the name of this platform."""
        pass

    @abstractmethod
    async def get_repository(self, owner: str, name: str) -> Repository:
        """Fetch repository information."""
        pass

    @abstractmethod
    async def list_repositories(
        self,
        owner: str | None = None,
        org: str | None = None,
    ) -> list[Repository]:
        """List repositories for a user or organization."""
        pass

    @abstractmethod
    async def get_activities(
        self,
        repository: Repository,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[Activity]:
        """Fetch activities for a repository."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the client and release resources."""
        pass

    async def __aenter__(self) -> PlatformClient:
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore
        """Exit async context manager."""
        await self.close()
