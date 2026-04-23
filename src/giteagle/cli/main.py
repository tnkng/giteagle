"""Main CLI entry point for Giteagle."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from datetime import datetime, timedelta, timezone
from typing import Any, TypeVar

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from giteagle import __version__
from giteagle.cli.log_renderer import assign_repo_colors, get_display_names, render_log
from giteagle.cli.prs_renderer import build_pr_infos, render_prs
from giteagle.cli.standup_renderer import build_standup_data, compute_standup_since, render_standup
from giteagle.cli.stats_renderer import build_pr_metrics, compute_repo_stats, render_stats
from giteagle.config import load_config
from giteagle.core import ActivityAggregator, ActivityType
from giteagle.integrations import GitHubClient

console = Console()

T = TypeVar("T")


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async function in the event loop."""
    return asyncio.run(coro)


def truncate_description(description: str | None, max_len: int = 50) -> str:
    """Truncate a description to a maximum length."""
    if not description:
        return ""
    if len(description) > max_len:
        return description[:max_len] + "..."
    return description


@click.group()
@click.version_option(version=__version__, prog_name="giteagle")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Giteagle - Get a bird's eye view of your repositories."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config()


@cli.command()
@click.argument("owner")
@click.option("--org", is_flag=True, help="Treat owner as an organization")
@click.pass_context
def repos(ctx: click.Context, owner: str, org: bool) -> None:
    """List repositories for a user or organization."""
    config = ctx.obj["config"]
    token = config.github.token.get_secret_value() if config.github.token else None

    async def fetch_repos() -> list:
        async with GitHubClient(token=token) as client:
            if org:
                return await client.list_repositories(org=owner)
            return await client.list_repositories(owner=owner)

    try:
        repositories = run_async(fetch_repos())
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from None

    table = Table(title=f"Repositories for {owner}", box=box.ROUNDED)
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="dim")
    table.add_column("Default Branch", style="green")
    table.add_column("Private", style="yellow")

    for repo in repositories:
        table.add_row(
            repo.name,
            truncate_description(repo.description),
            repo.default_branch,
            "Yes" if repo.is_private else "No",
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(repositories)} repositories[/dim]")


@cli.command()
@click.argument("repo")
@click.option("--days", default=7, help="Number of days to look back")
@click.option("--limit", default=50, help="Maximum number of activities to show")
@click.pass_context
def activity(ctx: click.Context, repo: str, days: int, limit: int) -> None:
    """Show recent activity for a repository.

    REPO should be in the format owner/name (e.g., octocat/hello-world)
    """
    config = ctx.obj["config"]
    token = config.github.token.get_secret_value() if config.github.token else None

    if "/" not in repo:
        console.print("[red]Error:[/red] Repository must be in format owner/name")
        raise SystemExit(1)

    owner, name = repo.split("/", 1)
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)

    async def fetch_activity() -> tuple:
        async with GitHubClient(token=token) as client:
            repository = await client.get_repository(owner, name)
            activities = await client.get_activities(repository, since=since, limit=limit)
            return repository, activities

    try:
        repository, activities = run_async(fetch_activity())
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from None

    console.print(
        Panel(
            f"[bold]{repository.full_name}[/bold]\n{repository.description or 'No description'}",
            title="Repository",
            box=box.ROUNDED,
        )
    )

    table = Table(title=f"Activity (last {days} days)", box=box.ROUNDED)
    table.add_column("Type", style="cyan", width=12)
    table.add_column("Title", style="white")
    table.add_column("Author", style="green")
    table.add_column("Date", style="yellow")

    type_colors = {
        ActivityType.COMMIT: "blue",
        ActivityType.PULL_REQUEST: "magenta",
        ActivityType.ISSUE: "yellow",
    }

    for act in activities:
        type_color = type_colors.get(act.type, "white")
        table.add_row(
            f"[{type_color}]{act.type.value}[/{type_color}]",
            act.title[:60] + "..." if len(act.title) > 60 else act.title,
            act.contributor.username,
            act.timestamp.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(activities)} activities[/dim]")


