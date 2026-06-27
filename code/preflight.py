"""Startup validation: verify everything the run needs exists, and fail fast with
a clear diagnostic listing every problem at once.
"""

from __future__ import annotations

import config


def check_environment(settings, require_api_keys=True):
    """Return a list of human-readable problems (empty means ready)."""
    problems = []

    def need_file(path, label):
        if not path.is_file():
            problems.append(f"missing {label}: {path}")

    def need_dir(path, label):
        if not path.is_dir():
            problems.append(f"missing {label}: {path}")

    need_dir(settings.data_root, "dataset directory")
    need_file(settings.claims_csv, "claims.csv")
    need_file(settings.sample_csv, "sample_claims.csv")
    need_file(settings.history_csv, "user_history.csv")
    need_file(settings.requirements_csv, "evidence_requirements.csv")
    need_dir(settings.images_root, "images directory")

    if require_api_keys:
        if not config.API_KEYS_FILE.is_file():
            problems.append(
                f"missing api keys file: {config.API_KEYS_FILE} "
                "(one Gemini key per line; blank lines and # comments ignored)")
        elif not config.load_api_keys():
            problems.append(
                f"no usable keys in {config.API_KEYS_FILE} (file is empty or only comments)")

    return problems


def validate_or_exit(settings, require_api_keys=True):
    """Print problems and raise SystemExit(2) if anything is missing."""
    problems = check_environment(settings, require_api_keys=require_api_keys)
    if problems:
        print("Startup validation failed:")
        for problem in problems:
            print(f"  - {problem}")
        raise SystemExit(2)
    keys = config.load_api_keys() if require_api_keys else []
    detail = f"{len(keys)} api key(s)" if require_api_keys else "mock backend (no keys required)"
    print(f"Startup validation passed: dataset at {settings.data_root}, {detail}")
