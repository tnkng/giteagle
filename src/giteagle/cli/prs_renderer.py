"""PR dashboard renderer for cross-repo open PR overview."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from rich import box
from rich.console import Console
from rich.table import Table


@dataclass
class ReviewStatus:
    """Aggregated review status for a PR."""

    approved: int = 0
    changes_requested: int = 0
    pending: int = 0

    @property
    def summary(self) -> str:
        """Return the overall review state."""
        if self.changes_requested > 0:
            return "changes_requested"
        if self.approved > 0:
            return "approved"
        return "pending"


@dataclass
class PullRequestInfo:
    """Presentation model for an open pull request."""

    repo_name: str
    number: int
    title: str
    author: str
    created_at: datetime
    labels: list[str] = field(default_factory=list)
    head_sha: str = ""
    review_status: ReviewStatus = field(default_factory=ReviewStatus)
    ci_status: str = "unknown"
    url: str = ""


def age_display(created_at: datetime, *, now: datetime | None = None) -> str:
    """Format age as human-readable string like '3d', '2h', '5w'."""
    now = now or datetime.now(tz=UTC)
    delta = now - created_at
    total_hours = int(delta.total_seconds() / 3600)

    if total_hours < 1:
        minutes = int(delta.total_seconds() / 60)
        return f"{max(minutes, 1)}m"
    if total_hours < 24:
        return f"{total_hours}h"
    days = delta.days
    if days < 7:
        return f"{days}d"
    weeks = days // 7
    return f"{weeks}w"


def _build_review_status(reviews: list[dict]) -> ReviewStatus:
    """Build ReviewStatus from raw GitHub review dicts."""
    status = ReviewStatus()
    # Track latest review state per reviewer
    reviewer_states: dict[str, str] = {}
    for review in sorted(reviews, key=lambda r: r.get("submitted_at", "")):
        reviewer = review.get("user", {}).get("login", "")
        state = review.get("state", "")
        if state in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            reviewer_states[reviewer] = state

    for state in reviewer_states.values():
        if state == "APPROVED":
            status.approved += 1
        elif state == "CHANGES_REQUESTED":
            status.changes_requested += 1

    if not reviewer_states:
        status.pending = 1

    return status


def build_pr_infos(
    raw_prs: list[dict],
    reviews_map: dict[int, list[dict]],
    status_map: dict[str, dict],
    repo_name: str,
) -> list[PullRequestInfo]:
    """Convert raw API data into PullRequestInfo objects."""
    infos: list[PullRequestInfo] = []
    for pr in raw_prs:
        created_at = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))
        head_sha = pr.get("head", {}).get("sha", "")
        labels = [label["name"] for label in pr.get("labels", [])]

        reviews = reviews_map.get(pr["number"], [])
        review_status = _build_review_status(reviews)

        combined_status = status_map.get(head_sha, {})
        ci_status = combined_status.get("state", "unknown")

        infos.append(
            PullRequestInfo(
                repo_name=repo_name,
                number=pr["number"],
                title=pr.get("title", ""),
                author=pr.get("user", {}).get("login", "unknown"),
                created_at=created_at,
                labels=labels,
                head_sha=head_sha,
                review_status=review_status,
                ci_status=ci_status,
                url=pr.get("html_url", ""),
            )
        )
    return infos


def _review_indicator(status: ReviewStatus) -> str:
    """Return a styled review status string."""
    summary = status.summary
    if summary == "approved":
        return f"[green]approved ({status.approved})[/green]"
    if summary == "changes_requested":
        return f"[red]changes ({status.changes_requested})[/red]"
    return "[yellow]pending[/yellow]"


def _ci_indicator(ci_status: str) -> str:
    """Return a styled CI status string."""
    if ci_status == "success":
        return "[green]pass[/green]"
    if ci_status in ("failure", "error"):
        return "[red]fail[/red]"
    if ci_status == "pending":
        return "[yellow]pending[/yellow]"
    return "[dim]--[/dim]"


def render_prs(
    console: Console,
    pr_infos: list[PullRequestInfo],
    *,
    stale_days: int = 7,
    author_filter: str | None = None,
) -> None:
    """Render the PR dashboard to console as a Rich table."""
    if author_filter:
        pr_infos = [p for p in pr_infos if p.author == author_filter]

    if not pr_infos:
        console.print("[yellow]No open pull requests found.[/yellow]")
        return

    # Sort oldest first
    pr_infos.sort(key=lambda p: p.created_at)

    now = datetime.now(tz=UTC)
    stale_cutoff = now - timedelta(days=stale_days)

    table = Table(title=f"Open Pull Requests ({len(pr_infos)})", box=box.ROUNDED)
    table.add_column("Repo", style="cyan", no_wrap=True)
    table.add_column("PR", style="white")
    table.add_column("Author", style="green", no_wrap=True)
    table.add_column("Age", no_wrap=True)
    table.add_column("Reviews", no_wrap=True)
    table.add_column("CI", no_wrap=True)
    table.add_column("Labels", style="dim")

    for pr in pr_infos:
        age = age_display(pr.created_at, now=now)
        is_stale = pr.created_at < stale_cutoff
        age_styled = f"[red]{age}[/red]" if is_stale else age

        pr_title = pr.title[:50] + "..." if len(pr.title) > 50 else pr.title
        pr_display = f"#{pr.number} {pr_title}"

        labels = ", ".join(pr.labels[:3]) if pr.labels else ""

        table.add_row(
            pr.repo_name.split("/")[-1],
            pr_display,
            pr.author,
            age_styled,
            _review_indicator(pr.review_status),
            _ci_indicator(pr.ci_status),
            labels,
        )

    console.print(table)
