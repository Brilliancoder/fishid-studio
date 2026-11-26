"""Guards the completeness of ``.env.example``.

``.env.example`` is the only discoverable list of the backend/frontend
configuration knobs: ``docker-compose.yml`` and the docs read from it, but
nothing fails when a key is quietly dropped from the template. These tests fail
loudly when one of the keys the services actually consume disappears.

Keys may be documented either as live assignments or as commented examples
(the photo-quality filters are commented by design), so both forms count.

Only the standard library and pytest are used on purpose: the CI pytest step
installs just the packages listed in ``.github/workflows/ci.yml``.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = REPO_ROOT / ".env.example"

REQUIRED_KEYS = (
    "MODEL_PATH",
    "STORAGE_BACKEND",
    "STORAGE_BUCKET",
    "LOCAL_STORAGE_DIR",
    "BACKEND_URL",
    "FISHID_MIN_IMAGE_DIM",
)


def _read(path):
    assert path.is_file(), f"{path.name} is missing at the repository root"
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("key", REQUIRED_KEYS)
def test_env_example_documents_key(key):
    text = _read(ENV_EXAMPLE)
    pattern = rf"^#?\s*{re.escape(key)}\s*="
    assert re.search(pattern, text, re.MULTILINE), (
        f".env.example no longer documents the '{key}' key "
        f"(expected a line like '{key}=...' or '# {key}=...')"
    )


def test_required_keys_appear_exactly_once():
    text = _read(ENV_EXAMPLE)
    for key in REQUIRED_KEYS:
        occurrences = re.findall(rf"^#?\s*{re.escape(key)}\s*=", text, re.MULTILINE)
        assert len(occurrences) == 1, (
            f".env.example must document '{key}' exactly once, found {len(occurrences)}"
        )
