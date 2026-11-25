import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rastrear_peixes_auto import PALETTE_BGR, _color_for_id, parse_args


def test_track_colors_use_bgr_palette_and_wrap():
    size = len(PALETTE_BGR)
    for track_id in (0, 1, size - 1, size, size + 1, -1):
        color = _color_for_id(track_id)
        assert isinstance(color, tuple)
        assert len(color) == 3
        assert all(isinstance(channel, int) and 0 <= channel <= 255 for channel in color)
        assert color == PALETTE_BGR[track_id % size]


def test_tracking_cli_defaults():
    args = parse_args([])
    assert args.tracker == "bytetrack.yaml"
    assert args.no_labels is False
    assert args.max_frames is None


def test_tracking_cli_flags_ignore_extra_notebook_arguments():
    args = parse_args(["--no-labels", "--max-frames", "12", "-f", "kernel.json"])
    assert args.no_labels is True
    assert args.max_frames == 12
