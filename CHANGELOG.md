# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security

- **CVE-2026-45409** (`idna` < 3.15) — Medium severity. Specially crafted inputs to `idna.encode()` could bypass the CVE-2024-3651 fix. Resolved by bumping `idna` 3.11 → 3.15 (#29).
- **PYSEC-2026-2132** (`click` < 8.3.3) — Resolved by bumping `click` 8.3.1 → 8.4.2, surfaced when pip-audit was introduced (#31).
- **CVE-2025-71176** (`pytest` < 9.0.3) — Medium severity. Vulnerable tmpdir handling. Resolved by bumping `pytest` to 9.0.3 (#28).
- **CVE-2026-4539** (`Pygments` < 2.20.0) — Low severity. ReDoS via inefficient regex for GUID matching. Resolved by bumping `Pygments` to 2.20.0 (#28).
- Fixed two silent exception swallows (B110) in `cli/main.py` — bare `except/pass` replaced with `logger.warning()` calls (#33).

### Added

- `pip-audit` CI job: scans the full dependency tree for known CVEs on every push and PR (#31).
- `bandit` CI job: static analysis of source code for common security issues on every push and PR (#33).
- `pip-audit>=2.0` and `bandit>=1.7` added to dev dependencies (#31, #33).
- `[tool.bandit]` configuration in `pyproject.toml` targeting `src/` at medium+ severity (#33).

## [0.1.0] - 2026-02-08

### Added

- Initial release with `log`, `standup`, `prs`, and `stats` commands.
- GitHub API integration via `httpx` with async pagination and rate limiting.
- Rich terminal output with tables, panels, and colour-coded activity feeds.
- Security hardening: HTTPS-only base URL validation, `0o600` config file permissions, input allowlist validation for owner/repo names.
