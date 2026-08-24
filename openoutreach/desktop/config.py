"""Desktop app configuration."""

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


_DEFAULT_API_URL = "https://outreach-api.lengrowth.com"


@dataclass
class AppConfig:
    """Desktop application configuration."""

    api_url: str = _DEFAULT_API_URL
    autostart: bool = True

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
        path = self._config_path()
        path.write_text(json.dumps(asdict(self), indent=2))
