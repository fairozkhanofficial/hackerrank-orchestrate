"""Central configuration for the evidence review pipeline.

Every value the rest of the pipeline treats as a constant lives here. The
allowed output vocabularies are copied verbatim from problem_statement.md and
are the single source of truth for enum validation, so the model can never push
an unexpected value into output.csv.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


# Repository layout. config.py sits in code/, the dataset sits next to it.
CODE_DIR = Path(__file__).resolve().parent
REPO_ROOT = CODE_DIR.parent
DEFAULT_DATA_ROOT = REPO_ROOT / "dataset"
PROMPTS_DIR = CODE_DIR / "prompts"
CONFIG_DIR = REPO_ROOT / "config"
API_KEYS_FILE = CONFIG_DIR / "api_keys.txt"


# Allowed output vocabularies (authoritative: problem_statement.md).
CLAIM_OBJECTS = ("car", "laptop", "package")

CLAIM_STATUSES = ("supported", "contradicted", "not_enough_information")

ISSUE_TYPES = (
    "dent", "scratch", "crack", "glass_shatter", "broken_part", "missing_part",
    "torn_packaging", "crushed_packaging", "water_damage", "stain", "none",
    "unknown",
)

OBJECT_PARTS = {
    "car": (
        "front_bumper", "rear_bumper", "door", "hood", "windshield",
        "side_mirror", "headlight", "taillight", "fender", "quarter_panel",
        "body", "unknown",
    ),
    "laptop": (
        "screen", "keyboard", "trackpad", "hinge", "lid", "corner", "port",
        "base", "body", "unknown",
    ),
    "package": (
        "box", "package_corner", "package_side", "seal", "label", "contents",
        "item", "unknown",
    ),
}

RISK_FLAGS = (
    "none", "blurry_image", "cropped_or_obstructed", "low_light_or_glare",
    "wrong_angle", "wrong_object", "wrong_object_part", "damage_not_visible",
    "claim_mismatch", "possible_manipulation", "non_original_image",
    "text_instruction_present", "user_history_risk", "manual_review_required",
)

SEVERITIES = ("none", "low", "medium", "high", "unknown")

INPUT_COLUMNS = ("user_id", "image_paths", "user_claim", "claim_object")

OUTPUT_COLUMNS = (
    "user_id", "image_paths", "user_claim", "claim_object",
    "evidence_standard_met", "evidence_standard_met_reason", "risk_flags",
    "issue_type", "object_part", "claim_status", "claim_status_justification",
    "supporting_image_ids", "valid_image", "severity",
)


# Model configuration. The first implementation runs Gemini 2.5 Flash for both
# the vision and decision calls; the registry can still fall back to the mock
# backend when no API key is present.
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_API_VERSION = "v1beta"
# Gemini 2.5 Flash exposes an internal "thinking" budget. Disable it for cheap,
# fast, deterministic structured output.
GEMINI_THINKING_BUDGET = 0
VISION_PROVIDER = os.environ.get("VISION_PROVIDER", "gemini")
DECISION_PROVIDER = os.environ.get("DECISION_PROVIDER", "gemini")

VISION_TEMPERATURE = 0.0
DECISION_TEMPERATURE = 0.0
MAX_OUTPUT_TOKENS = 2048


# Imaging. Large submissions reach ~47 megapixels, so the longest edge is capped
# before encoding to keep image-token cost and upload size under control.
IMAGE_MAX_EDGE = 1280
IMAGE_JPEG_QUALITY = 85


# Retry and throttle defaults. REQUESTS_PER_MINUTE keeps the run under the
# Gemini free-tier request rate by default.
MAX_RETRIES = 5
BACKOFF_BASE_SECONDS = 2.0
# Conservative spacing to stay under the free-tier per-minute request window.
REQUESTS_PER_MINUTE = 6
# Cap on how long to honour a server-provided retry delay, in seconds.
MAX_RETRY_DELAY_SECONDS = 65


# Pricing assumptions in USD per one million tokens. These are approximate
# published rates used only for the cost estimate in evaluation_report.md.
PRICING = {
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
}
# Gemini bills images as input tokens. One tile is about 258 tokens; this is the
# per-image fallback used when the API does not return an exact image-token count.
IMAGE_TOKENS_ESTIMATE = 258


@dataclass
class Settings:
    data_root: Path
    images_root: Path
    claims_csv: Path
    sample_csv: Path
    history_csv: Path
    requirements_csv: Path
    output_csv: Path
    cache_dir: Path
    logs_dir: Path
    results_dir: Path
    vision_provider: str = VISION_PROVIDER
    decision_provider: str = DECISION_PROVIDER

    @property
    def gemini_api_key(self):
        return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def _load_dotenv() -> None:
    """Populate os.environ from the first .env files found, without overriding
    values already set in the real environment. Keys are never logged.

    Also accepts a .env.txt name, which is what Windows produces when file
    extensions are hidden and a user saves a file called ".env".
    """
    names = (".env", ".env.txt", ".env.local")
    candidates = [base / name
                  for base in (REPO_ROOT, CODE_DIR, Path.cwd())
                  for name in names]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        for raw in candidate.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def load_settings(data_root=None, output_csv=None) -> "Settings":
    """Resolve dataset paths and create the cache and log directories.

    data_root precedence: explicit argument, then the DATA_ROOT env var, then the
    dataset folder next to this repository.
    """
    _load_dotenv()
    root = Path(data_root) if data_root else Path(os.environ.get("DATA_ROOT", DEFAULT_DATA_ROOT))
    root = root.resolve()
    out = Path(output_csv).resolve() if output_csv else (REPO_ROOT / "output.csv")
    settings = Settings(
        data_root=root,
        images_root=root / "images",
        claims_csv=root / "claims.csv",
        sample_csv=root / "sample_claims.csv",
        history_csv=root / "user_history.csv",
        requirements_csv=root / "evidence_requirements.csv",
        output_csv=out,
        cache_dir=CODE_DIR / "cache",
        logs_dir=CODE_DIR / "logs",
        results_dir=CODE_DIR / "results",
    )
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    settings.results_dir.mkdir(parents=True, exist_ok=True)
    return settings


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def load_api_keys() -> list:
    """All Gemini API keys, from config/api_keys.txt plus any key in the env.

    The file holds one key per line; blank lines and lines starting with '#' are
    ignored. The number of keys is unbounded and needs no code change. Keys are
    de-duplicated, order preserved, and never logged.
    """
    _load_dotenv()
    keys = []
    if API_KEYS_FILE.is_file():
        for raw in API_KEYS_FILE.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#"):
                keys.append(line)
    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        value = os.environ.get(env_name)
        if value:
            keys.append(value)
    ordered = []
    for key in keys:
        if key not in ordered:
            ordered.append(key)
    return ordered
