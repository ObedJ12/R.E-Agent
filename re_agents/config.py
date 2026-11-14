"""Settings loaded from the environment (or a local .env file)."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for raw in env.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

RENTCAST_API_KEY = os.environ.get("RENTCAST_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("RE_AGENTS_MODEL", "claude-opus-5-5")
CACHE_DIR = Path(os.environ.get("RE_AGENTS_CACHE", ROOT / ".cache"))
CACHE_TTL_DAYS = int(os.environ.get("RE_AGENTS_CACHE_DAYS", "30"))


def has_anthropic_credentials() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
