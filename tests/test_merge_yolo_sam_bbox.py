import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from segmentar_peixes_auto import merge_yolo_and_sam_bbox  # noqa: E402


@pytest.mark.parametrize(
    ("yolo_box", "sam_bbox", "expected"),
    [
        ((10.5, 20.5, 80.5, 60.5), None, (10.5, 20.5, 80.5, 60.5)),
        (np.array([10.5, 20.5, 80.5, 60.5]), (2, 15, 95, 70), (2, 15, 95, 70)),
        (np.array([10.5, 20.5, 80.5, 60.5]), (15, 25, 75, 55), (10.5, 20.5, 80.5, 60.5)),
        ((10.5, 20.5, 80.5, 60.5), (2, 25, 75, 70), (2, 20.5, 80.5, 70)),
    ],
    ids=["no-mask", "sam-extends", "yolo-extends", "both-extend"],
)
def test_merge_yolo_and_sam_bbox(yolo_box, sam_bbox, expected):
    result = merge_yolo_and_sam_bbox(yolo_box, sam_bbox)
    assert result.dtype == np.float32
    assert result.shape == (4,)
    np.testing.assert_array_equal(result, expected)
