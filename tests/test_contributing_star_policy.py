"""Guards the Star-First Review Priority policy across the contribution docs.

The Star-First Review Priority policy is spelled out in three independently
edited files: ``CONTRIBUTING.md``, ``.github/PULL_REQUEST_TEMPLATE.md`` and
``.github/ISSUE_TEMPLATE/config.yml``. A copy edit to any one of them can drop
the policy section or the sponsorship link without any test noticing, leaving
the contribution docs inconsistent with each other.

Each file carries the policy in its own idiom: the two Markdown files have a
"Star-First Review Priority" section heading, while ``config.yml`` expresses it
as the "Star FishID Studio on GitHub" contact link. All three must also keep
the GitHub Sponsors URL.

Only the standard library and pytest are used on purpose: the CI pytest step
installs just the packages listed in ``.github/workflows/ci.yml``.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"
PR_TEMPLATE = REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
ISSUE_CONFIG = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml"

SPONSORS_URL = "https://github.com/sponsors/viniciusscience"

# Marker each file must carry for the Star-First Review Priority policy.
STAR_POLICY_MARKERS = (
    (CONTRIBUTING, "Star-First Review Priority"),
    (PR_TEMPLATE, "Star-First Review Priority"),
    (ISSUE_CONFIG, "Star FishID Studio"),
)


def _read(path):
    assert path.is_file(), f"{path.relative_to(REPO_ROOT)} is missing"
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("path,marker", STAR_POLICY_MARKERS, ids=lambda v: getattr(v, "name", v))
def test_file_keeps_star_policy_marker(path, marker):
    text = _read(path)
    assert marker in text, (
        f"{path.relative_to(REPO_ROOT)} no longer carries the Star-First Review "
        f"Priority policy (expected to find {marker!r})"
    )


@pytest.mark.parametrize("path", [p for p, _ in STAR_POLICY_MARKERS], ids=lambda p: p.name)
def test_file_keeps_sponsors_link(path):
    text = _read(path)
    assert SPONSORS_URL in text, (
        f"{path.relative_to(REPO_ROOT)} no longer links {SPONSORS_URL}"
    )


def test_contribution_docs_agree_on_the_policy():
    """The three files must not drift apart on the star policy wording."""
    for path, marker in STAR_POLICY_MARKERS:
        text = _read(path)
        assert re.search(r"Star", text), (
            f"{path.relative_to(REPO_ROOT)} lost every star-priority mention"
        )
        assert marker in text
