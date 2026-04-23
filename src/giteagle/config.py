"""Configuration management for Giteagle."""

import os
import stat
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class PlatformConfig(BaseModel):
    """Configuration for a single platform."""

    token: SecretStr | None = Field(default=None, description="API token")
    base_url: str | None = Field(default=None, description="Base API URL (for enterprise)")

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str | None) -> str | None:
        """Ensure base_url uses HTTPS to prevent credential leakage."""
        if v is None:
            return v
        parsed = urlparse(v)
        if parsed.scheme and parsed.scheme != "https":
            raise ValueError(f"base_url must use HTTPS, got: {parsed.scheme}")
        if not parsed.hostname:
            raise ValueError("base_url must include a valid hostname")
        return v


class GiteagleConfig(BaseModel):
    """Main configuration for Giteagle."""

    model_config = ConfigDict(extra="ignore")

    github: PlatformConfig = PlatformConfig()
    gitlab: PlatformConfig = PlatformConfig()
    bitbucket: PlatformConfig = PlatformConfig()
    default_platform: str = "github"
    cache_ttl: int = 300
    max_concurrent_requests: int = 10


def get_config_path() -> Path:
    """Get the path to the configuration file."""
    # Check environment variable first
    if env_path := os.environ.get("GITEAGLE_CONFIG"):
        return Path(env_path)

    # Check XDG config directory
    xdg_config = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    xdg_path = Path(xdg_config) / "giteagle" / "config.yaml"
    if xdg_path.exists():
        return xdg_path

    # Check home directory
    home_path = Path.home() / ".giteagle.yaml"
    if home_path.exists():
        return home_path

    # Default to XDG location
    return xdg_path


def load_config(path: Path | None = None) -> GiteagleConfig:
    """Load configuration from file and environment variables."""
    config_path = path or get_config_path()
    config_data: dict[str, Any] = {}

    # Load from file if exists
    if config_path.exists():
        with open(config_path) as f:
            config_data = yaml.safe_load(f) or {}

    # Override with environment variables
    if github_token := os.environ.get("GITHUB_TOKEN"):
        if "github" not in config_data:
            config_data["github"] = {}
        config_data["github"]["token"] = github_token

    if gitlab_token := os.environ.get("GITLAB_TOKEN"):
        if "gitlab" not in config_data:
            config_data["gitlab"] = {}
        config_data["gitlab"]["token"] = gitlab_token

    if bitbucket_token := os.environ.get("BITBUCKET_TOKEN"):
        if "bitbucket" not in config_data:
            config_data["bitbucket"] = {}
        config_data["bitbucket"]["token"] = bitbucket_token

    return GiteagleConfig(**config_data)


def save_config(config: GiteagleConfig, path: Path | None = None) -> None:
    """Save configuration to file."""
    config_path = path or get_config_path()

    # Create directory if needed
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dict, handling SecretStr
    data = config.model_dump()
    for platform in ["github", "gitlab", "bitbucket"]:
        if data[platform]["token"]:
            data[platform]["token"] = data[platform]["token"].get_secret_value()

    with open(config_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False)

    # Restrict file permissions to owner-only (0o600) since it contains tokens
    config_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
