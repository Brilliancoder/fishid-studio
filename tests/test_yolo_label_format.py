from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rastrear_peixes_auto import format_yolo_bbox_line  # noqa: E402


YOLO_LINE_REGEX = re.compile(r"^\d+ \d+\.\d{6} \d+\.\d{6} \d+\.\d{6} \d+\.\d{6}$")


@pytest.mark.parametrize(
    ("x1", "y1", "x2", "y2", "width", "height", "class_id", "expected"),
    [
        (100, 200, 300, 400, 1000, 800, 0, "0 0.200000 0.375000 0.200000 0.250000"),
        (50, 50, 150, 250, 500, 500, 0, "0 0.200000 0.300000 0.200000 0.400000"),
        (10, 20, 10, 20, 100, 100, 0, "0 0.105000 0.205000 0.010000 0.010000"),
    ],
    ids=["standard-box", "rectangular-box", "degenerate-single-pixel-box"],
)
def test_normal_in_frame_bounding_boxes(x1, y1, x2, y2, width, height, class_id, expected):
    result = format_yolo_bbox_line(x1, y1, x2, y2, width, height, class_id)
    assert result == expected
    assert YOLO_LINE_REGEX.match(result)


@pytest.mark.parametrize(
    ("x1", "y1", "x2", "y2", "width", "height", "class_id", "expected"),
    [
        (-200, 100, -50, 200, 500, 500, 0, "0 0.000000 0.300000 0.300000 0.200000"),
        (100, -300, 200, -100, 500, 500, 0, "0 0.300000 0.000000 0.200000 0.400000"),
        (-100, -100, -20, -20, 500, 500, 0, "0 0.000000 0.000000 0.160000 0.160000"),
    ],
    ids=["negative-center-x", "negative-center-y", "both-centers-negative"],
)
def test_negative_normalized_center_coordinates_are_clamped_to_zero(
    x1, y1, x2, y2, width, height, class_id, expected
):
    result = format_yolo_bbox_line(x1, y1, x2, y2, width, height, class_id)
    assert result == expected
    assert YOLO_LINE_REGEX.match(result)


@pytest.mark.parametrize(
    ("x1", "y1", "x2", "y2", "width", "height", "class_id", "expected"),
    [
        (550, 100, 650, 200, 500, 500, 0, "0 1.000000 0.300000 0.200000 0.200000"),
        (100, 550, 200, 650, 500, 500, 0, "0 0.300000 1.000000 0.200000 0.200000"),
        (600, 700, 800, 900, 500, 500, 0, "0 1.000000 1.000000 0.400000 0.400000"),
    ],
    ids=["center-x-exceeds-one", "center-y-exceeds-one", "both-centers-exceed-one"],
)
def test_normalized_center_coordinates_exceeding_one_are_clamped_to_one(
    x1, y1, x2, y2, width, height, class_id, expected
):
    result = format_yolo_bbox_line(x1, y1, x2, y2, width, height, class_id)
    assert result == expected
    assert YOLO_LINE_REGEX.match(result)


@pytest.mark.parametrize(
    ("x1", "y1", "x2", "y2", "width", "height", "class_id", "expected"),
    [
        (0, 100, 1200, 300, 1000, 1000, 0, "0 0.600000 0.200000 1.000000 0.200000"),
        (100, 0, 300, 1500, 1000, 1000, 0, "0 0.200000 0.750000 0.200000 1.000000"),
        (-100, -100, 1500, 1500, 1000, 1000, 0, "0 0.700000 0.700000 1.000000 1.000000"),
    ],
    ids=["width-exceeds-frame", "height-exceeds-frame", "both-dimensions-exceed-frame"],
)
def test_bbox_dimensions_exceeding_frame_are_clamped_to_one(
    x1, y1, x2, y2, width, height, class_id, expected
):
    result = format_yolo_bbox_line(x1, y1, x2, y2, width, height, class_id)
    assert result == expected
    assert YOLO_LINE_REGEX.match(result)


@pytest.mark.parametrize(
    ("x1", "y1", "x2", "y2", "width", "height", "class_id", "expected"),
    [
        (0, 0, 1000, 1000, 1000, 1000, 0, "0 0.500000 0.500000 1.000000 1.000000"),
        (-500, -500, -100, -100, 1000, 1000, 0, "0 0.000000 0.000000 0.400000 0.400000"),
        (1500, 1500, 3000, 3000, 1000, 1000, 0, "0 1.000000 1.000000 1.000000 1.000000"),
    ],
    ids=["exact-full-frame-unit-dims", "extreme-negative-boundary", "extreme-positive-boundary"],
)
def test_boundary_values_zero_and_one(x1, y1, x2, y2, width, height, class_id, expected):
    result = format_yolo_bbox_line(x1, y1, x2, y2, width, height, class_id)
    assert result == expected
    assert YOLO_LINE_REGEX.match(result)


@pytest.mark.parametrize(
    ("class_id", "expected_prefix"),
    [
        (None, "0 "),
        (0, "0 "),
        (1, "1 "),
        (5, "5 "),
        (9, "9 "),
    ],
    ids=["default-omitted", "explicit-zero", "class-1", "class-5", "class-9"],
)
def test_default_and_custom_class_ids(class_id, expected_prefix):
    if class_id is None:
        result = format_yolo_bbox_line(100, 100, 200, 200, 1000, 1000)
    else:
        result = format_yolo_bbox_line(100, 100, 200, 200, 1000, 1000, class_id=class_id)
    assert result.startswith(expected_prefix)
    assert result == f"{expected_prefix}0.150000 0.150000 0.100000 0.100000"


def test_exact_six_decimal_formatting_with_non_terminating_fractions():
    # 2.5 / 7 = 0.357142857..., 4.0 / 9 = 0.444444444..., 3 / 7 = 0.428571428...
    result = format_yolo_bbox_line(1, 2, 4, 6, 7, 9, class_id=2)
    assert result == "2 0.357143 0.444444 0.428571 0.444444"
    parts = result.split()
    assert len(parts) == 5
    for part in parts[1:]:
        decimals = part.split(".")[1]
        assert len(decimals) == 6


def test_zero_or_negative_frame_dimension_safeguard():
    # width=0 and height=0 should default safely to max(dim, 1) and not raise ZeroDivisionError
    result = format_yolo_bbox_line(10, 20, 30, 40, width=0, height=-5, class_id=0)
    # bw=20, bh=20, raw_nx=(10+10)/1=20 -> clamped to 1.0, raw_nw=20/1 -> clamped to 1.0
    assert result == "0 1.000000 1.000000 1.000000 1.000000"
