"""Tests for the DORA-style stats renderer module."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import StringIO

from rich.console import Console

from giteagle.cli.stats_renderer import (
    PRMetrics,
    RepoStats,
    build_pr_metrics,
    compute_repo_stats,
    compute_trend,
    format_duration,
    median_timedelta,
    render_stats,
)


def _make_console() -> tuple[Console, StringIO]:
    """Create a Console that writes to a StringIO buffer."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=False, no_color=True, width=120)
    return console, buf


class TestMedianTimedelta:
    """Tests for the median_timedelta function."""

    def test_odd_count(self) -> None:
        deltas = [timedelta(hours=1), timedelta(hours=2), timedelta(hours=3)]
        assert median_timedelta(deltas) == timedelta(hours=2)

    def test_even_count(self) -> None:
        deltas = [
            timedelta(hours=1),
            timedelta(hours=2),
            timedelta(hours=3),
            timedelta(hours=4),
        ]
        assert median_timedelta(deltas) == timedelta(hours=2, minutes=30)

    def test_empty(self) -> None:
        assert median_timedelta([]) == timedelta(0)

    def test_single(self) -> None:
        assert median_timedelta([timedelta(hours=5)]) == timedelta(hours=5)


class TestFormatDuration:
    """Tests for the format_duration function."""

    def test_minutes(self) -> None:
        assert format_duration(timedelta(minutes=45)) == "45m"

    def test_hours(self) -> None:
        assert format_duration(timedelta(hours=3)) == "3h"

    def test_hours_and_minutes(self) -> None:
        assert format_duration(timedelta(hours=3, minutes=30)) == "3h 30m"

    def test_days_and_hours(self) -> None:
        assert format_duration(timedelta(days=2, hours=5)) == "2d 5h"

    def test_days_only(self) -> None:
        assert format_duration(timedelta(days=4)) == "4d"

    def test_weeks(self) -> None:
        assert format_duration(timedelta(days=14)) == "2w"

    def test_weeks_and_days(self) -> None:
        assert format_duration(timedelta(days=10)) == "1w 3d"

    def test_zero(self) -> None:
        assert format_duration(timedelta(0)) == "1m"


class TestBuildPrMetrics:
    """Tests for the build_pr_metrics function."""

    def test_basic_pr_metrics(self) -> None:
        raw_prs = [
            {
                "number": 42,
                "title": "Add feature",
                "created_at": "2026-02-01T10:00:00Z",
                "merged_at": "2026-02-03T10:00:00Z",
            },
        ]
        reviews_map: dict[int, list[dict]] = {42: []}

        metrics = build_pr_metrics(raw_prs, reviews_map, "org/repo")
        assert len(metrics) == 1
        assert metrics[0].time_to_merge == timedelta(days=2)
        assert metrics[0].time_to_first_review is None

    def test_first_review_detection(self) -> None:
        raw_prs = [
            {
                "number": 1,
                "title": "PR",
                "created_at": "2026-02-01T10:00:00Z",
                "merged_at": "2026-02-03T10:00:00Z",
            },
        ]
        reviews_map: dict[int, list[dict]] = {
            1: [
                {
                    "user": {"login": "r1"},
                    "state": "COMMENTED",
                    "submitted_at": "2026-02-01T11:00:00Z",
                },
                {
                    "user": {"login": "r2"},
                    "state": "APPROVED",
                    "submitted_at": "2026-02-01T14:00:00Z",
                },
            ],
        }

        metrics = build_pr_metrics(raw_prs, reviews_map, "org/repo")
        assert metrics[0].time_to_first_review == timedelta(hours=4)

    def test_skips_non_merged(self) -> None:
        raw_prs = [
            {
                "number": 1,
                "title": "Closed unmerged",
                "created_at": "2026-02-01T10:00:00Z",
                "merged_at": None,
            },
        ]
        metrics = build_pr_metrics(raw_prs, {}, "org/repo")
        assert len(metrics) == 0


