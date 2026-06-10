import os
from pathlib import Path

import yaml

CONFIG_PATH = os.environ.get(
    "HARDWARE_CONFIG_PATH",
    os.environ.get(
        "PI_REMOTE_CONFIG",
        str(Path(__file__).resolve().parent.parent / "config.yaml"),
    ),
)

_config = None


def get_config() -> dict:
    global _config
    if _config is None:
        with open(CONFIG_PATH) as f:
            _config = yaml.safe_load(f)
    return _config


def pc() -> dict:
    return get_config()["pc"]


def repos() -> dict:
    """Return repos config (scan_dirs + max_depth)."""
    return get_config()["repos"]


def scan_dirs() -> list[str]:
    """Directories to scan for git repos."""
    return get_config()["repos"].get("scan_dirs", ["~/projects"])


def scan_max_depth() -> int:
    return get_config()["repos"].get("max_depth", 2)


def timeouts() -> dict:
    return get_config()["timeouts"]
