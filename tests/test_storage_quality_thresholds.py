from pathlib import Path
import sys

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from storage import validate_image_quality


@pytest.fixture
def photo(monkeypatch):
    for suffix in ("MIN_IMAGE_DIM", "MIN_SHARPNESS", "MIN_BRIGHTNESS", "MAX_BRIGHTNESS", "MIN_CONTRAST"):
        monkeypatch.delenv("FISHID_" + suffix, raising=False)
    # A repeatable, sharp image at the default size; brightness 110, contrast 30.
    pixels = (np.indices((224, 224)).sum(axis=0) % 2 * 60 + 80).astype(np.uint8)
    return Image.fromarray(pixels).convert("RGB")


@pytest.mark.parametrize(("setting", "limit", "reason"), [
    ("MIN_IMAGE_DIM", "225", "225×225"),
    ("MIN_SHARPNESS", "60000", "borrada"),
    ("MIN_BRIGHTNESS", "111.5", "escura"),
    ("MAX_BRIGHTNESS", "109.5", "excesso de luz"),
    ("MIN_CONTRAST", "30.5", "sem contraste"),
])
def test_custom_threshold_rejects_otherwise_accepted_photo(photo, monkeypatch, setting, limit, reason):
    assert validate_image_quality(photo)[0]
    monkeypatch.setenv("FISHID_" + setting, limit)
    accepted, message, _ = validate_image_quality(photo)
    assert not accepted
    assert reason in message


def test_night_deck_photo_can_be_accepted_at_custom_boundary(photo, monkeypatch):
    night = photo.point(lambda pixel: (pixel - 80) // 2)
    assert not validate_image_quality(night)[0]
    monkeypatch.setenv("FISHID_MIN_BRIGHTNESS", "15")
    assert validate_image_quality(night)[0]