@cli.command()
@click.argument("repos", nargs=-1, required=True)
@click.option("--days", default=7, help="Number of days to look back")
@click.pass_context
def summary(ctx: click.Context, repos: tuple, days: int) -> None:
    """Show aggregated summary across multiple repositories.

    REPOS should be in the format owner/name (e.g., octocat/hello-world)
    """
    config = ctx.obj["config"]
    token = config.github.token.get_secret_value() if config.github.token else None
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)

    async def fetch_all() -> ActivityAggregator:
        async with GitHubClient(token=token) as client:
            aggregator = ActivityAggregator()

            for repo_name in repos:
                if "/" not in repo_name:
                    console.print(f"[yellow]Warning:[/yellow] Skipping invalid repo: {repo_name}")
                    continue

                owner, name = repo_name.split("/", 1)
                try:
                    repository = await client.get_repository(owner, name)
                    activities = await client.get_activities(repository, since=since, limit=100)
                    aggregator.add_activities(activities)
                    console.print(
                        f"[dim]Fetched {len(activities)} activities from {repo_name}[/dim]"
                    )
                except Exception as e:
                    console.print(f"[yellow]Warning:[/yellow] Failed to fetch {repo_name}: {e}")

            return aggregator

    try:
        aggregator = run_async(fetch_all())
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from None

    result = aggregator.aggregate(since=since)

    # Summary panel
    console.print(
        Panel(
            f"[bold]Total Activities:[/bold] {result.total_count}\n"
            f"[bold]Repositories:[/bold] {len(result.by_repository)}\n"
            f"[bold]Contributors:[/bold] {len(result.by_contributor)}",
            title=f"Summary (last {days} days)",
            box=box.ROUNDED,
        )
    )

    # Activity types breakdown
    if result.by_type:
        type_table = Table(title="By Activity Type", box=box.SIMPLE)
        type_table.add_column("Type", style="cyan")
        type_table.add_column("Count", style="white", justify="right")

        sorted_types = sorted(result.by_type.items(), key=lambda x: x[1], reverse=True)
        for activity_type, count in sorted_types:
            type_table.add_row(activity_type.value, str(count))

        console.print(type_table)

    # Top contributors
    top_contributors = aggregator.get_top_contributors(5)
    if top_contributors:
        contrib_table = Table(title="Top Contributors", box=box.SIMPLE)
        contrib_table.add_column("Username", style="green")
        contrib_table.add_column("Activities", style="white", justify="right")

        for username, count in top_contributors:
            contrib_table.add_row(username, str(count))

        console.print(contrib_table)

    # Repository breakdown
    if len(result.by_repository) > 1:
        repo_table = Table(title="By Repository", box=box.SIMPLE)
        repo_table.add_column("Repository", style="cyan")
        repo_table.add_column("Activities", style="white", justify="right")

        sorted_repos = sorted(result.by_repository.items(), key=lambda x: x[1], reverse=True)
        for repo_name, count in sorted_repos:
            repo_table.add_row(repo_name, str(count))

        console.print(repo_table)


@cli.command()
@click.argument("repos", nargs=-1, required=True)
@click.option("--days", default=30, help="Number of days to analyze")
@click.option("--granularity", type=click.Choice(["day", "week", "month"]), default="day")
@click.pass_context
def timeline(ctx: click.Context, repos: tuple, days: int, granularity: str) -> None:
    """Show activity timeline across repositories."""
    config = ctx.obj["config"]
    token = config.github.token.get_secret_value() if config.github.token else None
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)

    async def fetch_all() -> ActivityAggregator:
        async with GitHubClient(token=token) as client:
            aggregator = ActivityAggregator()

            for repo_name in repos:
                if "/" not in repo_name:
                    continue

                owner, name = repo_name.split("/", 1)
                try:
                    repository = await client.get_repository(owner, name)
                    activities = await client.get_activities(repository, since=since, limit=500)
                    aggregator.add_activities(activities)
                except Exception:
                    pass

            return aggregator

    try:
        aggregator = run_async(fetch_all())
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from None

    timeline_data = aggregator.get_activity_timeline(granularity=granularity, since=since)

    if not timeline_data:
        console.print("[yellow]No activity found in the specified period[/yellow]")
        return

    # Find max for scaling
    max_count = max(timeline_data.values())

    console.print(
        Panel(
            f"Activity Timeline ({granularity}ly)",
            box=box.ROUNDED,
        )
    )

    for date, count in timeline_data.items():
        bar_width = int((count / max_count) * 40) if max_count > 0 else 0
        bar = "[green]" + "█" * bar_width + "[/green]"
        console.print(f"{date}: {bar} {count}")


