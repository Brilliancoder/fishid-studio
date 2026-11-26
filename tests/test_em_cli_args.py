import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from monitoramento_em import parse_args  # noqa: E402
from rodar_suite_benchmark import EXPERIMENTS  # noqa: E402


def test_default_monitoring_arguments():
    args = parse_args(["--video", "test.mp4"])
    assert vars(args) == {
        "video": Path("test.mp4"),
        "tag": "v5",
        "exp_root": Path("experimentos_em"),
        "start_frame": 0,
        "end_frame": None,
        "frame_step": 1,
        "yolo_weights": "yolov8l-worldv2.pt",
        "sam_weights": "sam2.1_t.pt",
        "tracker": "bytetrack.yaml",
        "imgsz": 960,
        "conf": 0.12,
        "min_track_frames": 2,
        "min_event_frames": 4,
        "min_area_px": 15000,
        "min_length_px": 320.0,
        "min_aspect_ratio": 1.7,
        "merge_gap_s": 120.0,
        "merge_dist_px": 450.0,
        "top_k_frames": 6,
        "simple_centerline": False,
        "cm_por_px": None,
        "fishid_api": "",
        "save_video": False,
        "cpu": False,
    }


@pytest.mark.parametrize(
    ("tag", "flags"), [(tag, flags) for tag, _, flags in EXPERIMENTS],
    ids=[tag for tag, _, _ in EXPERIMENTS],
)
def test_monitoring_accepts_each_benchmark_experiment(tag, flags):
    args = parse_args(["--video", "test.mp4", "--tag", tag, *flags])
    assert args.video == Path("test.mp4")
    assert args.tag == tag
    assert args.start_frame < args.end_frame
