# CLAUDE.md - Project Rules

## Project

- **Repo**: `igormilovanovic/giteagle`
- **Default branch**: `master`
- **Language**: Python (3.10+)
- **Package manager**: `uv`

## GitHub Workflow Rules

All work MUST follow the GitHub issue/PR workflow. Never push directly to `master`.

### 1. Issues First

- Before starting any non-trivial work, create a GitHub issue using `gh issue create`.
- Assign yourself to the issue.
- Use descriptive titles and label issues appropriately (`bug`, `enhancement`, `docs`, etc.).
- Reference related issues when applicable.

### 2. Branch Naming

- Always create a feature branch from `master` before making changes.
- Use the convention: `<type>/<short-description>` (e.g., `fix/typo-in-readme`, `feat/add-auth`, `chore/update-deps`).
- Branch names should reference the issue number when applicable: `fix/123-broken-parser`.

### 3. Pull Requests

- Push your branch and create a PR using `gh pr create`.
- Link the PR to its issue using `Closes #<issue-number>` in the PR body.
- PRs must target `master`.
- PR titles should be concise (<70 chars) and descriptive.
- PR body must include a `## Summary` and `## Test plan` section.
- Request reviews when appropriate using `gh pr edit --add-reviewer`.

### 4. Verify Code via GH Actions

After every push, you MUST verify the code is correct by monitoring CI:

- Run `gh pr checks --watch` to wait for all checks to complete.
- If any check fails, run `gh run view --log-failed` to inspect the failure logs.
- Diagnose and fix the failure locally, then push again.
- Repeat until all checks pass — do not merge with failing checks.
- Do NOT rely solely on local test runs. GH Actions is the source of truth for correctness (it tests across Python 3.10-3.13).

**Verification loop after pushing:**

```bash
gh pr checks --watch          # Wait for CI to finish
gh run list -b <branch> -L 1  # Find the latest run
gh run view <run-id> --log-failed  # Inspect failures if any
```

- All PRs must pass the full CI workflow (lint, type-check, tests on Python 3.10-3.13) before merging.
- Never bypass or skip checks. Never use `--no-verify`.

### 5. Merging

- Prefer squash merges for clean history.
- Delete the branch after merging using `gh pr merge --squash --delete-branch`.
- Never force-push to `master`.

### 6. Issue Management

- Close issues via PR merges (using `Closes #N`), not manually.
- Use `gh issue list` to review open issues before starting new work.
- Use `gh issue comment` to provide status updates on long-running work.

## Development Commands

```bash
uv sync --all-extras          # Install dependencies
uv run ruff check src tests   # Lint
uv run ruff format src tests  # Format
uv run mypy src --ignore-missing-imports  # Type check
uv run pytest --cov           # Test with coverage
```

## Code Style

- Follow existing patterns in the codebase.
- All code must pass `ruff check` and `ruff format --check`.
- All code must pass `mypy` type checking.

## Architecture

### Project Layout

- Use the `src/` layout. It prevents accidental imports and catches packaging bugs early.
- CLI layer (`cli/`) must be **thin** — parse args, delegate to `core/`, format output. Zero business logic in Click callbacks.
- Core layer (`core/`) contains business logic with no I/O and no framework imports.
- Integrations layer (`integrations/`) contains external API clients.
- One module, one responsibility. Split at ~300-400 lines.
- `__init__.py` re-exports the public API only. No logic.
- Private modules use leading underscore: `_internal.py`.
- Dependencies always point inward: CLI → core ← integrations. Core never imports from CLI or integrations directly.

### Dependency Inversion

- Use `typing.Protocol` for structural subtyping (duck-typed interfaces between layers).
- Wire concrete implementations at the **composition root** (CLI entry point).
- Domain models must never import framework code.
- Keep Protocols small — follow Interface Segregation.
- Use manual DI (constructor injection). Only introduce a DI framework when complexity demands it.

### Dataclasses vs Pydantic