@cli.command()
@click.pass_context
def config(ctx: click.Context) -> None:
    """Show current configuration."""
    cfg = ctx.obj["config"]

    table = Table(title="Configuration", box=box.ROUNDED)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Default Platform", cfg.default_platform)
    table.add_row("Cache TTL", f"{cfg.cache_ttl}s")
    table.add_row("Max Concurrent Requests", str(cfg.max_concurrent_requests))
    table.add_row("GitHub Token", "***" if cfg.github.token else "[red]Not set[/red]")
    table.add_row("GitLab Token", "***" if cfg.gitlab.token else "[red]Not set[/red]")
    table.add_row("Bitbucket Token", "***" if cfg.bitbucket.token else "[red]Not set[/red]")

    console.print(table)
    console.print(
        "\n[dim]Set tokens via GITHUB_TOKEN, GITLAB_TOKEN, "
        "BITBUCKET_TOKEN environment variables[/dim]"
    )


@cli.command(name="log")
@click.argument("repos", nargs=-1, required=True)
@click.option("--days", default=7, help="Number of days to look back")
@click.option("--limit", default=100, help="Maximum number of commits per repo")
@click.option("--author", default=None, help="Filter by author username")
@click.pass_context
def log_cmd(ctx: click.Context, repos: tuple, days: int, limit: int, author: str | None) -> None:
    """Show unified git log across multiple repositories.

    REPOS should be in the format owner/name (e.g., octocat/hello-world)
    """
    config_obj = ctx.obj["config"]
    token = config_obj.github.token.get_secret_value() if config_obj.github.token else None
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)

    async def fetch_commits() -> list:
        async with GitHubClient(token=token) as client:
            all_commits: list = []

            for repo_name in repos:
                if "/" not in repo_name:
                    console.print(f"[yellow]Warning:[/yellow] Skipping invalid repo: {repo_name}")
                    continue

                owner, name = repo_name.split("/", 1)
                try:
                    repository = await client.get_repository(owner, name)
                    activities = await client.get_activities(repository, since=since, limit=limit)
                    commits = [a for a in activities if a.type == ActivityType.COMMIT]
                    all_commits.extend(commits)
                    console.print(f"[dim]Fetched {len(commits)} commits from {repo_name}[/dim]")
                except Exception as e:
                    console.print(f"[yellow]Warning:[/yellow] Failed to fetch {repo_name}: {e}")

            return all_commits

    try:
        commits = run_async(fetch_commits())
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from None

    if author:
        commits = [c for c in commits if c.contributor.username == author]

    commits.sort(key=lambda a: a.timestamp, reverse=True)

    repo_names = list({c.repository.full_name for c in commits})
    repo_colors = assign_repo_colors(repo_names)
    display_names = get_display_names(repo_names)

    render_log(console, commits, repo_colors, display_names)


