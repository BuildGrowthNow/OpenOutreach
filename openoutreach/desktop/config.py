"""Desktop app configuration."""

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class AppConfig:
    """Desktop application configuration."""

    api_url: str = "https://linkedin-api.lengrowth.com"

    @classmethod
    def _config_path(cls) -> Path:
        """Get platform-specific config file path."""
        if sys.platform == "darwin":
            base = Path.home() / "Library/Application Support/OpenOutreach"
        elif sys.platform == "win32":
            base = Path.home() / "AppData/Local/OpenOutreach"
        else:
            base = Path.home() / ".openoutreach"

        base.mkdir(parents=True, exist_ok=True)
        return base / "config.json"

    @classmethod
    def load(cls) -> "AppConfig":
        """Load config from disk, creating default if not found."""
        path = cls._config_path()
        if path.exists():
            try:
                data = json.loads(path.read_text())
                return cls(**data)
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()

    def save(self):
        """Save config to disk."""
        path = self._config_path()
        path.write_text(json.dumps(asdict(self), indent=2))