- Use `dataclasses` for internal domain models, value objects, and DTOs carrying trusted data between internal layers.
- Use Pydantic at **system boundaries** — parsing API responses, reading config files, validating user input.
- Never use raw dicts for structured data that appears in more than one place.

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Packages | `lowercase` | `giteagle` |
| Modules | `snake_case` | `log_renderer.py` |
| Classes | `PascalCase` | `ActivityAggregator` |
| Exceptions | `PascalCase` + `Error` suffix | `AuthenticationError` |
| Functions/Methods | `snake_case` | `fetch_commits()` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRIES = 3` |
| Variables | `snake_case` | `commit_count` |
| Private | leading `_` | `_parse_header()` |
| Booleans | `is_`/`has_`/`can_` prefix | `is_valid`, `has_token` |
| Type Variables | `PascalCase`, short | `T`, `KeyT` |

- Line length: **88** characters (Ruff default).
- Use trailing commas in multi-line collections (cleaner diffs).
- Never use `l`, `O`, `I` as variable names.
- Import order: stdlib → third-party → local (enforced by Ruff `"I"` rule).
- Prefer absolute imports over relative imports.

## Type Hints & Static Analysis

- Add `from __future__ import annotations` at the top of every module for consistent lazy annotation evaluation.
- Type-hint **all** public functions, methods, and class attributes.
- Use modern syntax: `list[str]`, `dict[str, int]`, `str | None`.
- Always annotate return types including `-> None`.
- Never use `Any` as a shortcut. If truly needed, add a comment explaining why.
- Use keyword-only arguments for optional params: `def fetch(repo: str, *, limit: int = 100)`.
- Use `TypeAlias` for complex types.
- Prefer `typing.Protocol` over abstract base classes for structural subtyping.

## Dependency Management

- `pyproject.toml` is the **single source of truth** for all metadata and dependencies (PEP 621). No `setup.py`, no `requirements.txt`.
- Always commit `uv.lock` to version control.
- Declare loose version constraints in `[project.dependencies]` (e.g., `httpx>=0.25`). The lock file pins exact versions.
- Use `uv sync --frozen` in CI for reproducible builds.
- **Minimize dependencies.** Every dependency is a supply-chain risk and a maintenance burden. Evaluate before adding.
- Pin dev tools (ruff, mypy) in dev dependencies so all developers use the same version.
- Run `uv lock --upgrade` periodically and review changes. Never blindly upgrade.
- Audit dependencies with `pip-audit` in CI.

## Security

### Credentials

- **Never** hardcode secrets (API keys, tokens, passwords) in source code, config files, or commit history.
- Load secrets exclusively from environment variables or a secrets manager.
- Use `os.environ["KEY"]` (raises `KeyError`) for **required** secrets — fail loudly.
- Use Pydantic `SecretStr` to prevent accidental logging of tokens.
- Set `0o600` permissions on config files containing secrets.
- Add `.env` to `.gitignore`. Never commit it.
- Never log credentials, tokens, or passwords.

### Subprocess Safety

- **Never** use `shell=True` in `subprocess.run()` / `subprocess.Popen()`. It enables shell injection.
- Always pass commands as a list: `subprocess.run(["git", "log", "--oneline"], check=True)`.
- Validate input against allowlists. Use regex patterns like `^[a-zA-Z0-9._-]+$` for repo/owner names.
- Set `check=True` to ensure non-zero exit codes raise `CalledProcessError`.
- Set `timeout` on all subprocess calls to prevent hangs.

### Input Validation

- Validate **all** user-supplied input (CLI args, file paths, URLs) before use.
- Use allowlists, not denylists.
- For file paths: use `pathlib.Path.resolve()` + `is_relative_to(base)` to prevent path traversal.
- For URLs: validate scheme is `https://`.
- Use `yaml.safe_load()`, never `yaml.load()`.
- Never use `eval()`, `exec()`, or `pickle.loads()` with untrusted data.

### Dependency Security

- Audit dependencies with `pip-audit` in CI.
- Use Trusted Publishers on PyPI (OIDC, no stored API tokens).
- Use pre-commit hooks with `gitleaks` for secret detection.

## Testing

- Use **pytest** exclusively. No unittest-style classes.
- Follow the testing pyramid: many unit tests, fewer integration, minimal e2e.
- Test naming: `test_<function>_<scenario>_<expected>` (e.g., `test_parse_commit_with_empty_message_raises_value_error`).
- One logical assertion per test.
- Use fixtures for setup. Widely-shared fixtures in `conftest.py`, module-specific inline.
- Use `tmp_path` for temp files. Never write to the source tree.
- Mock external I/O in unit tests. Mock at the **boundary** (where the function is *used*, not where it is *defined*).
- Use `pytest.raises(SpecificError, match="pattern")` for error paths.
- Use `@pytest.mark.parametrize` for data-driven tests instead of repetitive test functions.
- Enforce coverage threshold: `--cov-fail-under=80` minimum, target 90%+.
- Mark slow tests with `@pytest.mark.slow`.
- Use `respx` for HTTP mocking with `httpx`.

## Error Handling

