import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from segmentar_peixes_auto import identify_review_reasons  # noqa: E402


@pytest.mark.parametrize(
    ("confidence", "boxes", "use_sam", "mask_saved", "area", "expected"),
    [
        (0.25, 2, True, True, 3.0, []),
        (0.25, 2, True, True, 92.0, []),
        (0.24, 1, True, True, 50.0, ["baixa_confianca"]),
        (0.5, 3, True, True, 50.0, ["multiplos_peixes"]),
        (0.5, 2, True, True, 2.9, ["area_mascara_atipica"]),
        (0.5, 2, True, True, 92.1, ["area_mascara_atipica"]),
        (0.5, 2, False, True, 2.9, []),
        (0.5, 2, True, False, 2.9, []),
        (0.2, 3, True, True, 93.0, [
            "baixa_confianca", "multiplos_peixes", "area_mascara_atipica",
        ]),
    ],
)
def test_segmentation_review_reasons(confidence, boxes, use_sam, mask_saved, area, expected):
    assert identify_review_reasons(confidence, boxes, use_sam, mask_saved, area) == expected


def test_segmentation_review_accepts_custom_confidence_threshold():
    assert identify_review_reasons(0.4, 1, False, False, 0.0, review_thresh=0.5) == [
        "baixa_confianca",
    ]
