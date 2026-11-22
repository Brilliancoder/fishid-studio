"""Suite sistemática de 10 experimentos controlados (ablação + cenas reais + stress anti-FP).

Executa 10 configurações no vídeo 30_06_2023.mp4 (todos centralizados em experimentos_em/)
e gera o comparativo final em experimentos_em/comparativo_10_experimentos.md.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

DEFAULT_VIDEO = os.getenv("FISHID_EM_VIDEO", "./data/video_em.mp4")
PY = sys.executable
SCRIPT = str(Path(__file__).parent / "monitoramento_em.py")
EXP_ROOT = Path(__file__).parent / "experimentos_em"

EXPERIMENTS: list[tuple[str, str, list[str]]] = [
    (
        "exp04_12h_v4_ridge",
        "Janela 12h (5m) — v4 padrão (YOLOv8l + ByteTrack + SAM2.1-t + crista coluna)",
        ["--start-frame", "42697", "--end-frame", "43297", "--conf", "0.12", "--min-event-frames", "4"],
    ),
    (
        "exp05_12h_ablation_simple",
        "Janela 12h (5m) — Ablação: linha média simples (sem crista distanceTransform)",
        ["--start-frame", "42697", "--end-frame", "43297", "--conf", "0.12", "--min-event-frames", "4", "--simple-centerline"],
    ),
    (
        "exp06_12h_sam21_small",
        "Janela 12h (5m) — Comparativo SAM 2.1 Small (sam2.1_s.pt vs Tiny)",
        ["--start-frame", "42697", "--end-frame", "43297", "--conf", "0.12", "--min-event-frames", "4", "--sam-weights", "sam2.1_s.pt"],
    ),
    (
        "exp07_12h_botsort",
        "Janela 12h (5m) — Comparativo rastreador BoT-SORT vs ByteTrack",
        ["--start-frame", "42697", "--end-frame", "43297", "--conf", "0.12", "--min-event-frames", "4", "--tracker", "botsort.yaml"],
    ),
    (
        "exp08_12h_1fps_step2",
        "Janela 12h (5m) — Velocidade 1 FPS (--frame-step 2, min_event=2)",
        ["--start-frame", "42697", "--end-frame", "43297", "--conf", "0.12", "--frame-step", "2", "--min-event-frames", "2"],
    ),
    (
        "exp09_12h_imgsz1280",
        "Janela 12h (5m) — Resolução de inferência 1280px vs 960px",
        ["--start-frame", "42697", "--end-frame", "43297", "--conf", "0.12", "--min-event-frames", "4", "--imgsz", "1280"],
    ),
    (
        "exp10_cena_02h32_madrugada",
        "Cena real 02h32 (3m) — Múltiplos peixes no convés à madrugada",
        ["--start-frame", "18060", "--end-frame", "18420", "--conf", "0.15", "--min-event-frames", "4"],
    ),
    (
        "exp11_cena_05h04_multipeixes",
        "Cena real 05h04 (3m) — 4 peixes + 4 pescadores (alta oclusão)",
        ["--start-frame", "36300", "--end-frame", "36660", "--conf", "0.15", "--min-event-frames", "4"],
    ),
    (
        "exp12_stress_09h35_boias",
        "Teste stress 09h35 (3m) — Boias amarelas/rosas sem peixe (alvo: 0 FP)",
        ["--start-frame", "68800", "--end-frame", "69160", "--conf", "0.15", "--min-event-frames", "4"],
    ),
    (
        "exp13_stress_01h12_vazio",
        "Teste stress 01h12 (3m) — Convés vazio à noite (alvo: 0 FP)",
        ["--start-frame", "4150", "--end-frame", "4510", "--conf", "0.15", "--min-event-frames", "4"],
    ),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Suíte controlada de 10 experimentos de Monitoramento Eletrônico.")
    parser.add_argument("--video", type=str, default=DEFAULT_VIDEO, help="Caminho do vídeo MP4/MOV (ou env FISHID_EM_VIDEO)")
    parser.add_argument("--report-only", action="store_true", help="Apenas regenera a tabela comparativa a partir do índice")
    args = parser.parse_args()

    video_arg = args.video
    report_only = args.report_only
    results_summary = []

    if not report_only:
        print(f"Iniciando suite de {len(EXPERIMENTS)} experimentos controlados...\n")
        for i, (tag, desc, extra_args) in enumerate(EXPERIMENTS, start=1):
            print(f"\n==================== [{i}/{len(EXPERIMENTS)}] {tag} ====================")
            print(f"Objetivo: {desc}")
            cmd = [PY, SCRIPT, "--video", video_arg, "--tag", tag, *extra_args]
            proc = subprocess.run(cmd, check=False)
            status = "OK" if proc.returncode == 0 else f"ERRO({proc.returncode})"
            results_summary.append((tag, desc, status))
    else:
        results_summary = [(tag, desc, "OK") for tag, desc, _ in EXPERIMENTS]

    # Gera tabela comparativa consolidada a partir do indice_experimentos.csv
    idx_path = EXP_ROOT / "indice_experimentos.csv"
    if idx_path.exists():
        df = pd.read_csv(idx_path)
        suite_tags = {t for t, _, _ in EXPERIMENTS}
        # Pega o último run de cada tag da suite
        rows_md = [
            "# Comparativo Consolidado — Suite de 10 Experimentos (`30_06_2023.mp4`)",
            "",
            "| Experimento | Objetivo | Frames | Contados | Tam. Mediano (px) | Erro Médio (±%) | Tempo (s) | Pasta |",
            "| :--- | :--- | :-: | :-: | :-: | :-: | :-: | :--- |",
        ]
        for tag, desc, status in results_summary:
            match = df[df["run_id"].str.endswith("_" + tag)]
            if not match.empty:
                r = match.iloc[-1]
                run_dir = Path(r["pasta"])
                res_csv = run_dir / "resumo_peixes.csv"
                err_str = "-"
                if res_csv.exists() and res_csv.stat().st_size > 10:
                    try:
                        rdf = pd.read_csv(res_csv)
                        if not rdf.empty and "erro_estimado_pct" in rdf.columns:
                            err_str = f"±{rdf['erro_estimado_pct'].mean():.1f}%"
                    except Exception:
                        pass
                rows_md.append(
                    f"| `{tag}` | {desc} | {int(r['frames_processados'])} | **{int(r['peixes_contados'])}** "
                    f"| {r['comprimento_mediano_px']} | {err_str} | {r['tempo_execucao_s']}s | `{run_dir.name}` |"
                )
            else:
                rows_md.append(f"| `{tag}` | {desc} | - | {status} | - | - | - | - |")

        out_md = EXP_ROOT / "comparativo_10_experimentos.md"
        out_md.write_text("\n".join(rows_md) + "\n", encoding="utf-8")
        print(f"\nComparativo salvo em: {out_md}")


if __name__ == "__main__":
    main()
