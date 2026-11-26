import importlib.util
from pathlib import Path

import numpy as np
import pytest


@pytest.fixture(scope="module")
def demo_predict():
    app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
    spec = importlib.util.spec_from_file_location("fishid_frontend_app", app_path)
    assert spec is not None and spec.loader is not None
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)
    return app._local_demo_predict


@pytest.fixture
def rgb_image():
    return np.arange(24 * 24 * 3, dtype=np.uint8).reshape(24, 24, 3)


def test_local_demo_prediction_is_deterministic(demo_predict, rgb_image):
    first = demo_predict(rgb_image)
    second = demo_predict(rgb_image.copy())

    assert first["scientific_name"] == second["scientific_name"]
    assert first["confidence"] == second["confidence"]


def test_local_demo_probability_distribution(demo_predict, rgb_image):
    result = demo_predict(rgb_image)
    probabilities = result["probabilities"]
    scores = [item["probability"] for item in probabilities]

    assert len(probabilities) == 10
    assert len({item["scientific"] for item in probabilities}) == 10
    assert all(0.0 <= score <= 1.0 for score in scores)
    assert scores == sorted(scores, reverse=True)
    assert sum(scores) == pytest.approx(1.0)
    assert result["scientific_name"] == probabilities[0]["scientific"]
    assert result["confidence"] == scores[0]


def test_local_demo_hint_promotes_the_requested_species(demo_predict, rgb_image):
    hint = "Xiphias gladius"

    assert demo_predict(rgb_image)["scientific_name"] != hint
    result = demo_predict(rgb_image, hint_species=hint)
    assert result["scientific_name"] == hint
    assert result["probabilities"][0]["scientific"] == hint
