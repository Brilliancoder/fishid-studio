import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from main import app  # noqa: E402


def catalog(**params):
    response = TestClient(app).get("/species", params=params)
    assert response.status_code == 200
    result = response.json()
    assert result["count"] == len(result["species"])
    return result["species"]


def test_full_catalog_includes_display_names():
    species = catalog()
    assert len(species) == 10
    assert species[0] == {
        "scientific": "Coryphaena hippurus",
        "common_pt": "Dourado-do-mar",
        "group": "Pelágico",
        "display_name": "Dourado-do-mar (Coryphaena hippurus)",
    }


def test_group_matches_the_whole_group_ignoring_case():
    tuna = catalog(group="aTuM")
    assert len(tuna) == 4
    assert all(item["group"] == "Atum" for item in tuna)
    assert catalog(group="Atu") == []


def test_search_matches_scientific_and_common_names():
    for query in ("HIPPUR", "DO-MAR"):
        assert [i["scientific"] for i in catalog(q=query)] == ["Coryphaena hippurus"]


def test_group_and_search_apply_together():
    assert len(catalog(group="Pelágico", q="hippurus")) == 1
    assert catalog(group="Atum", q="hippurus") == []
