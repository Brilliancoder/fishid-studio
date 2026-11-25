import shlex
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rodar_suite_benchmark as benchmark


@pytest.mark.parametrize("only", [None, "exp04_12h_v4_ridge"])
def test_dry_run_only_prints_selected_commands(only, monkeypatch, capsys, tmp_path):
    video = str(tmp_path / "test video.mp4")
    output = tmp_path / "report.json"
    args = ["benchmark", "--dry-run", "--video", video, "--json-out", str(output)]
    selected = benchmark.EXPERIMENTS
    if only:
        args += ["--only", only]
        selected = [exp for exp in selected if exp[0] == only]

    monkeypatch.setattr(sys, "argv", args)
    monkeypatch.setattr(benchmark, "EXP_ROOT", tmp_path)
    index = tmp_path / "indice_experimentos.csv"
    index.touch()
    with patch.object(benchmark.subprocess, "run") as run:
        benchmark.main()
    run.assert_not_called()

    commands = [shlex.split(line) for line in capsys.readouterr().out.splitlines()]
    assert commands == [
        [benchmark.PY, benchmark.SCRIPT, "--video", video, "--tag", tag, *extra]
        for tag, _, extra in selected
    ]
    assert list(tmp_path.iterdir()) == [index]
