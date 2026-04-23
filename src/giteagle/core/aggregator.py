"""Activity aggregation engine for combining data from multiple repositories."""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from giteagle.core.models import Activity, ActivityType, Contributor, Repository


@dataclass
class AggregationResult:
    """Result of aggregating activities."""

    activities: list[Activity] = field(default_factory=list)
    total_count: int = 0
    by_repository: dict[str, int] = field(default_factory=dict)
    by_contributor: dict[str, int] = field(default_factory=dict)
    by_type: dict[ActivityType, int] = field(default_factory=dict)
    date_range: tuple[datetime | None, datetime | None] = (None, None)


@dataclass
class ContributorStats:
    """Statistics for a single contributor."""

    contributor: Contributor
    total_activities: int = 0
    by_type: dict[ActivityType, int] = field(default_factory=dict)
    by_repository: dict[str, int] = field(default_factory=dict)
    first_activity: datetime | None = None
    last_activity: datetime | None = None


@dataclass
class RepositoryStats:
    """Statistics for a single repository."""

    repository: Repository
    total_activities: int = 0
    by_type: dict[ActivityType, int] = field(default_factory=dict)
    contributors: set[str] = field(default_factory=set)
    first_activity: datetime | None = None
    last_activity: datetime | None = None


class ActivityAggregator:
    """Aggregates and analyzes activities across multiple repositories."""

    def __init__(self) -> None:
        self._activities: list[Activity] = []

    def add_activities(self, activities: list[Activity]) -> None:
        """Add activities to the aggregator."""
        self._activities.extend(activities)

    def clear(self) -> None:
        """Clear all stored activities."""
        self._activities.clear()

    @property
    def activities(self) -> list[Activity]:
        """Return all stored activities."""
        return self._activities.copy()

    def filter(
        self,
        *,
        repositories: list[Repository] | None = None,
        contributors: list[str] | None = None,
        activity_types: list[ActivityType] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        predicate: Callable[[Activity], bool] | None = None,
    ) -> list[Activity]:
        """Filter activities based on criteria."""
        result = self._activities

        if repositories:
            repo_set = {r.full_name for r in repositories}
            result = [a for a in result if a.repository.full_name in repo_set]

        if contributors:
            contrib_set = set(contributors)
            result = [a for a in result if a.contributor.username in contrib_set]

        if activity_types:
            type_set = set(activity_types)
            result = [a for a in result if a.type in type_set]

        if since:
            result = [a for a in result if a.timestamp >= since]

        if until:
            result = [a for a in result if a.timestamp <= until]

        if predicate:
            result = [a for a in result if predicate(a)]

        return result

    def aggregate(
        self,
        *,
        repositories: list[Repository] | None = None,
        contributors: list[str] | None = None,
        activity_types: list[ActivityType] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> AggregationResult:
        """Aggregate activities and compute statistics."""
        filtered = self.filter(
            repositories=repositories,
            contributors=contributors,
            activity_types=activity_types,
            since=since,
            until=until,
        )

        result = AggregationResult(
            activities=sorted(filtered, key=lambda a: a.timestamp, reverse=True),
            total_count=len(filtered),
        )

        by_repo: dict[str, int] = defaultdict(int)
        by_contrib: dict[str, int] = defaultdict(int)
        by_type: dict[ActivityType, int] = defaultdict(int)

        min_date: datetime | None = None
        max_date: datetime | None = None

        for activity in filtered:
            by_repo[activity.repository.full_name] += 1
            by_contrib[activity.contributor.username] += 1
            by_type[activity.type] += 1

            if min_date is None or activity.timestamp < min_date:
                min_date = activity.timestamp
            if max_date is None or activity.timestamp > max_date:
                max_date = activity.timestamp

        result.by_repository = dict(by_repo)
        result.by_contributor = dict(by_contrib)
        result.by_type = dict(by_type)
        result.date_range = (min_date, max_date)

        return result

    def get_contributor_stats(self, username: str) -> ContributorStats | None:
        """Get statistics for a specific contributor."""
        user_activities = [a for a in self._activities if a.contributor.username == username]

        if not user_activities:
            return None

        stats = ContributorStats(contributor=user_activities[0].contributor)

        for activity in user_activities:
            stats.total_activities += 1
            stats.by_type[activity.type] = stats.by_type.get(activity.type, 0) + 1
            stats.by_repository[activity.repository.full_name] = (
                stats.by_repository.get(activity.repository.full_name, 0) + 1
            )

            if stats.first_activity is None or activity.timestamp < stats.first_activity:
                stats.first_activity = activity.timestamp
            if stats.last_activity is None or activity.timestamp > stats.last_activity:
                stats.last_activity = activity.timestamp

        return stats

    def get_repository_stats(self, repository: Repository) -> RepositoryStats | None:
        """Get statistics for a specific repository."""
        repo_activities = [
            a for a in self._activities if a.repository.full_name == repository.full_name
        ]

        if not repo_activities:
            return None

        stats = RepositoryStats(repository=repository)

        for activity in repo_activities:
            stats.total_activities += 1
            stats.by_type[activity.type] = stats.by_type.get(activity.type, 0) + 1
            stats.contributors.add(activity.contributor.username)

            if stats.first_activity is None or activity.timestamp < stats.first_activity:
                stats.first_activity = activity.timestamp
            if stats.last_activity is None or activity.timestamp > stats.last_activity:
                stats.last_activity = activity.timestamp

        return stats

    def get_activity_timeline(
        self,
        *,
        granularity: str = "day",
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict[str, int]:
        """Get activity counts grouped by time period."""
        filtered = self.filter(since=since, until=until)

        timeline: dict[str, int] = defaultdict(int)

        for activity in filtered:
            if granularity == "hour":
                key = activity.timestamp.strftime("%Y-%m-%d %H:00")
            elif granularity == "day":
                key = activity.timestamp.strftime("%Y-%m-%d")
            elif granularity == "week":
                # Get the Monday of the week
                monday = activity.timestamp - timedelta(days=activity.timestamp.weekday())
                key = monday.strftime("%Y-%m-%d")
            elif granularity == "month":
                key = activity.timestamp.strftime("%Y-%m")
            else:
                key = activity.timestamp.strftime("%Y-%m-%d")

            timeline[key] += 1

        return dict(sorted(timeline.items()))

    def get_top_contributors(self, limit: int = 10) -> list[tuple[str, int]]:
        """Get the top contributors by activity count."""
        counts: dict[str, int] = defaultdict(int)
        for activity in self._activities:
            counts[activity.contributor.username] += 1

        sorted_contributors = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_contributors[:limit]

    def get_most_active_repositories(self, limit: int = 10) -> list[tuple[str, int]]:
        """Get the most active repositories by activity count."""
        counts: dict[str, int] = defaultdict(int)
        for activity in self._activities:
            counts[activity.repository.full_name] += 1

        sorted_repos = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_repos[:limit]
