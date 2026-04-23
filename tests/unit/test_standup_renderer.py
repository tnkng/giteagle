"""Tests for the standup renderer module."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import StringIO

from rich.console import Console

from giteagle.cli.standup_renderer import (
    RepoStandup,
    build_standup_data,
    compute_standup_since,
    render_standup,
)
from giteagle.core.models import Activity, ActivityType, Contributor, Repository


def _make_console() -> tuple[Console, StringIO]:
    """Create a Console that writes to a StringIO buffer."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=False, no_color=True, width=120)
    return console, buf


def _make_activity(
    repo_name: str = "testowner/test-repo",
    activity_type: ActivityType = ActivityType.COMMIT,
    title: str = "Test activity",
    username: str = "testuser",
    hours_ago: int = 0,
    metadata: dict | None = None,
) -> Activity:
    """Helper to create an Activity for testing."""
    owner, name = repo_name.split("/", 1)
    default_metadata: dict = {}
    if activity_type == ActivityType.COMMIT:
        default_metadata = {"sha": "abc1234", "parents": ["parent1"]}
    elif activity_type == ActivityType.PULL_REQUEST:
        default_metadata = {
            "number": 42,
            "state": "open",
            "merged": False,
            "merged_at": None,
            "closed_at": None,
        }
    elif activity_type == ActivityType.ISSUE:
        default_metadata = {
            "number": 10,
            "state": "open",
            "closed_at": None,
            "labels": [],
        }
    if metadata:
        default_metadata.update(metadata)

    return Activity(
        id=f"github:{activity_type.value}:{repo_name}:{title}",
        type=activity_type,
        repository=Repository(
            name=name,
            owner=owner,
            platform="github",
            url=f"https://github.com/{repo_name}",
        ),
        contributor=Contributor(username=username),
        timestamp=datetime.now(tz=UTC) - timedelta(hours=hours_ago),
        title=title,
        metadata=default_metadata,
    )


class TestComputeStandupSince:
    """Tests for the compute_standup_since function."""

    def test_weekday_returns_1_day(self) -> None:
        """On a Tuesday, days=1 returns yesterday midnight."""
        tuesday = datetime(2026, 2, 10, 14, 30, 0, tzinfo=UTC)  # Tuesday
        since = compute_standup_since(1, now=tuesday)
        assert since == datetime(2026, 2, 9, 0, 0, 0, tzinfo=UTC)

    def test_monday_skips_weekend(self) -> None:
        """On a Monday, days=1 returns Friday midnight."""
        monday = datetime(2026, 2, 9, 14, 30, 0, tzinfo=UTC)  # Monday
        since = compute_standup_since(1, now=monday)
        assert since == datetime(2026, 2, 6, 0, 0, 0, tzinfo=UTC)

    def test_custom_days(self) -> None:
        """days=3 returns 3 days ago regardless of day of week."""
        wednesday = datetime(2026, 2, 11, 10, 0, 0, tzinfo=UTC)
        since = compute_standup_since(3, now=wednesday)
        assert since == datetime(2026, 2, 8, 0, 0, 0, tzinfo=UTC)

    def test_monday_with_custom_days_no_skip(self) -> None:
        """On Monday with days=3, does NOT auto-adjust for weekend."""
        monday = datetime(2026, 2, 9, 14, 30, 0, tzinfo=UTC)
        since = compute_standup_since(3, now=monday)
        assert since == datetime(2026, 2, 6, 0, 0, 0, tzinfo=UTC)


