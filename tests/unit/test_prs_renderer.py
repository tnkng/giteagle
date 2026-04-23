"""Tests for the PR dashboard renderer module."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import StringIO

from rich.console import Console

from giteagle.cli.prs_renderer import (
    PullRequestInfo,
    ReviewStatus,
    age_display,
    build_pr_infos,
    render_prs,
)


def _make_console() -> tuple[Console, StringIO]:
    """Create a Console that writes to a StringIO buffer."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=False, no_color=True, width=120)
    return console, buf


class TestAgeDisplay:
    """Tests for the age_display function."""

    def test_minutes(self) -> None:
        now = datetime(2026, 2, 9, 12, 0, 0, tzinfo=UTC)
        created = datetime(2026, 2, 9, 11, 30, 0, tzinfo=UTC)
        assert age_display(created, now=now) == "30m"

    def test_hours(self) -> None:
        now = datetime(2026, 2, 9, 14, 0, 0, tzinfo=UTC)
        created = datetime(2026, 2, 9, 12, 0, 0, tzinfo=UTC)
        assert age_display(created, now=now) == "2h"

    def test_days(self) -> None:
        now = datetime(2026, 2, 9, 12, 0, 0, tzinfo=UTC)
        created = datetime(2026, 2, 6, 12, 0, 0, tzinfo=UTC)
        assert age_display(created, now=now) == "3d"

    def test_weeks(self) -> None:
        now = datetime(2026, 2, 9, 12, 0, 0, tzinfo=UTC)
        created = datetime(2026, 1, 26, 12, 0, 0, tzinfo=UTC)
        assert age_display(created, now=now) == "2w"


class TestReviewStatus:
    """Tests for the ReviewStatus dataclass."""

    def test_pending_by_default(self) -> None:
        status = ReviewStatus()
        assert status.summary == "pending"

    def test_approved(self) -> None:
        status = ReviewStatus(approved=2)
        assert status.summary == "approved"

    def test_changes_requested_takes_precedence(self) -> None:
        status = ReviewStatus(approved=1, changes_requested=1)
        assert status.summary == "changes_requested"


class TestBuildPrInfos:
    """Tests for the build_pr_infos function."""

    def test_basic_pr(self) -> None:
        raw_prs = [
            {
                "number": 42,
                "title": "Add feature",
                "user": {"login": "alice"},
                "created_at": "2026-02-08T10:00:00Z",
                "head": {"sha": "abc123"},
                "labels": [{"name": "enhancement"}],
                "html_url": "https://github.com/org/repo/pull/42",
            },
        ]
        reviews_map: dict[int, list[dict]] = {42: []}
        status_map: dict[str, dict] = {"abc123": {"state": "success"}}

        infos = build_pr_infos(raw_prs, reviews_map, status_map, "org/repo")

        assert len(infos) == 1
        assert infos[0].number == 42
        assert infos[0].title == "Add feature"
        assert infos[0].author == "alice"
        assert infos[0].labels == ["enhancement"]
        assert infos[0].ci_status == "success"

    def test_review_status_approved(self) -> None:
        raw_prs = [
            {
                "number": 1,
                "title": "PR",
                "user": {"login": "bob"},
                "created_at": "2026-02-08T10:00:00Z",
                "head": {"sha": "def456"},
                "labels": [],
                "html_url": "",
            },
        ]
        reviews_map: dict[int, list[dict]] = {
            1: [
                {
                    "user": {"login": "reviewer1"},
                    "state": "APPROVED",
                    "submitted_at": "2026-02-08T12:00:00Z",
                },
            ],
        }
        status_map: dict[str, dict] = {}

        infos = build_pr_infos(raw_prs, reviews_map, status_map, "org/repo")
        assert infos[0].review_status.summary == "approved"
        assert infos[0].review_status.approved == 1

    def test_review_status_changes_requested(self) -> None:
        raw_prs = [
            {
                "number": 1,
                "title": "PR",
                "user": {"login": "bob"},
                "created_at": "2026-02-08T10:00:00Z",
                "head": {"sha": "def456"},
                "labels": [],
                "html_url": "",
            },
        ]
        reviews_map: dict[int, list[dict]] = {
            1: [
                {
                    "user": {"login": "reviewer1"},
                    "state": "APPROVED",
                    "submitted_at": "2026-02-08T12:00:00Z",
                },
                {
                    "user": {"login": "reviewer2"},
                    "state": "CHANGES_REQUESTED",
                    "submitted_at": "2026-02-08T13:00:00Z",
                },
            ],
        }
        status_map: dict[str, dict] = {}

        infos = build_pr_infos(raw_prs, reviews_map, status_map, "org/repo")
        assert infos[0].review_status.summary == "changes_requested"

    def test_ci_status_mapping(self) -> None:
        raw_prs = [
            {
                "number": 1,
                "title": "PR",
                "user": {"login": "bob"},
                "created_at": "2026-02-08T10:00:00Z",
                "head": {"sha": "abc"},
                "labels": [],
                "html_url": "",
            },
        ]
        status_map: dict[str, dict] = {"abc": {"state": "failure"}}

        infos = build_pr_infos(raw_prs, {1: []}, status_map, "org/repo")
        assert infos[0].ci_status == "failure"


class TestRenderPrs:
    """Tests for the render_prs function."""

    def test_renders_table_headers(self) -> None:
        console, buf = _make_console()
        pr = PullRequestInfo(
            repo_name="org/repo",
            number=42,
            title="Add feature",
            author="alice",
            created_at=datetime.now(tz=UTC) - timedelta(days=2),
        )
        render_prs(console, [pr])
        output = buf.getvalue()
        assert "Repo" in output
        assert "PR" in output
        assert "Author" in output

    def test_stale_indicator(self) -> None:
        console, buf = _make_console()
        old_pr = PullRequestInfo(
            repo_name="org/repo",
            number=1,
            title="Old PR",
            author="alice",
            created_at=datetime.now(tz=UTC) - timedelta(days=14),
        )
        render_prs(console, [old_pr], stale_days=7)
        output = buf.getvalue()
        assert "2w" in output

    def test_empty_prs(self) -> None:
        console, buf = _make_console()
        render_prs(console, [])
        output = buf.getvalue()
        assert "No open pull requests" in output

    def test_author_filter(self) -> None:
        console, buf = _make_console()
        prs = [
            PullRequestInfo(
                repo_name="org/repo",
                number=1,
                title="Alice PR",
                author="alice",
                created_at=datetime.now(tz=UTC) - timedelta(days=1),
            ),
            PullRequestInfo(
                repo_name="org/repo",
                number=2,
                title="Bob PR",
                author="bob",
                created_at=datetime.now(tz=UTC) - timedelta(days=1),
            ),
        ]
        render_prs(console, prs, author_filter="alice")
        output = buf.getvalue()
        assert "Alice PR" in output
        assert "Bob PR" not in output

    def test_renders_pr_count(self) -> None:
        console, buf = _make_console()
        prs = [
            PullRequestInfo(
                repo_name="org/repo",
                number=i,
                title=f"PR {i}",
                author="alice",
                created_at=datetime.now(tz=UTC) - timedelta(days=1),
            )
            for i in range(3)
        ]
        render_prs(console, prs)
        output = buf.getvalue()
        assert "3" in output