class TestComputeRepoStats:
    """Tests for the compute_repo_stats function."""

    def test_throughput_calculation(self) -> None:
        now = datetime(2026, 2, 9, 12, 0, 0, tzinfo=UTC)
        metrics = [
            PRMetrics(
                repo_name="org/repo",
                number=i,
                title=f"PR {i}",
                created_at=now - timedelta(days=10),
                merged_at=now - timedelta(days=5),
                first_review_at=None,
                time_to_merge=timedelta(days=5),
                time_to_first_review=None,
            )
            for i in range(4)
        ]
        stats = compute_repo_stats(metrics, 5, "org/repo", window_days=14)
        assert stats.throughput_per_week == 4 / 2  # 4 PRs in 2 weeks
        assert stats.merged_count == 4

    def test_merge_rate(self) -> None:
        now = datetime(2026, 2, 9, 12, 0, 0, tzinfo=UTC)
        metrics = [
            PRMetrics(
                repo_name="org/repo",
                number=i,
                title=f"PR {i}",
                created_at=now - timedelta(days=10),
                merged_at=now - timedelta(days=5),
                first_review_at=None,
                time_to_merge=timedelta(days=5),
                time_to_first_review=None,
            )
            for i in range(8)
        ]
        stats = compute_repo_stats(metrics, 10, "org/repo", window_days=30)
        assert stats.merge_rate == 0.8  # 8 merged out of 10 closed

    def test_zero_closed(self) -> None:
        stats = compute_repo_stats([], 0, "org/repo", window_days=30)
        assert stats.merge_rate == 0.0
        assert stats.merged_count == 0


class TestComputeTrend:
    """Tests for the compute_trend function."""

    def test_up_trend(self) -> None:
        assert compute_trend(5.0, 3.0) == "up"

    def test_down_trend(self) -> None:
        assert compute_trend(2.0, 5.0) == "down"

    def test_stable(self) -> None:
        assert compute_trend(5.0, 5.0) == "stable"

    def test_no_previous(self) -> None:
        assert compute_trend(5.0, 0.0) == "n/a"


class TestRenderStats:
    """Tests for the render_stats function."""

    def test_renders_table(self) -> None:
        console, buf = _make_console()
        stats = [
            RepoStats(
                repo_name="org/api",
                merged_count=10,
                closed_count=12,
                median_time_to_merge=timedelta(days=1, hours=4),
                median_time_to_first_review=timedelta(hours=2),
                merge_rate=0.83,
                throughput_per_week=2.5,
            ),
        ]
        render_stats(console, stats, [], window_days=30)
        output = buf.getvalue()
        assert "api" in output
        assert "10" in output
        assert "1d 4h" in output

    def test_renders_trend_indicators(self) -> None:
        console, buf = _make_console()
        current = [
            RepoStats(
                repo_name="org/api",
                merged_count=10,
                closed_count=12,
                median_time_to_merge=timedelta(days=1),
                median_time_to_first_review=None,
                merge_rate=0.83,
                throughput_per_week=5.0,
            ),
        ]
        previous = [
            RepoStats(
                repo_name="org/api",
                merged_count=3,
                closed_count=4,
                median_time_to_merge=timedelta(days=2),
                median_time_to_first_review=None,
                merge_rate=0.75,
                throughput_per_week=1.5,
            ),
        ]
        render_stats(console, current, previous, window_days=30)
        output = buf.getvalue()
        assert "up" in output

    def test_empty_data(self) -> None:
        console, buf = _make_console()
        render_stats(console, [], [], window_days=30)
        output = buf.getvalue()
        assert "No merged pull requests" in output

    def test_overall_row_with_multiple_repos(self) -> None:
        console, buf = _make_console()
        stats = [
            RepoStats(
                repo_name="org/api",
                merged_count=5,
                closed_count=6,
                median_time_to_merge=timedelta(days=1),
                median_time_to_first_review=timedelta(hours=2),
                merge_rate=0.83,
                throughput_per_week=1.25,
            ),
            RepoStats(
                repo_name="org/web",
                merged_count=8,
                closed_count=10,
                median_time_to_merge=timedelta(days=2),
                median_time_to_first_review=timedelta(hours=5),
                merge_rate=0.80,
                throughput_per_week=2.0,
            ),
        ]
        render_stats(console, stats, [], window_days=30)
        output = buf.getvalue()
        assert "Overall" in output
        assert "13" in output  # total merged
