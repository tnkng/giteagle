"""Tests for the log renderer module."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import StringIO

from rich.console import Console

from giteagle.cli.log_renderer import (
    assign_repo_colors,
    get_display_names,
    group_by_date,
    render_log,
)
from giteagle.core.models import Activity, ActivityType, Contributor, Repository


def _make_console() -> tuple[Console, StringIO]:
    """Create a Console that writes to a StringIO buffer."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=False, no_color=True, width=120)
    return console, buf


def _make_activity(
    repo_name: str = "testowner/test-repo",
    sha: str = "abc1234def5678",
    title: str = "Test commit",
    parents: list[str] | None = None,
    hours_ago: int = 0,
) -> Activity:
    """Helper to create a commit Activity."""
    owner, name = repo_name.split("/", 1)
    return Activity(
        id=f"github:commit:{sha}",
        type=ActivityType.COMMIT,
        repository=Repository(
            name=name,
            owner=owner,
            platform="github",
            url=f"https://github.com/{repo_name}",
        ),
        contributor=Contributor(username="testuser"),
        timestamp=datetime.now(tz=UTC) - timedelta(hours=hours_ago),
        title=title,
        metadata={
            "sha": sha,
            "parents": parents if parents is not None else ["parent1"],
        },
    )


class TestAssignRepoColors:
    """Tests for the assign_repo_colors function."""

    def test_single_repo(self) -> None:
        colors = assign_repo_colors(["org/api"])
        assert len(colors) == 1
        assert "org/api" in colors

    def test_deterministic_assignment(self) -> None:
        colors1 = assign_repo_colors(["org/api", "org/web"])
        colors2 = assign_repo_colors(["org/web", "org/api"])
        assert colors1 == colors2

    def test_wraps_around_palette(self) -> None:
        repos = [f"org/repo-{i}" for i in range(15)]
        colors = assign_repo_colors(repos)
        assert len(colors) == 15
        assert all(c for c in colors.values())


class TestGetDisplayNames:
    """Tests for the get_display_names function."""

    def test_unique_short_names(self) -> None:
        names = get_display_names(["org1/api", "org1/frontend"])
        assert names["org1/api"] == "api"
        assert names["org1/frontend"] == "frontend"

    def test_conflicting_short_names(self) -> None:
        names = get_display_names(["org1/api", "org2/api"])
        assert names["org1/api"] == "org1/api"
        assert names["org2/api"] == "org2/api"

    def test_mixed(self) -> None:
        names = get_display_names(["org1/api", "org2/api", "org1/web"])
        assert names["org1/api"] == "org1/api"
        assert names["org2/api"] == "org2/api"
        assert names["org1/web"] == "web"


class TestGroupByDate:
    """Tests for the group_by_date function."""

    def test_groups_by_date(self) -> None:
        activities = [_make_activity(sha=f"sha{i}", hours_ago=i * 12) for i in range(4)]
        groups = group_by_date(activities)
        assert len(groups) >= 1
        total = sum(len(g[1]) for g in groups)
        assert total == 4

    def test_empty_list(self) -> None:
        groups = group_by_date([])
        assert groups == []


class TestRenderLog:
    """Tests for the render_log function."""

    def test_empty_activities(self) -> None:
        console, buf = _make_console()
        render_log(console, [], {}, {})
        output = buf.getvalue()
        assert "No commits found" in output

    def test_renders_sha_and_message(self) -> None:
        console, buf = _make_console()
        activity = _make_activity(sha="abc1234def5678", title="Fix the bug")
        colors = {"testowner/test-repo": "cyan"}
        names = {"testowner/test-repo": "test-repo"}
        render_log(console, [activity], colors, names)
        output = buf.getvalue()
        assert "abc1234" in output
        assert "Fix the bug" in output

    def test_renders_merge_indicator(self) -> None:
        console, buf = _make_console()
        activity = _make_activity(sha="abc1234", title="Merge branch", parents=["p1", "p2"])
        colors = {"testowner/test-repo": "cyan"}
        names = {"testowner/test-repo": "test-repo"}
        render_log(console, [activity], colors, names)
        output = buf.getvalue()
        assert "merge" in output.lower()

    def test_no_merge_indicator_for_single_parent(self) -> None:
        console, buf = _make_console()
        activity = _make_activity(sha="abc1234", title="Normal commit")
        colors = {"testowner/test-repo": "cyan"}
        names = {"testowner/test-repo": "test-repo"}
        render_log(console, [activity], colors, names)
        output = buf.getvalue()
        assert "(merge)" not in output

    def test_summary_footer(self) -> None:
        console, buf = _make_console()
        activities = [_make_activity(sha=f"sha{i}") for i in range(3)]
        colors = {"testowner/test-repo": "cyan"}
        names = {"testowner/test-repo": "test-repo"}
        render_log(console, activities, colors, names)
        output = buf.getvalue()
        assert "3 commits" in output
        assert "1 repositories" in output

    def test_multiple_repos(self) -> None:
        console, buf = _make_console()
        activities = [
            _make_activity(repo_name="org/api", sha="sha1", title="API fix"),
            _make_activity(repo_name="org/web", sha="sha2", title="Web fix"),
        ]
        colors = {"org/api": "cyan", "org/web": "magenta"}
        names = {"org/api": "api", "org/web": "web"}
        render_log(console, activities, colors, names)
        output = buf.getvalue()
        assert "API fix" in output
        assert "Web fix" in output
        assert "2 commits" in output
        assert "2 repositories" in output