@cli.command()
@click.argument("repos", nargs=-1, required=True)
@click.option("--days", default=1, help="Number of days to look back (auto-adjusts for weekends)")
@click.option("--author", default=None, help="Filter by author (default: authenticated user)")
@click.pass_context
def standup(ctx: click.Context, repos: tuple, days: int, author: str | None) -> None:
    """Show daily standup report across repositories.

    REPOS should be in the format owner/name (e.g., octocat/hello-world)
    """
    config_obj = ctx.obj["config"]
    token = config_obj.github.token.get_secret_value() if config_obj.github.token else None
    since = compute_standup_since(days)

    async def fetch_standup() -> tuple[list, str | None]:
        client = GitHubClient(token=token)
        try:
            resolved_author = author
            if resolved_author is None and token:
                try:
                    resolved_author = await client.get_authenticated_user()
                except Exception:
                    pass

            all_activities: list = []
            for repo_name in repos:
                if "/" not in repo_name:
                    console.print(f"[yellow]Warning:[/yellow] Skipping invalid repo: {repo_name}")
                    continue

                owner, name = repo_name.split("/", 1)
                try:
                    repository = await client.get_repository(owner, name)
                    activities = await client.get_activities(
                        repository,
                        since=since,
                        limit=200,
                    )
                    all_activities.extend(activities)
                    console.print(
                        f"[dim]Fetched {len(activities)} activities from {repo_name}[/dim]"
                    )
                except Exception as e:
                    console.print(f"[yellow]Warning:[/yellow] Failed to fetch {repo_name}: {e}")

            return all_activities, resolved_author
        finally:
            await client.close()

    try:
        activities, resolved_author = run_async(fetch_standup())
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from None

    if resolved_author:
        activities = [a for a in activities if a.contributor.username == resolved_author]

    standup_data = build_standup_data(activities, since)
    render_standup(console, standup_data, author=resolved_author, since=since)


@cli.command()
@click.argument("repos", nargs=-1, required=True)
@click.option("--author", default=None, help="Filter by PR author")
@click.option("--stale", default=7, type=int, help="Days after which a PR is considered stale")
@click.pass_context
def prs(ctx: click.Context, repos: tuple, author: str | None, stale: int) -> None:
    """Show open pull requests across repositories.

    REPOS should be in the format owner/name (e.g., octocat/hello-world)
    """
    config_obj = ctx.obj["config"]
    token = config_obj.github.token.get_secret_value() if config_obj.github.token else None

    async def fetch_prs() -> list:
        client = GitHubClient(token=token)
        try:
            all_pr_infos: list = []

            for repo_name in repos:
                if "/" not in repo_name:
                    console.print(f"[yellow]Warning:[/yellow] Skipping invalid repo: {repo_name}")
                    continue

                owner, name = repo_name.split("/", 1)
                try:
                    repository = await client.get_repository(owner, name)
                    raw_prs = await client.get_open_pull_requests(repository)
                    console.print(f"[dim]Fetched {len(raw_prs)} open PRs from {repo_name}[/dim]")

                    if not raw_prs:
                        continue

                    # Fetch reviews and statuses concurrently
                    review_tasks = [
                        client.get_pr_reviews(repository, pr["number"]) for pr in raw_prs
                    ]
                    status_tasks = [
                        client.get_commit_status(repository, pr.get("head", {}).get("sha", ""))
                        for pr in raw_prs
                        if pr.get("head", {}).get("sha")
                    ]

                    reviews_results = await asyncio.gather(*review_tasks, return_exceptions=True)
                    status_results = await asyncio.gather(*status_tasks, return_exceptions=True)

                    reviews_map: dict[int, list] = {}
                    for pr, result in zip(raw_prs, reviews_results, strict=True):
                        if isinstance(result, list):
                            reviews_map[pr["number"]] = result
                        else:
                            reviews_map[pr["number"]] = []

                    status_map: dict[str, dict] = {}
                    prs_with_sha = [pr for pr in raw_prs if pr.get("head", {}).get("sha")]
                    for pr, status_result in zip(prs_with_sha, status_results, strict=True):
                        sha = pr["head"]["sha"]
                        if isinstance(status_result, dict):
                            status_map[sha] = status_result
                        else:
                            status_map[sha] = {"state": "unknown"}

                    pr_infos = build_pr_infos(raw_prs, reviews_map, status_map, repo_name)
                    all_pr_infos.extend(pr_infos)

                except Exception as e:
                    console.print(f"[yellow]Warning:[/yellow] Failed to fetch {repo_name}: {e}")

            return all_pr_infos
        finally:
            await client.close()

    try:
        pr_infos = run_async(fetch_prs())
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from None

    render_prs(console, pr_infos, stale_days=stale, author_filter=author)


