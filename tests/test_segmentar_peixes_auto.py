import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from segmentar_peixes_auto import (  # noqa: E402
    _clamp_box_with_margin,
    _mask_to_clean_bbox,
    _resize_for_inference,
    _select_best_box,
)


# --- _clamp_box_with_margin ---------------------------------------------------

def test_clamp_box_adds_margin_inside_image():
    # 100x100 box, 10% margin -> 10px on each side
    assert _clamp_box_with_margin(100, 100, 200, 200, 640, 480, 0.1) == (90, 90, 210, 210)


def test_clamp_box_stays_inside_image_bounds():
    box = _clamp_box_with_margin(-20, -5, 700, 500, 640, 480, 0.2)
    assert box == (0, 0, 640, 480)


def test_clamp_box_degenerate_box_is_at_least_one_pixel():
    x1, y1, x2, y2 = _clamp_box_with_margin(50, 50, 50, 50, 640, 480, 0.0)
    assert x2 - x1 >= 1 and y2 - y1 >= 1


# --- _select_best_box ---------------------------------------------------------

def test_select_best_box_ignores_tiny_background_box():
    img_area = 1000.0 * 1000.0
    boxes = np.array([
        [0, 0, 50, 50],        # 0.25% area, very confident (e.g. a sign)
        [100, 100, 600, 500],  # 20% area, the fish
    ], dtype=float)
    confs = np.array([0.99, 0.40])
    box, conf, area_frac = _select_best_box(boxes, confs, img_area)
    np.testing.assert_array_equal(box, boxes[1])
    assert conf == 0.40
    assert area_frac == 0.2


def test_select_best_box_falls_back_to_tiny_boxes_when_no_large_one():
    img_area = 1000.0 * 1000.0
    boxes = np.array([[0, 0, 50, 50], [0, 0, 60, 60]], dtype=float)
    confs = np.array([0.30, 0.90])
    box, conf, _ = _select_best_box(boxes, confs, img_area)
    np.testing.assert_array_equal(box, boxes[1])
    assert conf == 0.90


# --- _mask_to_clean_bbox ------------------------------------------------------

def test_mask_to_clean_bbox_returns_exclusive_bounds():
    mask = np.zeros((100, 200), dtype=np.uint8)
    mask[10:30, 40:90] = 255
    assert _mask_to_clean_bbox(mask) == (40, 10, 90, 30)


def test_mask_to_clean_bbox_empty_mask_returns_none():
    assert _mask_to_clean_bbox(np.zeros((50, 50), dtype=np.uint8)) is None


# --- _resize_for_inference ----------------------------------------------------

def test_resize_for_inference_downscales_longest_side():
    img = np.zeros((1000, 2000, 3), dtype=np.uint8)
    resized, scale = _resize_for_inference(img, 1280)
    assert resized.shape == (640, 1280, 3)
    assert scale == 0.64


def test_resize_for_inference_keeps_small_image_untouched():
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    resized, scale = _resize_for_inference(img, 1280)
    assert resized is img
    assert scale == 1.0


def test_resize_for_inference_disabled_when_max_side_not_positive():
    img = np.zeros((3000, 4000, 3), dtype=np.uint8)
    resized, scale = _resize_for_inference(img, 0)
    assert resized is img
    assert scale == 1.0