- Create a single base exception for the package. Users can `except GiteagleError` to catch all errors.
- Always inherit from `Exception`, never from `BaseException`.
- Catch the **narrowest** exception possible. Never bare `except:` or `except Exception:` in business logic.
- Keep `try` blocks minimal — only the specific line(s) that can raise.
- Use `raise ... from err` to chain exceptions and preserve tracebacks.
- In CLI entry points, catch the base exception and convert to user-friendly messages with appropriate exit codes.
- Never silently swallow exceptions (empty `except: pass` is a bug).
- Use `logging.exception()` inside `except` blocks (auto-captures traceback).
- Put custom exceptions in a dedicated `exceptions.py` module.
- Name exceptions with `Error` suffix (not `Exception`).

## Documentation

- Every public function, class, and module **must** have a docstring.
- Use Google-style docstrings.
- First line: imperative summary, <=79 chars, ends with period.
- Include `Args`, `Returns`, `Raises` sections for any non-trivial function.
- Class docstrings go after the `class` line, not after `__init__`.
- Module docstrings go at the very top of the file, before imports.
- Maintain a `CHANGELOG.md` following [Keep a Changelog](https://keepachangelog.com/) format.

## Packaging & Distribution

- Use **SemVer** (MAJOR.MINOR.PATCH). MAJOR = breaking, MINOR = features, PATCH = fixes.
- Use `[project.scripts]` for CLI entry points.
- Declare `requires-python` to enforce minimum Python version.
- Use Trusted Publishers on PyPI (OIDC, no API tokens stored in secrets).
- Never publish manually — use CI triggered by git tags.
- Test the build locally before publishing: `uv build`.

## CI/CD

- Lint + type-check in a **separate job** from tests (fail fast on style issues).
- Matrix test across **all** supported Python versions (3.10, 3.11, 3.12, 3.13).
- Enforce coverage thresholds with `--cov-fail-under`.
- Use `uv sync --frozen` in CI for reproducible builds.
- Add security scanning (bandit, pip-audit) as a CI job.
- Trigger releases from git tags, not manual dispatch.
- Never merge with failing checks. Protect `master` with required status checks.

## Git Conventions

### Conventional Commits

All commit messages must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <description>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`.

- Subject line: imperative mood, <=50 chars, no period at end.
- Body (optional): wrap at 72 chars, explain **why** not **what**.
- One logical change per commit. Don't mix refactoring with feature work.
- Reference issues in PR body with `Closes #N`, not in commit messages.

## Performance

- Lazy-load heavy imports (Rich, etc.) to keep CLI startup under 100ms.
- Use `functools.lru_cache` for pure functions with repeated inputs.
- Use `asyncio.gather()` for concurrent API calls.
- Use `asyncio.Semaphore` to bound concurrency and respect rate limits.
- Prefer generators (`yield`) over lists for large datasets.
- Profile before optimizing: `python -X importtime -m giteagle`.

## Configuration Management

Priority hierarchy (highest to lowest):

1. CLI arguments (explicit user intent)
2. Environment variables (prefixed: `GITEAGLE_*`)
3. Project config file (`.giteagle.yaml`)
4. User config file (`~/.config/giteagle/config.yaml`)
5. Hardcoded defaults

- Validate config at startup. Fail fast with clear error messages.
- Never scatter `os.getenv()` calls — centralize all config in one config class.
- Use `env_prefix` to namespace variables (`GITEAGLE_*`).
- Never require configuration for basic operations. Sensible defaults are mandatory.

## API Client Design

- Reuse a single long-lived `httpx.AsyncClient` with explicit connection limits and timeouts.
- **Always** set both connect and read timeouts. Never make a "naked" HTTP call.
- Implement exponential backoff with jitter for retries.
- Classify errors: 4xx (permanent, raise immediately) vs 429/5xx (transient, retry with backoff).
- Use `asyncio.Semaphore` for rate limiting.
- Use async generators for pagination.
- Proper cleanup with `async with` or `aclose()` in `finally`.

## Logging

- Use `logging.getLogger(__name__)` in every module.
- Never use `print()` for operational output.
- Use lazy formatting: `logger.info("Found %d items", count)` — not f-strings.
- Log levels: `DEBUG` = diagnostics, `INFO` = milestones, `WARNING` = unexpected but recoverable, `ERROR` = operation failed.
- Configure logging once at the CLI entry point, never in library modules.
- Default to `WARNING`. Use `--verbose` for `INFO`, `--debug` for `DEBUG`.
- Never log secrets, tokens, or PII.
- In library `__init__.py`: `logging.getLogger(__name__).addHandler(logging.NullHandler())`.

## Attribution

- NEVER add AI-generated signatures, badges, or footers to commits, PRs, issues, or code. This includes lines like "Generated with Claude Code", "Co-Authored-By: Claude", or any similar attribution. All contributions should appear as normal developer contributions.
