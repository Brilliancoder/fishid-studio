import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rodar_suite_benchmark as benchmark


def test_build_benchmark_records_keeps_latest_run_and_missing_experiments():
    df = pd.DataFrame([
        {"run_id": "old_tag", "frames_processados": 12},
        {"run_id": "new_tag", "pasta": "runs/new_tag", "frames_processados": 40,
         "peixes_contados": 0, "tempo_execucao_s": 1.5, "comprimento_mediano_px": 0},
        {"run_id": "new_tag_extra", "frames_processados": 99},
    ])
    records = benchmark.build_benchmark_records(df, [("missing", "Sem dados", "ERRO(1)"), ("tag", "Cena", "OK")])
    assert records == [
        {"tag": "missing", "description": "Sem dados", "status": "ERRO(1)", "frames_processados": None,
         "peixes_contados": None, "tempo_execucao_s": None, "comprimento_mediano_px": None,
         "erro_medio_pct": None, "pasta": None},
        {"tag": "tag", "description": "Cena", "status": "OK", "frames_processados": 40,
         "peixes_contados": 0, "tempo_execucao_s": 1.5, "comprimento_mediano_px": 0,
         "erro_medio_pct": None, "pasta": "runs/new_tag"},
    ]


def test_report_only_exports_same_mean_error_as_markdown(tmp_path, monkeypatch):
    tag, description, _ = benchmark.EXPERIMENTS[0]
    run = tmp_path / ("latest_" + tag)
    run.mkdir()
    pd.DataFrame([{
        "run_id": run.name, "pasta": str(run), "frames_processados": 30, "peixes_contados": 2,
        "comprimento_mediano_px": 120.5, "tempo_execucao_s": 2.1,
    }]).to_csv(tmp_path / "indice_experimentos.csv", index=False)
    pd.DataFrame({"erro_estimado_pct": [4.5, 5.5]}).to_csv(run / "resumo_peixes.csv", index=False)
    output = tmp_path / "comparativo.json"
    monkeypatch.setattr(benchmark, "EXP_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["benchmark", "--report-only", "--json-out", str(output)])
    benchmark.main()
    records = json.loads(output.read_text(encoding="utf-8"))
    assert len(records) == len(benchmark.EXPERIMENTS)
    assert records[0]["description"] == description
    assert records[0]["erro_medio_pct"] == 5.0
    assert records[1]["erro_medio_pct"] is None
    assert "±5.0%" in (tmp_path / "comparativo_10_experimentos.md").read_text(encoding="utf-8")
