"""Desktop app configuration."""

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit


_DEFAULT_API_URL = "https://outreach-api.lengrowth.com"
_ALLOWED_API_HOSTS = frozenset({"outreach-api.lengrowth.com", "localhost", "127.0.0.1", "::1"})


def validate_api_url(value: str) -> str:
    """Validate the daemon endpoint before it can become an SSRF primitive."""
    parsed = urlsplit(str(value).strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
        raise ValueError("daemon API URL must be an HTTP(S) URL without credentials")
    if host not in _ALLOWED_API_HOSTS:
        raise ValueError("daemon API host is not approved")
    if parsed.scheme != "https" and host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("non-TLS daemon API URLs are allowed only for loopback development")
    if parsed.query or parsed.fragment:
        raise ValueError("daemon API URL must not contain a query or fragment")
    return str(value).strip().rstrip("/")


@dataclass
class AppConfig:
    """Desktop application configuration."""

    api_url: str = _DEFAULT_API_URL
    autostart: bool = True

    def __post_init__(self) -> None:
        self.api_url = validate_api_url(self.api_url)

    @classmethod
    def _config_path(cls) -> Path:
        """Get platform-specific config file path."""
        if sys.platform == "darwin":
            base = Path.home() / "Library/Application Support/Lengrowth"
        elif sys.platform == "win32":
            base = Path.home() / "AppData/Local/Lengrowth"
        else:
            base = Path.home() / ".lengrowth"

        base.mkdir(parents=True, exist_ok=True)
        return base / "config.json"

    @classmethod
    def load(cls) -> "AppConfig":
        """Load config from disk, creating default if not found."""
        path = cls._config_path()
        if path.exists():
            try:
                data = json.loads(path.read_text())
                cfg = cls(**data)
                # Migrate any stale openoutreach.io URL to the correct domain
                if "openoutreach.io" in cfg.api_url or "linkedin-api." in cfg.api_url:
                    cfg.api_url = _DEFAULT_API_URL
                    cfg.save()
                return cfg
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()

    def save(self):
        """Save config to disk."""
        self.api_url = validate_api_url(self.api_url)
        path = self._config_path()
        path.write_text(json.dumps(asdict(self), indent=2))
