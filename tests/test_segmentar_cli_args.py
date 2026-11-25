import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from segmentar_peixes_auto import DEFAULT_OUT_DIR, DEFAULT_SPLITS_DIR, parse_args  # noqa: E402


def test_segmentation_cli_defaults():
    args = parse_args([])
    assert vars(args) == {
        "splits_dir": Path(DEFAULT_SPLITS_DIR),
        "out_dir": Path(DEFAULT_OUT_DIR),
        "yolo_weights": "yolov8l-worldv2.pt",
        "sam_weights": "sam2.1_t.pt",
        "conf": 0.08,
        "review_thresh": 0.25,
        "margin": 0.15,
        "batch_size": 16,
        "max_infer_side": 1280,
        "io_workers": 8,
        "no_sam": False,
        "no_staging": False,
        "limit": None,
    }


def test_segmentation_cli_accepts_custom_flags():
    args = parse_args(["--no-sam", "--limit", "20", "--margin", "0.2"])
    assert args.no_sam is True
    assert args.limit == 20
    assert args.margin == 0.2


def test_segmentation_cli_ignores_colab_kernel_args(monkeypatch):
    kernel_args = ["-f", "/root/.local/share/jupyter/runtime/kernel-123.json"]
    assert parse_args(kernel_args) == parse_args([])
    monkeypatch.setattr(sys, "argv", ["segmentar_peixes_auto.py", *kernel_args, "--limit", "20"])
    assert parse_args().limit == 20
    assert parse_args([]).limit is None