@cli.command()
@click.argument("repos", nargs=-1, required=True)
@click.option("--days", default=30, help="Time window in days for metrics")
@click.pass_context
def stats(ctx: click.Context, repos: tuple, days: int) -> None:
    """Show DORA-style PR metrics across repositories.

    REPOS should be in the format owner/name (e.g., octocat/hello-world)
    """
    config_obj = ctx.obj["config"]
    token = config_obj.github.token.get_secret_value() if config_obj.github.token else None
    now = datetime.now(tz=timezone.utc)
    current_since = now - timedelta(days=days)
    prev_since = current_since - timedelta(days=days)

    async def fetch_stats() -> tuple[list, list]:
        client = GitHubClient(token=token)
        try:
            current_repo_stats: list = []
            previous_repo_stats: list = []

            for repo_name in repos:
                if "/" not in repo_name:
                    console.print(f"[yellow]Warning:[/yellow] Skipping invalid repo: {repo_name}")
                    continue

                owner, name = repo_name.split("/", 1)
                try:
                    repository = await client.get_repository(owner, name)

                    # Fetch closed PRs covering both windows
                    closed_prs = await client.get_closed_pull_requests(
                        repository, since=prev_since, limit=200
                    )
                    console.print(
                        f"[dim]Fetched {len(closed_prs)} closed PRs from {repo_name}[/dim]"
                    )

                    # Split into current and previous windows
                    current_prs = [
                        pr
                        for pr in closed_prs
                        if pr.get("closed_at")
                        and datetime.fromisoformat(pr["closed_at"].replace("Z", "+00:00"))
                        >= current_since
                    ]
                    previous_prs = [
                        pr
                        for pr in closed_prs
                        if pr.get("closed_at")
                        and datetime.fromisoformat(pr["closed_at"].replace("Z", "+00:00"))
                        < current_since
                    ]

                    # Fetch reviews for merged PRs concurrently
                    merged_current = [pr for pr in current_prs if pr.get("merged_at")]
                    merged_previous = [pr for pr in previous_prs if pr.get("merged_at")]

                    all_merged = merged_current + merged_previous
                    review_tasks = [
                        client.get_pr_reviews(repository, pr["number"]) for pr in all_merged
                    ]
                    review_results = await asyncio.gather(*review_tasks, return_exceptions=True)

                    reviews_map: dict[int, list] = {}
                    for pr, result in zip(all_merged, review_results, strict=True):
                        if isinstance(result, list):
                            reviews_map[pr["number"]] = result
                        else:
                            reviews_map[pr["number"]] = []

                    # Build metrics for current and previous
                    current_metrics = build_pr_metrics(current_prs, reviews_map, repo_name)
                    previous_metrics = build_pr_metrics(previous_prs, reviews_map, repo_name)

                    current_repo_stats.append(
                        compute_repo_stats(
                            current_metrics,
                            len(current_prs),
                            repo_name,
                            window_days=days,
                        )
                    )
                    if previous_metrics:
                        previous_repo_stats.append(
                            compute_repo_stats(
                                previous_metrics,
                                len(previous_prs),
                                repo_name,
                                window_days=days,
                            )
                        )

                except Exception as e:
                    console.print(f"[yellow]Warning:[/yellow] Failed to fetch {repo_name}: {e}")

            return current_repo_stats, previous_repo_stats
        finally:
            await client.close()

    try:
        current_stats, previous_stats = run_async(fetch_stats())
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from None

    render_stats(console, current_stats, previous_stats, window_days=days)


if __name__ == "__main__":
    cli()