class TestBuildStandupData:
    """Tests for the build_standup_data function."""

    def test_groups_by_repo(self) -> None:
        """Activities from 2 repos produce 2 RepoStandup entries."""
        since = datetime.now(tz=UTC) - timedelta(hours=2)
        activities = [
            _make_activity(repo_name="org/api", title="commit1"),
            _make_activity(repo_name="org/web", title="commit2"),
        ]
        result = build_standup_data(activities, since)
        assert len(result) == 2
        repo_names = {s.repo_name for s in result}
        assert repo_names == {"org/api", "org/web"}

    def test_separates_commits(self) -> None:
        """Commits go into the commits list."""
        since = datetime.now(tz=UTC) - timedelta(hours=2)
        activities = [
            _make_activity(activity_type=ActivityType.COMMIT, title="fix bug"),
        ]
        result = build_standup_data(activities, since)
        assert len(result) == 1
        assert len(result[0].commits) == 1
        assert result[0].commits[0].title == "fix bug"

    def test_separates_pr_opened(self) -> None:
        """PRs created within the window go into prs_opened."""
        since = datetime.now(tz=UTC) - timedelta(hours=2)
        activities = [
            _make_activity(
                activity_type=ActivityType.PULL_REQUEST,
                title="Add feature",
            ),
        ]
        result = build_standup_data(activities, since)
        assert len(result[0].prs_opened) == 1

    def test_separates_pr_merged(self) -> None:
        """PRs merged within the window go into prs_merged."""
        since = datetime.now(tz=UTC) - timedelta(hours=2)
        merged_at = (datetime.now(tz=UTC) - timedelta(hours=1)).isoformat()
        activities = [
            _make_activity(
                activity_type=ActivityType.PULL_REQUEST,
                title="Merged PR",
                hours_ago=24,  # Created before the window
                metadata={"merged": True, "merged_at": merged_at},
            ),
        ]
        result = build_standup_data(activities, since)
        assert len(result[0].prs_merged) == 1
        # Created before window, so not in prs_opened
        assert len(result[0].prs_opened) == 0

    def test_separates_issue_closed(self) -> None:
        """Issues closed within the window go into issues_closed."""
        since = datetime.now(tz=UTC) - timedelta(hours=2)
        closed_at = (datetime.now(tz=UTC) - timedelta(hours=1)).isoformat()
        activities = [
            _make_activity(
                activity_type=ActivityType.ISSUE,
                title="Fixed bug",
                hours_ago=24,  # Created before the window
                metadata={"state": "closed", "closed_at": closed_at},
            ),
        ]
        result = build_standup_data(activities, since)
        assert len(result[0].issues_closed) == 1
        assert len(result[0].issues_opened) == 0

    def test_empty_activities(self) -> None:
        """Empty activities list returns empty result."""
        since = datetime.now(tz=UTC) - timedelta(hours=2)
        result = build_standup_data([], since)
        assert result == []

    def test_filters_old_activities(self) -> None:
        """Activities before the since window are excluded."""
        since = datetime.now(tz=UTC) - timedelta(hours=2)
        activities = [
            _make_activity(title="old commit", hours_ago=48),
        ]
        result = build_standup_data(activities, since)
        assert result == []


class TestRepoStandup:
    """Tests for the RepoStandup dataclass."""

    def test_total_property(self) -> None:
        """Total counts all activity lists."""
        standup = RepoStandup(repo_name="org/repo")
        assert standup.total == 0

        standup.commits = [_make_activity()] * 3
        standup.prs_opened = [_make_activity(activity_type=ActivityType.PULL_REQUEST)] * 2
        assert standup.total == 5


class TestRenderStandup:
    """Tests for the render_standup function."""

    def test_renders_repo_name(self) -> None:
        """Output contains the repository name."""
        console, buf = _make_console()
        since = datetime.now(tz=UTC) - timedelta(hours=2)
        data = [
            RepoStandup(
                repo_name="org/api",
                commits=[_make_activity(repo_name="org/api")],
            ),
        ]
        render_standup(console, data, since=since)
        output = buf.getvalue()
        assert "org/api" in output

    def test_renders_commit_count(self) -> None:
        """Output contains commit count."""
        console, buf = _make_console()
        since = datetime.now(tz=UTC) - timedelta(hours=2)
        data = [
            RepoStandup(
                repo_name="org/api",
                commits=[_make_activity(repo_name="org/api")] * 3,
            ),
        ]
        render_standup(console, data, since=since)
        output = buf.getvalue()
        assert "Commits (3)" in output

    def test_renders_author(self) -> None:
        """Output contains the author name when provided."""
        console, buf = _make_console()
        since = datetime.now(tz=UTC) - timedelta(hours=2)
        data = [
            RepoStandup(
                repo_name="org/api",
                commits=[_make_activity(repo_name="org/api")],
            ),
        ]
        render_standup(console, data, author="igor", since=since)
        output = buf.getvalue()
        assert "igor" in output

    def test_empty_data_message(self) -> None:
        """Shows 'No activity' message when no data."""
        console, buf = _make_console()
        since = datetime.now(tz=UTC) - timedelta(hours=2)
        render_standup(console, [], since=since)
        output = buf.getvalue()
        assert "No activity" in output

    def test_renders_total_footer(self) -> None:
        """Output contains total activity count."""
        console, buf = _make_console()
        since = datetime.now(tz=UTC) - timedelta(hours=2)
        data = [
            RepoStandup(
                repo_name="org/api",
                commits=[_make_activity(repo_name="org/api")] * 2,
                prs_opened=[
                    _make_activity(
                        repo_name="org/api",
                        activity_type=ActivityType.PULL_REQUEST,
                    ),
                ],
            ),
        ]
        render_standup(console, data, since=since)
        output = buf.getvalue()
        assert "3 activities" in output
        assert "1 repositories" in output
