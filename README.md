# Giteagle

**Get a bird's eye view of your repositories.**

[![Tests](https://github.com/pletisan/giteagle/actions/workflows/test.yml/badge.svg)](https://github.com/pletisan/giteagle/actions/workflows/test.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Giteagle helps engineering teams track activities across multiple repositories. When your project spans dozens of repos with contributions from multiple teams, staying on top of what's happening becomes challenging. Giteagle aggregates commits, pull requests, and issues into a unified view.

## Why Giteagle?

Modern software development often involves **multi-repository architectures**:

| Scenario | Example Projects | Challenge |
|----------|------------------|-----------|
| **Microservices** | Uber, Netflix, Spotify | 100s of service repos, hard to track cross-service changes |
| **Platform ecosystems** | Kubernetes (70+ repos), HashiCorp (Terraform providers) | Core + plugins/providers across many repos |
| **Monorepo alternatives** | Google's approach before Piper | Related projects in separate repos need coordination |
| **Open source foundations** | Apache, CNCF, Linux Foundation | Governance across project portfolios |

### Real-World Examples

**Kubernetes Ecosystem** - The Kubernetes project spans 70+ repositories:
- `kubernetes/kubernetes` - Core
- `kubernetes/dashboard` - Web UI
- `kubernetes/ingress-nginx` - Ingress controller
- `kubernetes/client-go` - Go client library
- ...and many more

**HashiCorp Terraform** - Terraform's provider ecosystem:
- `hashicorp/terraform` - Core
- `hashicorp/terraform-provider-aws` - AWS provider
- `hashicorp/terraform-provider-google` - GCP provider
- Hundreds of community providers

**Your Company** - Typical enterprise setup:
- `company/api-gateway`
- `company/user-service`
- `company/billing-service`
- `company/shared-libs`
- `company/infrastructure`

## Features

- **Unified Activity Feed** - See commits, PRs, and issues across all your repos in one view
- **Standup Reports** - "What did I do yesterday?" across all repos, weekend-aware
- **PR Dashboard** - Open PRs across repos with review status, CI status, and stale warnings
- **DORA Metrics** - Time-to-merge, time-to-first-review, merge rate, throughput with trends
- **Contributor Insights** - Track who's contributing where and how much
- **Timeline Analysis** - Visualize activity patterns over time
- **Cross-Repo Aggregation** - Combine statistics from multiple repositories
- **Beautiful CLI Output** - Rich terminal formatting with tables and charts
- **GitHub Integration** - Full support for GitHub API with rate limiting and pagination

## Quick Start

### Installation

```bash
# Install from local source (recommended for development)
git clone https://github.com/igormilovanovic/giteagle.git
cd giteagle
uv tool install .

# Or editable/development install (changes reflect immediately)
uv tool install -e .

# Or just run directly without installing
uv sync
uv run giteagle --help
```

### Configuration

Set your GitHub token for API access:

```bash
# Via environment variable (recommended)
export GITHUB_TOKEN=ghp_your_token_here

# Or create a config file
mkdir -p ~/.config/giteagle
cat > ~/.config/giteagle/config.yaml << EOF
github:
  token: ghp_your_token_here
default_platform: github
EOF
```

### Basic Usage

```bash
# List repositories for a user or organization
giteagle repos kubernetes --org

# View recent activity for a repository
giteagle activity kubernetes/kubernetes --days 7

# Get aggregated summary across multiple repos
giteagle summary kubernetes/kubernetes kubernetes/dashboard kubernetes/ingress-nginx

# View activity timeline
giteagle timeline hashicorp/terraform hashicorp/terraform-provider-aws --days 30

# Unified git log across multiple repos
giteagle log kubernetes/kubernetes kubernetes/dashboard --days 7

# Daily standup report (auto-detects your GitHub user)
giteagle standup mycompany/api mycompany/web --days 1

# Open PR dashboard with review and CI status
giteagle prs mycompany/api mycompany/web --stale 7

# DORA-style PR metrics with trend comparison
giteagle stats mycompany/api mycompany/web --days 30
```

## Usage Examples

### Example 1: Track a Microservices Project

You're leading a team with 5 microservices. Get a weekly summary:

```bash
# See what happened across all services this week
giteagle summary \
  mycompany/api-gateway \
  mycompany/user-service \
  mycompany/order-service \
  mycompany/payment-service \
  mycompany/notification-service \
  --days 7
```

Output:
```
╭─────────────────────────────────────╮
│        Summary (last 7 days)        │
├─────────────────────────────────────┤
│ Total Activities: 47                │
│ Repositories: 5                     │
│ Contributors: 8                     │
╰─────────────────────────────────────╯

By Activity Type
┌──────────────┬───────┐
│ Type         │ Count │
├──────────────┼───────┤
│ commit       │    32 │
│ pull_request │    12 │
│ issue        │     3 │
└──────────────┴───────┘

Top Contributors
┌──────────────┬────────────┐
│ Username     │ Activities │
├──────────────┼────────────┤
│ alice        │         15 │
│ bob          │         12 │
│ charlie      │          9 │
└──────────────┴────────────┘
```

### Example 2: Monitor Open Source Dependencies

Track activity in critical dependencies your project relies on:

```bash
# Monitor key libraries you depend on
giteagle summary \
  pallets/flask \
  psf/requests \
  encode/httpx \
  --days 14
```

### Example 3: Activity Timeline for Sprint Planning

Visualize development patterns to plan capacity:

```bash
giteagle timeline myorg/backend myorg/frontend --days 30 --granularity week
```

Output:
```
╭──────────────────────────────────────╮
│     Activity Timeline (weekly)       │
╰──────────────────────────────────────╯
2024-01-01: ████████████████████ 45
2024-01-08: ██████████████████████████ 58
2024-01-15: ████████████ 27
2024-01-22: ██████████████████████████████ 67
2024-01-29: ████████████████ 35
```

### Example 4: View Detailed Repository Activity

Drill into a specific repository:

```bash
giteagle activity facebook/react --days 3 --limit 20
```

Output:
```
╭────────────────────────────────────────────────────╮
│                 facebook/react                      │
│  A declarative, efficient, and flexible JavaScript │
│  library for building user interfaces.              │
╰────────────────────────────────────────────────────╯

Activity (last 3 days)
┌──────────────┬────────────────────────────────────┬───────────┬──────────────────┐
│ Type         │ Title                              │ Author    │ Date             │
├──────────────┼────────────────────────────────────┼───────────┼──────────────────┤
│ commit       │ Fix hydration mismatch warning     │ gaearon   │ 2024-01-15 14:32 │
│ pull_request │ Add new concurrent features        │ acdlite   │ 2024-01-15 11:20 │
│ commit       │ Update scheduler priority levels   │ sebmarkba │ 2024-01-14 16:45 │
└──────────────┴────────────────────────────────────┴───────────┴──────────────────┘
```

### Example 5: Unified Git Log Across Repos

Browse commits across your entire project like `tig`, but for multiple repos:

```bash
giteagle log mycompany/api-gateway mycompany/user-service mycompany/shared-libs --days 7
```

Output:

```text
 ● 2024-01-15  api-gateway  a1b2c3f  Fix rate limiter bug
 │             user-service d4e5f6a  Update auth middleware
 ● 2024-01-14  api-gateway  b7c8d9e  Add /users endpoint (merge)
 │             shared-libs  3d4e5f6  Bump version to 2.1
 ● 2024-01-13  user-service 7a8b9c0  Refactor session handling

 Total: 5 commits across 3 repositories
```

Filter by author:

```bash
giteagle log mycompany/api-gateway mycompany/user-service --author alice --days 14
```

### Example 6: Daily Standup Report

Generate a standup-ready summary of what you (or your team) did since yesterday. Weekend-aware — on Monday it looks back to Friday.

```bash
# Auto-detects your GitHub user from your token
giteagle standup mycompany/api mycompany/web mycompany/shared-libs

# Specific author, look back 2 days
giteagle standup mycompany/api mycompany/web --author alice --days 2
```

### Example 7: Cross-Repo PR Dashboard

See all open PRs across your repos with review status, CI status, and age. Stale PRs (older than `--stale` days) are highlighted.

```bash
giteagle prs mycompany/api mycompany/web mycompany/shared-libs --stale 7
```

### Example 8: DORA-Style PR Metrics

Track engineering velocity with time-to-merge, time-to-first-review, merge rate, and throughput. Includes trend comparison vs the previous period.

```bash
# Last 30 days with trend comparison vs prior 30 days
giteagle stats mycompany/api mycompany/web --days 30
```

## CLI Reference

### Commands

| Command | Description |
|---------|-------------|
| `giteagle repos <owner>` | List repositories for a user or organization |
| `giteagle activity <repo>` | Show recent activity for a repository |
| `giteagle summary <repos...>` | Aggregated summary across multiple repos |
| `giteagle timeline <repos...>` | Activity timeline visualization |
| `giteagle log <repos...>` | Unified git log across multiple repos |
| `giteagle standup <repos...>` | Daily standup report across repos |
| `giteagle prs <repos...>` | Cross-repo open PR dashboard |
| `giteagle stats <repos...>` | DORA-style PR metrics and trends |
| `giteagle config` | Show current configuration |

### Common Options

| Option | Description |
|--------|-------------|
| `--days N` | Number of days to look back (default varies by command) |
| `--limit N` | Maximum number of items to show (default: 50) |
| `--org` | Treat owner as organization (for `repos` command) |
| `--granularity` | Timeline granularity: day, week, month |
| `--author` | Filter by author username |
| `--stale N` | Days after which a PR is considered stale (for `prs`, default: 7) |

## Development

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Setup

```bash
# Clone the repository
git clone https://github.com/pletisan/giteagle.git
cd giteagle

# Install dependencies with uv
uv sync

# Run tests
uv run pytest

# Run linting
uv run ruff check src tests

# Run type checking
uv run mypy src
```

### Project Structure

```
giteagle/
├── src/giteagle/
│   ├── cli/              # CLI commands (Click + Rich)
│   ├── core/             # Core models and aggregation logic
│   ├── integrations/     # Platform API clients (GitHub, etc.)
│   └── config.py         # Configuration management
├── tests/
│   ├── unit/             # Unit tests
│   └── integration/      # Integration tests
├── pyproject.toml        # Project configuration
└── uv.lock               # Locked dependencies
```

## Roadmap

- [ ] GitLab integration
- [ ] Bitbucket integration
- [ ] Web dashboard
- [ ] Slack/Discord notifications
- [ ] Custom activity filters
- [ ] Export to CSV/JSON
- [ ] Team/group analytics

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`uv run pytest`)
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

Inspired by the challenges of managing multi-repository projects at scale. Built with:

- [Click](https://click.palletsprojects.com/) - CLI framework
- [Rich](https://rich.readthedocs.io/) - Terminal formatting
- [httpx](https://www.python-httpx.org/) - Async HTTP client
- [Pydantic](https://docs.pydantic.dev/) - Data validation
