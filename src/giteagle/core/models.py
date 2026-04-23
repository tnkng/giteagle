"""Core data models for Giteagle."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ActivityType(str, Enum):
    """Types of activities that can be tracked."""

    COMMIT = "commit"
    PULL_REQUEST = "pull_request"
    PULL_REQUEST_REVIEW = "pull_request_review"
    ISSUE = "issue"
    ISSUE_COMMENT = "issue_comment"
    RELEASE = "release"


class Contributor(BaseModel):
    """A person who contributes to repositories."""

    username: str = Field(..., description="Username on the platform")
    name: str | None = Field(None, description="Display name")
    email: str | None = Field(None, description="Email address")
    avatar_url: str | None = Field(None, description="URL to avatar image")

    def __hash__(self) -> int:
        return hash(self.username)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Contributor):
            return False
        return self.username == other.username


class Repository(BaseModel):
    """A git repository being tracked."""

    name: str = Field(..., description="Repository name")
    owner: str = Field(..., description="Owner/organization name")
    platform: str = Field(..., description="Platform (github, gitlab, bitbucket)")
    url: HttpUrl = Field(..., description="Repository URL")
    description: str | None = Field(None, description="Repository description")
    default_branch: str = Field("main", description="Default branch name")
    is_private: bool = Field(False, description="Whether the repository is private")

    @property
    def full_name(self) -> str:
        """Return the full repository name (owner/name)."""
        return f"{self.owner}/{self.name}"

    def __hash__(self) -> int:
        return hash((self.platform, self.owner, self.name))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Repository):
            return False
        return (
            self.platform == other.platform
            and self.owner == other.owner
            and self.name == other.name
        )


class Activity(BaseModel):
    """An activity event in a repository."""

    id: str = Field(..., description="Unique identifier for this activity")
    type: ActivityType = Field(..., description="Type of activity")
    repository: Repository = Field(..., description="Repository where activity occurred")
    contributor: Contributor = Field(..., description="Who performed the activity")
    timestamp: datetime = Field(..., description="When the activity occurred")
    title: str = Field(..., description="Activity title/summary")
    description: str | None = Field(None, description="Detailed description")
    url: HttpUrl | None = Field(None, description="URL to view this activity")
    metadata: dict = Field(default_factory=dict, description="Additional platform-specific data")

    def __hash__(self) -> int:
        return hash(self.id)

    model_config = ConfigDict(frozen=False)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Activity):
            return False
        return self.id == other.id
