"""Small JSON-backed GUI preferences without a GSettings schema."""

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    show_hubs: bool = False
    show_empty_ports: bool = False
    show_internal_devices: bool = True
    show_details: bool = False


def default_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "whatcable" / "settings.json"


def load(path: Path | None = None) -> Settings:
    try:
        values = json.loads((path or default_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return Settings()
    defaults = asdict(Settings())
    return Settings(**{name: bool(values.get(name, default)) for name, default in defaults.items()})


def save(settings: Settings, path: Path | None = None) -> None:
    target = path or default_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(settings), indent=2) + "\n", encoding="utf-8")
