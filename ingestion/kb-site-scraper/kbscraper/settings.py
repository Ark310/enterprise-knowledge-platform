"""Paths, site constants, product/space mapping and persisted user settings."""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

BASE_URL = "https://help.contoso.example"

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).resolve().parent.parent

STATE_DIR = APP_DIR / "state"
RUNS_DIR = STATE_DIR / "runs"
LOG_DIR = STATE_DIR / "logs"
SETTINGS_FILE = STATE_DIR / "settings.json"
SITEMAP_FILE = STATE_DIR / "sitemap.json"
DEFAULT_OUTPUT = APP_DIR / "library"

# Spaces that are not knowledge-base content (site theme / navigation layout).
DEFAULT_EXCLUDED_SPACES = ["rwlayoutkey"]

# product folder -> label, in display order
PRODUCTS: dict[str, str] = {
    "tradedesk": "TradeDesk KB",
    "web2": "Web 2.5 KB",
    "web4": "Web 4.0 KB",
    "api": "API KB",
    "saleshub": "SalesHub KB",
    "formflow": "FormFlow KB",
    "training_videos": "Training Videos",
    "other": "Other",
}

# space_key -> (product folder, space folder). Spaces not listed here (e.g. new
# spaces added to the site later) still get scraped, under other/<space name>.
SPACE_MAP: dict[str, tuple[str, str]] = {
    # TradeDesk KB
    "SA": ("tradedesk", "system_administration"),
    "parameters": ("tradedesk", "parameters"),
    "Finance": ("tradedesk", "finance"),
    "Dealing": ("tradedesk", "dealing"),
    "compliance": ("tradedesk", "compliance"),
    "Reports": ("tradedesk", "reports"),
    "DistributionLayer": ("tradedesk", "fix_distribution_layer"),
    "releasenotes": ("tradedesk", "release_notes"),
    # Web 2.5 KB
    "administration": ("web2", "administration"),
    "beneficiaries": ("web2", "beneficiaries"),
    "BookingDeals": ("web2", "booking_deals"),
    "dealinghistory": ("web2", "dealing_history"),
    "documents": ("web2", "documents"),
    "GettingStarted": ("web2", "getting_started"),
    "howto": ("web2", "how_to"),
    "MyAccount": ("web2", "my_account"),
    "payments": ("web2", "payments"),
    # Web 4.0 KB
    "AdministrationWeb4": ("web4", "administration"),
    "BookingDealsWeb4": ("web4", "booking_deals"),
    "DealingHistoryWeb4": ("web4", "dealing_history"),
    "MyAccountWeb4": ("web4", "my_account"),
    "PaymentsWeb4": ("web4", "payments"),
    "RecipientsWeb4": ("web4", "recipients"),
    "ReleaseNotesWeb4": ("web4", "release_notes"),
    # API KB
    "Functions": ("api", "functions"),
    "GS": ("api", "getting_started"),
    "API25ReleaseNotes": ("api", "api_25_release_notes"),
    "apireleasenotes": ("api", "release_notes"),
    "RestAPIReleaseNotes": ("api", "rest_api_release_notes"),
    # SalesHub KB
    "SHGettingStarted": ("saleshub", "getting_started"),
    "SHBeneficiaries": ("saleshub", "beneficiaries"),
    "SHAccounts": ("saleshub", "accounts"),
    "SHAdministration": ("saleshub", "administration"),
    "SHBookingDeals": ("saleshub", "booking_deals"),
    "SHDocuments": ("saleshub", "documents"),
    "SHPayments": ("saleshub", "payments"),
    "SHHowTo": ("saleshub", "how_to"),
    "SHDealingHistory": ("saleshub", "dealing_history"),
    "SHAPIReleaseNotes": ("saleshub", "sh_api_release_notes"),
    "SHReleaseNotes": ("saleshub", "web_release_notes"),
    # FormFlow KB
    "SFFormManagement": ("formflow", "form_management"),
    "SFHowTo": ("formflow", "how_to"),
    "SFOpenForms": ("formflow", "open_forms"),
    "SFUserAccessControl": ("formflow", "user_access_control"),
    "SFReleaseNotes": ("formflow", "release_notes"),
    "FBD": ("formflow", "form_builder_docs"),
    # Training videos
    "TrainingVideos": ("training_videos", "training_videos"),
    # Other
    "WebReleaseNotes": ("other", "web_release_notes"),
}


def space_location(space_key: str, space_name: str) -> tuple[str, str]:
    """(product folder, space folder) for a space, including unmapped new spaces."""
    if space_key in SPACE_MAP:
        return SPACE_MAP[space_key]
    folder = re.sub(r"[^a-z0-9]+", "_", f"{space_name} {space_key}".lower()).strip("_")
    return "other", folder or space_key.lower()


@dataclass
class Settings:
    output_dir: str = str(DEFAULT_OUTPUT)
    workers: int = 4
    screenshots: bool = True
    headless: bool = True
    excluded_spaces: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDED_SPACES))
    # Per-article ceiling; generous because some articles carry large MP4 videos.
    article_timeout_s: int = 900
    max_attempts: int = 3

    @classmethod
    def load(cls) -> "Settings":
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
            s = cls(**known)
        except FileNotFoundError:
            s = cls()
        except (ValueError, TypeError):
            s = cls()
        s.workers = max(1, min(10, int(s.workers)))
        return s

    def save(self) -> None:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = SETTINGS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        tmp.replace(SETTINGS_FILE)

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir)
