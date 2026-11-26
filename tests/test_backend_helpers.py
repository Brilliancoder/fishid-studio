import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from main import (  # noqa: E402
    CLASS_NAMES,
    DEFAULT_INPUT_SIZE,
    _display_name,
    _parse_input_size,
    _parse_num_classes,
    _softmax,
    get_effective_class_names,
)


@pytest.mark.parametrize(
    ("shape", "expected"),
    [
        ((None, 320, 320, 3), (320, 320)),
        ([(None, 224, 192, 3)], (224, 192)),
        ((None, -1, 320, 3), DEFAULT_INPUT_SIZE),
        ((None, "224", 320, 3), DEFAULT_INPUT_SIZE),
        ((None, 224), DEFAULT_INPUT_SIZE),
        (None, DEFAULT_INPUT_SIZE),
    ],
)
def test_parse_input_size(shape, expected):
    assert _parse_input_size(shape) == expected


@pytest.mark.parametrize(
    ("shape", "expected"),
    [
        ((None, 10), 10),
        ([(None, 12)], 12),
        ((None, 0), None),
        ((None, "12"), None),
        ((10,), None),
        ([], None),
    ],
)
def test_parse_num_classes(shape, expected):
    assert _parse_num_classes(shape) == expected


def test_effective_names_match_the_model_shape_without_changing_the_catalog():
    baseline = get_effective_class_names(None)
    assert len(baseline) == 10
    assert baseline == CLASS_NAMES
    assert get_effective_class_names({"num_classes": 5}) == baseline[:5]
    assert get_effective_class_names({"num_classes": 12}) == [
        *baseline, "Espécie 11", "Espécie 12",
    ]
    assert get_effective_class_names(None) == baseline


def test_display_name_includes_translation_when_available():
    assert _display_name("Coryphaena hippurus") == "Dourado-do-mar (Coryphaena hippurus)"
    assert _display_name("Unlisted species") == "Unlisted species"


def test_softmax_is_finite_normalized_and_invariant_to_large_common_offset():
    small = np.array([0.0, -1.0, -2.0])
    with np.errstate(over="raise", invalid="raise"):
        result = _softmax(small + 1000.0)
    expected = np.exp(small) / np.exp(small).sum()
    np.testing.assert_allclose(result, expected)
    assert result.sum() == pytest.approx(1.0)
