"""Standup renderer for daily activity reports across repositories."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from rich.console import Console

from giteagle.core.models import Activity, ActivityType


@dataclass
class RepoStandup:
    """Aggregated standup data for a single repository."""

    repo_name: str
    commits: list[Activity] = field(default_factory=list)
    prs_opened: list[Activity] = field(default_factory=list)
    prs_merged: list[Activity] = field(default_factory=list)
    prs_closed: list[Activity] = field(default_factory=list)
    issues_opened: list[Activity] = field(default_factory=list)
    issues_closed: list[Activity] = field(default_factory=list)

    @property
    def total(self) -> int:
        """Return total number of activities."""
        return (
            len(self.commits)
            + len(self.prs_opened)
            + len(self.prs_merged)
            + len(self.prs_closed)
            + len(self.issues_opened)
            + len(self.issues_closed)
        )


def compute_standup_since(days: int, *, now: datetime | None = None) -> datetime:
    """Compute the 'since' datetime for standup.

    If days == 1 and today is Monday, look back to Friday (3 days).
    Otherwise, look back `days` calendar days.
    """
    now = now or datetime.now(tz=UTC)
    if days == 1 and now.weekday() == 0:  # Monday
        delta = timedelta(days=3)
    else:
        delta = timedelta(days=days)
    since = (now - delta).replace(hour=0, minute=0, second=0, microsecond=0)
    return since


def _parse_iso_datetime(value: str | None) -> datetime | None:
    """Parse an ISO datetime string from GitHub API."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError, AttributeError:
        return None


def build_standup_data(
    activities: list[Activity],
    since: datetime,
) -> list[RepoStandup]:
    """Group activities into per-repo standup summaries."""
    repos: dict[str, RepoStandup] = {}

    for activity in activities:
        repo_name = activity.repository.full_name
        if repo_name not in repos:
            repos[repo_name] = RepoStandup(repo_name=repo_name)
        standup = repos[repo_name]

        if activity.type == ActivityType.COMMIT:
            if activity.timestamp >= since:
                standup.commits.append(activity)

        elif activity.type == ActivityType.PULL_REQUEST:
            merged_at = _parse_iso_datetime(activity.metadata.get("merged_at"))
            closed_at = _parse_iso_datetime(activity.metadata.get("closed_at"))
            is_merged = activity.metadata.get("merged", False)

            if activity.timestamp >= since:
                standup.prs_opened.append(activity)
            if is_merged and merged_at and merged_at >= since:
                standup.prs_merged.append(activity)
            elif not is_merged and closed_at and closed_at >= since:
                standup.prs_closed.append(activity)

        elif activity.type == ActivityType.ISSUE:
            closed_at = _parse_iso_datetime(activity.metadata.get("closed_at"))

            if activity.timestamp >= since:
                standup.issues_opened.append(activity)
            if closed_at and closed_at >= since:
                standup.issues_closed.append(activity)

    # Filter out repos with no activity and sort by name
    result = [s for s in repos.values() if s.total > 0]
    result.sort(key=lambda s: s.repo_name)
    return result


def render_standup(
    console: Console,
    standup_data: list[RepoStandup],
    *,
    author: str | None = None,
    since: datetime,
) -> None:
    """Render the standup report to the console."""
    if not standup_data:
        label = f" for [bold]{author}[/bold]" if author else ""
        console.print(f"[yellow]No activity{label} since {since.strftime('%Y-%m-%d')}[/yellow]")
        return

    # Header
    day_name = since.strftime("%a")
    author_label = f" for [bold]{author}[/bold]" if author else ""
    console.print(
        f"[bold]Standup{author_label} since {since.strftime('%Y-%m-%d')} ({day_name})[/bold]"
    )
    console.print("[dim]" + "\u2500" * 50 + "[/dim]")

    total_count = 0
    for standup in standup_data:
        total_count += standup.total
        console.print(f"\n[bold cyan]{standup.repo_name}[/bold cyan] ({standup.total} activities)")

        if standup.commits:
            titles = ", ".join(a.title[:50] for a in standup.commits[:5])
            console.print(f"  [green]Commits ({len(standup.commits)}):[/green] {titles}")

        if standup.prs_opened:
            titles = ", ".join(
                f"#{a.metadata.get('number', '?')} {a.title[:40]}" for a in standup.prs_opened[:5]
            )
            console.print(f"  [magenta]PRs opened ({len(standup.prs_opened)}):[/magenta] {titles}")

        if standup.prs_merged:
            titles = ", ".join(
                f"#{a.metadata.get('number', '?')} {a.title[:40]}" for a in standup.prs_merged[:5]
            )
            console.print(f"  [blue]PRs merged ({len(standup.prs_merged)}):[/blue] {titles}")

        if standup.prs_closed:
            titles = ", ".join(
                f"#{a.metadata.get('number', '?')} {a.title[:40]}" for a in standup.prs_closed[:5]
            )
            console.print(f"  [dim]PRs closed ({len(standup.prs_closed)}):[/dim] {titles}")

        if standup.issues_opened:
            titles = ", ".join(
                f"#{a.metadata.get('number', '?')} {a.title[:40]}"
                for a in standup.issues_opened[:5]
            )
            console.print(
                f"  [yellow]Issues opened ({len(standup.issues_opened)}):[/yellow] {titles}"
            )

        if standup.issues_closed:
            titles = ", ".join(
                f"#{a.metadata.get('number', '?')} {a.title[:40]}"
                for a in standup.issues_closed[:5]
            )
            console.print(f"  [dim]Issues closed ({len(standup.issues_closed)}):[/dim] {titles}")

    repo_count = len(standup_data)
    console.print(f"\n[dim]Total: {total_count} activities across {repo_count} repositories[/dim]")
