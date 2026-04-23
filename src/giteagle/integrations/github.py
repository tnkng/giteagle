"""GitHub API integration."""

import asyncio
import logging
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from giteagle.core.models import Activity, ActivityType, Contributor, Repository
from giteagle.integrations.base import PlatformClient

logger = logging.getLogger(__name__)

_SAFE_PATH_SEGMENT = re.compile(r"^[a-zA-Z0-9._-]+$")


def _validate_path_segment(value: str, name: str) -> str:
    """Validate that a value is safe to use in a URL path segment."""
    if not _SAFE_PATH_SEGMENT.match(value):
        raise ValueError(f"Invalid {name}: {value!r} contains unsafe characters")
    return value


class GitHubAPIError(Exception):
    """Error from GitHub API."""

    def __init__(self, message: str, status_code: int = 0, response: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response or {}


class RateLimitError(GitHubAPIError):
    """GitHub rate limit exceeded."""

    def __init__(self, reset_at: datetime, message: str = "Rate limit exceeded"):
        super().__init__(message, status_code=403)
        self.reset_at = reset_at


class GitHubClient(PlatformClient):
    """Client for GitHub API."""

    BASE_URL = "https://api.github.com"

    def __init__(
        self,
        token: str | None = None,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
    ):
        self._token = token
        self._base_url = base_url.rstrip("/")
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=timeout,
        )

    @property
    def platform_name(self) -> str:
        return "github"

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        retry_count: int = 3,
    ) -> Any:
        """Make an API request with retry logic."""
        last_error: Exception | None = None

        for attempt in range(retry_count):
            try:
                response = await self._client.request(method, path, params=params)

                if response.status_code == 403:
                    # Check for rate limiting
                    remaining = response.headers.get("X-RateLimit-Remaining", "1")
                    if remaining == "0":
                        reset_timestamp = int(response.headers.get("X-RateLimit-Reset", "0"))
                        reset_at = datetime.fromtimestamp(reset_timestamp, tz=UTC)
                        raise RateLimitError(reset_at)

                if response.status_code == 404:
                    raise GitHubAPIError("Resource not found", 404)

                if response.status_code >= 400:
                    error_data = response.json() if response.content else {}
                    message = error_data.get("message", f"HTTP {response.status_code}")
                    raise GitHubAPIError(message, response.status_code, error_data)

                return response.json()

            except httpx.TimeoutException:
                last_error = GitHubAPIError("Request timed out")
                if attempt < retry_count - 1:
                    await asyncio.sleep(2**attempt)
            except httpx.NetworkError as e:
                last_error = GitHubAPIError(f"Network error: {e}")
                if attempt < retry_count - 1:
                    await asyncio.sleep(2**attempt)

        raise last_error or GitHubAPIError("Unknown error")

    async def _paginate(
        self,
        path: str,
        params: dict | None = None,
        limit: int = 100,
    ) -> list[Any]:
        """Paginate through API results."""
        params = params or {}
        params["per_page"] = min(100, limit)
        page = 1
        results: list[Any] = []

        while len(results) < limit:
            params["page"] = page
            data = await self._request("GET", path, params=params)

            if not data:
                break

            results.extend(data)
            page += 1

            if len(data) < params["per_page"]:
                break

        return results[:limit]

    def _parse_repository(self, data: dict) -> Repository:
        """Parse GitHub API response into Repository model."""
        return Repository(
            name=data["name"],
            owner=data["owner"]["login"],
            platform="github",
            url=data["html_url"],
            description=data.get("description"),
            default_branch=data.get("default_branch", "main"),
            is_private=data.get("private", False),
        )

    def _parse_contributor(self, data: dict) -> Contributor:
        """Parse GitHub API user data into Contributor model."""
        return Contributor(
            username=data.get("login", data.get("name", "unknown")),
            name=data.get("name"),
            email=data.get("email"),
            avatar_url=data.get("avatar_url"),
        )

    async def get_repository(self, owner: str, name: str) -> Repository:
        """Fetch repository information."""
        _validate_path_segment(owner, "owner")
        _validate_path_segment(name, "name")
        data = await self._request("GET", f"/repos/{owner}/{name}")
        return self._parse_repository(data)

    async def list_repositories(
        self,
        owner: str | None = None,
        org: str | None = None,
    ) -> list[Repository]:
        """List repositories for a user or organization."""
        if org:
            _validate_path_segment(org, "org")
            path = f"/orgs/{org}/repos"
        elif owner:
            _validate_path_segment(owner, "owner")
            path = f"/users/{owner}/repos"
        else:
            path = "/user/repos"

        data = await self._paginate(path, limit=100)
        return [self._parse_repository(repo) for repo in data]

    async def get_commits(
        self,
        repository: Repository,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[Activity]:
        """Fetch commit activities for a repository."""
        params: dict[str, Any] = {}
        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()

        path = f"/repos/{repository.owner}/{repository.name}/commits"
        commits = await self._paginate(path, params=params, limit=limit)

        activities = []
        for commit in commits:
            # Handle commits with no author info
            author_data = commit.get("author") or {}
            commit_data = commit.get("commit", {})
            commit_author = commit_data.get("author", {})

            contributor = Contributor(
                username=author_data.get("login", commit_author.get("name", "unknown")),
                name=commit_author.get("name"),
                email=commit_author.get("email"),
                avatar_url=author_data.get("avatar_url"),
            )

            # Parse timestamp
            timestamp_str = commit_author.get("date", "")
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except ValueError:
                timestamp = datetime.now(tz=UTC)

            activity = Activity(
                id=f"github:commit:{commit['sha']}",
                type=ActivityType.COMMIT,
                repository=repository,
                contributor=contributor,
                timestamp=timestamp,
                title=commit_data.get("message", "").split("\n")[0][:100],
                description=commit_data.get("message"),
                url=commit.get("html_url"),
                metadata={
                    "sha": commit["sha"],
                    "parents": [p["sha"] for p in commit.get("parents", [])],
                    "stats": commit.get("stats", {}),
                },
            )
            activities.append(activity)

        return activities

    async def get_pull_requests(
        self,
        repository: Repository,
        since: datetime | None = None,
        state: str = "all",
        limit: int = 100,
    ) -> list[Activity]:
        """Fetch pull request activities for a repository."""
        params = {"state": state, "sort": "updated", "direction": "desc"}

        path = f"/repos/{repository.owner}/{repository.name}/pulls"
        prs = await self._paginate(path, params=params, limit=limit)

        activities = []
        for pr in prs:
            # Filter by date if specified
            updated_at = datetime.fromisoformat(pr["updated_at"].replace("Z", "+00:00"))
            if since and updated_at < since:
                continue

            user_data = pr.get("user", {})
            contributor = self._parse_contributor(user_data)

            created_at = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))

            activity = Activity(
                id=f"github:pr:{repository.full_name}:{pr['number']}",
                type=ActivityType.PULL_REQUEST,
                repository=repository,
                contributor=contributor,
                timestamp=created_at,
                title=pr.get("title", ""),
                description=pr.get("body"),
                url=pr.get("html_url"),
                metadata={
                    "number": pr["number"],
                    "state": pr["state"],
                    "merged": pr.get("merged", False),
                    "merged_at": pr.get("merged_at"),
                    "closed_at": pr.get("closed_at"),
                    "additions": pr.get("additions", 0),
                    "deletions": pr.get("deletions", 0),
                },
            )
            activities.append(activity)

        return activities

    async def get_issues(
        self,
        repository: Repository,
        since: datetime | None = None,
        state: str = "all",
        limit: int = 100,
    ) -> list[Activity]:
        """Fetch issue activities for a repository."""
        params: dict[str, Any] = {"state": state, "sort": "updated", "direction": "desc"}
        if since:
            params["since"] = since.isoformat()

        path = f"/repos/{repository.owner}/{repository.name}/issues"
        issues = await self._paginate(path, params=params, limit=limit)

        activities = []
        for issue in issues:
            # Skip pull requests (they appear in the issues endpoint too)
            if "pull_request" in issue:
                continue

            user_data = issue.get("user", {})
            contributor = self._parse_contributor(user_data)

            created_at = datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))

            activity = Activity(
                id=f"github:issue:{repository.full_name}:{issue['number']}",
                type=ActivityType.ISSUE,
                repository=repository,
                contributor=contributor,
                timestamp=created_at,
                title=issue.get("title", ""),
                description=issue.get("body"),
                url=issue.get("html_url"),
                metadata={
                    "number": issue["number"],
                    "state": issue["state"],
                    "closed_at": issue.get("closed_at"),
                    "labels": [label["name"] for label in issue.get("labels", [])],
                },
            )
            activities.append(activity)

        return activities

    async def get_activities(
        self,
        repository: Repository,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[Activity]:
        """Fetch all activities for a repository."""
        # Fetch different activity types concurrently
        commits_task = self.get_commits(repository, since=since, until=until, limit=limit)
        prs_task = self.get_pull_requests(repository, since=since, limit=limit)
        issues_task = self.get_issues(repository, since=since, limit=limit)

        commits, prs, issues = await asyncio.gather(
            commits_task, prs_task, issues_task, return_exceptions=True
        )

        activities: list[Activity] = []

        for label, result in [("commits", commits), ("pull_requests", prs), ("issues", issues)]:
            if isinstance(result, BaseException):
                logger.warning("Failed to fetch %s for %s: %s", label, repository.full_name, result)
            elif isinstance(result, list):
                activities.extend(result)

        # Sort by timestamp descending
        activities.sort(key=lambda a: a.timestamp, reverse=True)

        return activities[:limit]

    async def get_authenticated_user(self) -> str:
        """Get the username of the authenticated user."""
        data = await self._request("GET", "/user")
        login: str = data["login"]
        return login

    async def get_open_pull_requests(
        self,
        repository: Repository,
        *,
        limit: int = 100,
    ) -> list[Any]:
        """Fetch open pull requests as raw GitHub API dicts."""
        params: dict[str, Any] = {
            "state": "open",
            "sort": "created",
            "direction": "asc",
        }
        path = f"/repos/{repository.owner}/{repository.name}/pulls"
        return await self._paginate(path, params=params, limit=limit)

    async def get_closed_pull_requests(
        self,
        repository: Repository,
        *,
        since: datetime | None = None,
        limit: int = 200,
    ) -> list[Any]:
        """Fetch closed pull requests as raw GitHub API dicts."""
        params: dict[str, Any] = {
            "state": "closed",
            "sort": "updated",
            "direction": "desc",
        }
        path = f"/repos/{repository.owner}/{repository.name}/pulls"
        prs = await self._paginate(path, params=params, limit=limit)

        if since:
            result: list[Any] = []
            for pr in prs:
                closed_at_str = pr.get("closed_at") or pr.get("updated_at", "")
                if closed_at_str:
                    closed_dt = datetime.fromisoformat(closed_at_str.replace("Z", "+00:00"))
                    if closed_dt >= since:
                        result.append(pr)
            return result
        return prs

    async def get_pr_reviews(
        self,
        repository: Repository,
        pr_number: int,
    ) -> list[Any]:
        """Fetch reviews for a pull request."""
        _validate_path_segment(str(pr_number), "pr_number")
        path = f"/repos/{repository.owner}/{repository.name}/pulls/{pr_number}/reviews"
        result = await self._request("GET", path)
        if isinstance(result, list):
            return result
        return []

    async def get_commit_status(
        self,
        repository: Repository,
        sha: str,
    ) -> dict[str, Any]:
        """Fetch combined commit status for a ref."""
        _validate_path_segment(sha, "sha")
        path = f"/repos/{repository.owner}/{repository.name}/commits/{sha}/status"
        result = await self._request("GET", path)
        if isinstance(result, dict):
            return result
        return {"state": "unknown"}

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
