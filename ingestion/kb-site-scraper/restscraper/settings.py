"""Paths, site constants and persisted user settings for the REST API scraper.

State lives in state/rest/ so it never mixes with the KB scraper's runs.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

BASE_URL = "https://apidocs.contoso.example"
START_SLUG = "getting-started-1"
# The "Try in API Explorer" page; opened by URL, never by clicking.
RUNNER_PREFIX = "/api-runner/contoso/contoso-rest-api-1/"

# (label in the snippet dropdown, file key, extension), in dropdown order.
LANGUAGES: list[tuple[str, str, str]] = [
    ("cURL", "curl", "sh"),
    ("Ruby", "ruby", "rb"),
    ("Python", "python", "py"),
    ("PHP", "php", "php"),
    ("Java", "java", "java"),
    ("Node.js", "nodejs", "js"),
    ("Go", "go", "go"),
    (".NET", "dotnet", "cs"),
]

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).resolve().parent.parent

STATE_DIR = APP_DIR / "state" / "rest"
RUNS_DIR = STATE_DIR / "runs"
LOG_DIR = STATE_DIR / "logs"
SETTINGS_FILE = STATE_DIR / "settings.json"
SITEMAP_FILE = STATE_DIR / "sitemap.json"
DEFAULT_OUTPUT = APP_DIR / "REST API"


@dataclass
class Settings:
    output_dir: str = str(DEFAULT_OUTPUT)
    workers: int = 3
    screenshots: bool = True
    headless: bool = True
    page_timeout_s: int = 300
    max_attempts: int = 3
    # Shared gap between page loads across all workers; the site rate-limits by IP.
    min_interval_s: float = 2.0
    # How long a rate-limit block may last before the run pauses and asks for help.
    cooldown_max_min: int = 60

    @classmethod
    def load(cls) -> "Settings":
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            s = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except (FileNotFoundError, ValueError, TypeError):
            s = cls()
        s.workers = max(1, min(6, int(s.workers)))
        s.min_interval_s = max(0.5, float(s.min_interval_s))
        return s

    def save(self) -> None:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = SETTINGS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        tmp.replace(SETTINGS_FILE)

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir)
