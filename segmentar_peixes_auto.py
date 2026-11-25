"""Segmentação e recorte automático de peixes marinhos (YOLO-World + SAM 2) — Versão Turbo GPU.

Otimizações de performance (reduz o tempo de >1h para ~3–8 min em GPU T4/L4/A100 no Colab):
    1. Inferência em lote (batch) + FP16 (half=True) na GPU com aviso claro caso o Colab esteja em CPU.
    2. Leitura e gravação paralelas com ThreadPoolExecutor (GPU não fica ociosa esperando disco).
    3. Staging em SSD local do Colab (/content/_seg_staging) para evitar o gargalo do Google Drive FUSE
       (gravar 12.000 arquivos um por um no Drive causa 40+ minutos só de latência de rede), com
       sincronização paralela segura para o Drive ao final de cada split.
    4. Redimensionamento inteligente para inferência (max 1280px) preservando o recorte na resolução original.
    5. Pesos rápidos por padrão (`yolov8m-worldv2.pt` + `sam2.1_t.pt`) com ótima precisão de contorno.

Uso no Google Colab (cole numa célula após `!pip install -q ultralytics opencv-python-headless pandas tqdm`):
    - Basta executar a célula diretamente (usa os caminhos padrão do seu Drive), OU rodar via terminal:
      !python segmentar_peixes_auto.py --limit 20
      !python segmentar_peixes_auto.py --no-sam        # só recorte rápido (~2 min para 6.200 fotos)

Saídas geradas em `--out-dir`:
    - crops/<split>/<especie>/<arquivo>.jpg     -> Peixe recortado com margem (pronto para o ConvNeXt-Tiny)
    - masks/<split>/<especie>/<arquivo>.png     -> Máscara binária 0/255 (base para medição de comprimento)
    - split_train_cropped.csv / validation / test -> Novos CSVs mantendo exatamente os splits originais
    - revisao_manual.csv                        -> Lista apenas casos difíceis para revisão humana
"""
from __future__ import annotations

import argparse
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm

# =============================================================================
# Configurações padrão (funcionam via terminal OU colando direto numa célula do Colab!)
# =============================================================================
DEFAULT_SPLITS_DIR: str = os.getenv(
    "FISHID_SPLITS_DIR",
    "/content/drive/MyDrive/modelos_peixes/fonte_verdade_experimentos/run_20261011_165821",
)
DEFAULT_OUT_DIR: str = os.getenv(
    "FISHID_SEG_OUT_DIR",
    "/content/drive/MyDrive/modelos_peixes/dataset_segmentado",
)
DEFAULT_LIMIT: int | None = None      # None = dataset completo (~6.220 fotos); coloque 20 só para teste rápido
DEFAULT_USE_SAM: bool = True          # Mude para False se quiser apenas os recortes ultrarrápidos (sem máscara)
DEFAULT_BATCH_SIZE: int = 16          # Lote de imagens por chamada do YOLO-World na GPU
DEFAULT_MAX_INFER_SIDE: int = 1280    # Reduz fotos 4K/12MP apenas na inferência (recorte final mantém resolução original)
DEFAULT_IO_WORKERS: int = 8           # Threads paralelas para leitura/escrita

# Classes textuais open-vocabulary otimizadas para grandes peixes migratórios (alto recall em fotos de campo)
FISH_PROMPTS: list[str] = [
    "fish",
    "large fish",
    "ocean fish",
    "tuna",
    "marlin",
    "sailfish",
    "swordfish",
    "billfish",
    "mahi mahi",
    "dolphin fish",
    "shark",
    "dead fish",
    "caught fish",
    "seafood",
]


def _clamp_box_with_margin(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    img_w: int,
    img_h: int,
    margin_ratio: float,
) -> tuple[int, int, int, int]:
    bw = max(1.0, x2 - x1)
    bh = max(1.0, y2 - y1)
    mx = bw * margin_ratio
    my = bh * margin_ratio
    nx1 = max(0, int(round(x1 - mx)))
    ny1 = max(0, int(round(y1 - my)))
    nx2 = min(img_w, int(round(x2 + mx)))
    ny2 = min(img_h, int(round(y2 + my)))
    return nx1, ny1, max(nx1 + 1, nx2), max(ny1 + 1, ny2)


def _select_best_box(
    boxes_xyxy: np.ndarray,
    confs: np.ndarray,
    img_area: float,
    min_primary_area_frac: float = 0.04,
) -> tuple[np.ndarray, float, float]:
    """Escolhe o peixe principal ponderando confiança e área relativa (ignora placas/ruídos minúsculos)."""
    areas_frac = [
        min(1.0, max(1.0, float((b[2] - b[0]) * (b[3] - b[1]))) / max(img_area, 1.0))
        for b in boxes_xyxy
    ]
    # Se houver pelo menos uma detecção razoável (>= 4% da imagem), descarta micro-caixas do fundo
    valid_idxs = [i for i, af in enumerate(areas_frac) if af >= min_primary_area_frac]
    candidate_idxs = valid_idxs if valid_idxs else list(range(len(boxes_xyxy)))

    best_idx = candidate_idxs[0]
    best_score = -1.0
    for idx in candidate_idxs:
        af = areas_frac[idx]
        score = float(confs[idx]) * (0.45 + 0.55 * np.sqrt(af))
        if score > best_score:
            best_score = score
            best_idx = idx
    return boxes_xyxy[best_idx], float(confs[best_idx]), float(areas_frac[best_idx])


def merge_yolo_and_sam_bbox(
    yolo_box: np.ndarray | tuple,
    sam_bbox: tuple[int, int, int, int] | None,
) -> np.ndarray:
    """Return the float32 box covering the detection and, if present, the mask."""
    if sam_bbox is None:
        return np.asarray(yolo_box, dtype=np.float32)
    x0, y0, x1, y1 = yolo_box
    sx0, sy0, sx1, sy1 = sam_bbox
    return np.array(
        [min(x0, sx0), min(y0, sy0), max(x1, sx1), max(y1, sy1)],
        dtype=np.float32,
    )


def _mask_to_clean_bbox(mask_u8: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.where(mask_u8 > 0)
    if len(xs) == 0 or len(ys) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _resize_for_inference(img_bgr: np.ndarray, max_side: int) -> tuple[np.ndarray, float]:
    """Redimensiona imagens muito grandes para acelerar YOLO/SAM e retorna o fator de escala."""
    h, w = img_bgr.shape[:2]
    longest = max(h, w)
    if max_side <= 0 or longest <= max_side:
        return img_bgr, 1.0
    scale = max_side / float(longest)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return resized, scale


def _read_image_task(item: tuple[int, Path, int]) -> tuple[int, np.ndarray | None, np.ndarray | None, float]:
    """Lê imagem do disco e já prepara a versão redimensionada para inferência (em thread paralela)."""
    idx, path, max_side = item
    img_bgr = cv2.imread(str(path))
    if img_bgr is None:
        return idx, None, None, 1.0
    infer_bgr, scale = _resize_for_inference(img_bgr, max_side)
    return idx, img_bgr, infer_bgr, scale


def _write_image_task(args: tuple[Path, np.ndarray, list[int]]) -> None:
    path, img, params = args
    cv2.imwrite(str(path), img, params)


def _sync_directory_parallel(src_root: Path, dst_root: Path, workers: int = 8) -> int:
    """Copia arquivos do SSD local para o Google Drive em paralelo (muito mais rápido que FUSE sequencial)."""
    if not src_root.exists():
        return 0

    pairs: list[tuple[Path, Path]] = []
    dirs_to_make: set[Path] = set()
    for src_file in src_root.rglob("*"):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(src_root)
        dst_file = dst_root / rel
        dirs_to_make.add(dst_file.parent)
        pairs.append((src_file, dst_file))

    for d in sorted(dirs_to_make):
        d.mkdir(parents=True, exist_ok=True)

    def _copy_one(pair: tuple[Path, Path]) -> None:
        shutil.copy2(pair[0], pair[1])

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(tqdm(pool.map(_copy_one, pairs), total=len(pairs), desc="Sincronizando p/ Drive", leave=False))
    return len(pairs)


def run_segmentation(
    splits_dir: Path,
    out_dir: Path,
    yolo_weights: str,
    sam_weights: str,
    conf_thresh: float,
    review_thresh: float,
    margin_ratio: float,
    use_sam: bool,
    limit: int | None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_infer_side: int = DEFAULT_MAX_INFER_SIDE,
    io_workers: int = DEFAULT_IO_WORKERS,
    use_local_staging: bool = True,
) -> None:
    import torch
    from ultralytics import SAM, YOLO

    has_cuda = torch.cuda.is_available()
    device = 0 if has_cuda else "cpu"
    use_half = bool(has_cuda)

    if has_cuda:
        gpu_name = torch.cuda.get_device_name(0)
        print(f"GPU detectada: {gpu_name} | FP16 (half): ATIVADO | Batch: {batch_size}")
    else:
        print("=" * 72)
        print("[AVISO CRÍTICO] Nenhuma GPU CUDA detectada — rodando em CPU!")
        print("No Colab vá em: Ambiente de execução -> Alterar tipo -> GPU (T4 / L4 / A100).")
        print("Em CPU o processo pode levar horas; em GPU leva poucos minutos.")
        print("=" * 72)

    print(f"Carregando detector open-vocabulary: {yolo_weights}")
    detector = YOLO(yolo_weights)
    detector.set_classes(FISH_PROMPTS)

    sam_model = None
    if use_sam:
        print(f"Carregando segmentador SAM 2: {sam_weights}")
        sam_model = SAM(sam_weights)
    else:
        print("Modo rápido (--no-sam): recorte direto pelo YOLO-World sem máscaras SAM 2.")

    out_dir.mkdir(parents=True, exist_ok=True)

    # Usa SSD local do Colab quando a saída está no Google Drive para eliminar lentidão do FUSE
    is_drive_out = "/content/drive/" in str(out_dir).replace("\\", "/")
    staging_root = Path("/content/_fishid_seg_staging") if (use_local_staging and is_drive_out and Path("/content").is_dir()) else out_dir
    if staging_root != out_dir:
        staging_root.mkdir(parents=True, exist_ok=True)
        print(f"Staging SSD local ativado: {staging_root} -> sincronização paralela para {out_dir}")

    review_rows: list[dict] = []
    splits_processed = 0
    t_global = time.perf_counter()

    with ThreadPoolExecutor(max_workers=io_workers) as io_pool:
        for split_name in ("train", "validation", "test"):
            csv_path = splits_dir / f"split_{split_name}.csv"
            if not csv_path.is_file():
                print(f"[AVISO] Split não encontrado, pulando: {csv_path}")
                continue
            splits_processed += 1

            df = pd.read_csv(csv_path)
            if limit is not None:
                df = df.head(limit).copy()

            # Pré-cria todas as subpastas de espécies UMA única vez (zero mkdir no loop!)
            unique_species = sorted({str(s).replace("/", "_").replace(" ", "_") for s in df["species"].unique()})
            for safe_sp in unique_species:
                (staging_root / "crops" / split_name / safe_sp).mkdir(parents=True, exist_ok=True)
                if use_sam:
                    (staging_root / "masks" / split_name / safe_sp).mkdir(parents=True, exist_ok=True)

            # Mapa rápido de arquivos já existentes no destino final (retomada sem stat repetido)
            existing_crops: set[str] = set()
            existing_masks: set[str] = set()
            final_crop_split = out_dir / "crops" / split_name
            final_mask_split = out_dir / "masks" / split_name
            if final_crop_split.exists():
                for root_d, _, files in os.walk(final_crop_split):
                    sp_dir = Path(root_d).name
                    for fname in files:
                        existing_crops.add(f"{sp_dir}/{fname}")
            if use_sam and final_mask_split.exists():
                for root_d, _, files in os.walk(final_mask_split):
                    sp_dir = Path(root_d).name
                    for fname in files:
                        existing_masks.add(f"{sp_dir}/{fname}")

            new_rows: list[dict] = []
            pending_items: list[dict] = []

            for row in df.itertuples(index=False):
                src_path = Path(str(row.path))
                species = str(row.species)
                label = int(row.label)
                safe_species = species.replace("/", "_").replace(" ", "_")

                crop_rel = f"{safe_species}/{src_path.stem}.jpg"
                mask_rel = f"{safe_species}/{src_path.stem}.png"
                final_crop = out_dir / "crops" / split_name / crop_rel
                final_mask = out_dir / "masks" / split_name / mask_rel

                if crop_rel in existing_crops and (not use_sam or mask_rel in existing_masks):
                    new_rows.append(
                        {
                            "path": str(final_crop),
                            "original_path": str(src_path),
                            "mask_path": str(final_mask) if mask_rel in existing_masks else "",
                            "species": species,
                            "label": label,
                            "status": "cached",
                        }
                    )
                else:
                    pending_items.append(
                        {
                            "src_path": src_path,
                            "species": species,
                            "label": label,
                            "stage_crop": staging_root / "crops" / split_name / crop_rel,
                            "stage_mask": staging_root / "masks" / split_name / mask_rel,
                            "final_crop": final_crop,
                            "final_mask": final_mask,
                        }
                    )

            print(
                f"\nSplit '{split_name}': {len(df)} total | {len(new_rows)} já prontos (cache) | {len(pending_items)} a processar"
            )

            pbar = tqdm(total=len(pending_items), desc=f"Split {split_name}", unit="img")
            pending_writes = []

            for start in range(0, len(pending_items), batch_size):
                chunk = pending_items[start : start + batch_size]

                # 1) Leitura + pré-redimensionamento em paralelo
                read_jobs = [(i, it["src_path"], max_infer_side) for i, it in enumerate(chunk)]
                loaded = list(io_pool.map(_read_image_task, read_jobs))

                valid_entries: list[tuple[dict, np.ndarray, np.ndarray, float]] = []
                for idx_local, img_bgr, infer_bgr, scale in loaded:
                    item = chunk[idx_local]
                    if img_bgr is None or infer_bgr is None:
                        review_rows.append(
                            {
                                "split": split_name,
                                "path": str(item["src_path"]),
                                "species": item["species"],
                                "motivo": "falha_leitura_imagem",
                                "confianca": 0.0,
                                "area_mascara_pct": 0.0,
                            }
                        )
                        pbar.update(1)
                    else:
                        valid_entries.append((item, img_bgr, infer_bgr, scale))

                if not valid_entries:
                    continue

                # 2) YOLO-World EM LOTE (batch na GPU com FP16!)
                infer_batch = [entry[2] for entry in valid_entries]
                det_results = detector.predict(
                    infer_batch,
                    conf=conf_thresh,
                    imgsz=640,
                    device=device,
                    half=use_half,
                    verbose=False,
                )

                for (item, img_bgr, infer_bgr, scale), det_res in zip(valid_entries, det_results):
                    img_h, img_w = img_bgr.shape[:2]
                    inf_h, inf_w = infer_bgr.shape[:2]
                    inf_area = float(inf_w * inf_h)
                    boxes = det_res.boxes

                    # Passada 2 (resgate em alta resolução 960px / FP32 / conf 0.025) para casos difíceis
                    if boxes is None or len(boxes) == 0:
                        rescue_res = detector.predict(
                            infer_bgr,
                            conf=min(0.025, conf_thresh),
                            imgsz=960,
                            device=device,
                            verbose=False,
                        )[0]
                        boxes = rescue_res.boxes

                    if boxes is None or len(boxes) == 0:
                        pending_writes.append(
                            io_pool.submit(
                                _write_image_task,
                                (item["stage_crop"], img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 92]),
                            )
                        )
                        review_rows.append(
                            {
                                "split": split_name,
                                "path": str(item["src_path"]),
                                "species": item["species"],
                                "motivo": "nenhum_peixe_detectado",
                                "confianca": 0.0,
                                "area_mascara_pct": 100.0,
                            }
                        )
                        new_rows.append(
                            {
                                "path": str(item["final_crop"]),
                                "original_path": str(item["src_path"]),
                                "mask_path": "",
                                "species": item["species"],
                                "label": item["label"],
                                "status": "fallback_full",
                            }
                        )
                        pbar.update(1)
                        continue

                    boxes_xyxy = boxes.xyxy.cpu().numpy()
                    confs = boxes.conf.cpu().numpy()
                    best_box_inf, best_conf, best_area_frac = _select_best_box(boxes_xyxy, confs, inf_area)

                    # Rejeita micro-detecções (< 2,5% da foto, ex.: placa/desenho de peixe na parede)
                    if best_area_frac < 0.025:
                        pending_writes.append(
                            io_pool.submit(
                                _write_image_task,
                                (item["stage_crop"], img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 92]),
                            )
                        )
                        review_rows.append(
                            {
                                "split": split_name,
                                "path": str(item["src_path"]),
                                "species": item["species"],
                                "motivo": "deteccao_muito_pequena_fallback",
                                "confianca": round(best_conf, 4),
                                "area_mascara_pct": round(best_area_frac * 100.0, 2),
                            }
                        )
                        new_rows.append(
                            {
                                "path": str(item["final_crop"]),
                                "original_path": str(item["src_path"]),
                                "mask_path": "",
                                "species": item["species"],
                                "label": item["label"],
                                "status": "fallback_full",
                            }
                        )
                        pbar.update(1)
                        continue

                    mask_area_pct = 0.0
                    mask_saved = False
                    final_box_inf = best_box_inf

                    # 3) SAM 2 na imagem redimensionada (até 4x mais rápido que em 12MP!)
                    if sam_model is not None:
                        sam_res = sam_model.predict(
                            infer_bgr,
                            bboxes=[best_box_inf.tolist()],
                            device=device,
                            verbose=False,
                        )[0]
                        if sam_res.masks is not None and len(sam_res.masks.data) > 0:
                            mask_raw = sam_res.masks.data[0].cpu().numpy()
                            mask_u8 = (mask_raw > 0.5).astype(np.uint8) * 255
                            if mask_u8.shape != (inf_h, inf_w):
                                mask_u8 = cv2.resize(mask_u8, (inf_w, inf_h), interpolation=cv2.INTER_NEAREST)
                            pending_writes.append(
                                io_pool.submit(
                                    _write_image_task,
                                    (item["stage_mask"], mask_u8, [int(cv2.IMWRITE_PNG_COMPRESSION), 1]),
                                )
                            )
                            mask_saved = True
                            mask_area_pct = round(100.0 * float(np.count_nonzero(mask_u8)) / max(inf_area, 1.0), 2)
                            tight = _mask_to_clean_bbox(mask_u8)
                            # UNIÃO da caixa YOLO + máscara SAM 2: preserva bico/rostro fino e nadadeiras longas
                            final_box_inf = merge_yolo_and_sam_bbox(best_box_inf, tight)

                    # Reprojeta a caixa para a resolução ORIGINAL e recorta sem perda de qualidade
                    inv_scale = 1.0 / scale
                    x1, y1, x2, y2 = _clamp_box_with_margin(
                        float(final_box_inf[0]) * inv_scale,
                        float(final_box_inf[1]) * inv_scale,
                        float(final_box_inf[2]) * inv_scale,
                        float(final_box_inf[3]) * inv_scale,
                        img_w,
                        img_h,
                        margin_ratio=margin_ratio,
                    )
                    crop_bgr = img_bgr[y1:y2, x1:x2]
                    pending_writes.append(
                        io_pool.submit(
                            _write_image_task,
                            (item["stage_crop"], crop_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 92]),
                        )
                    )

                    motivos = []
                    if best_conf < review_thresh:
                        motivos.append("baixa_confianca")
                    if len(boxes_xyxy) > 2:
                        motivos.append("multiplos_peixes")
                    if use_sam and mask_saved and (mask_area_pct < 3.0 or mask_area_pct > 92.0):
                        motivos.append("area_mascara_atipica")

                    if motivos:
                        review_rows.append(
                            {
                                "split": split_name,
                                "path": str(item["src_path"]),
                                "crop_path": str(item["final_crop"]),
                                "species": item["species"],
                                "motivo": ",".join(motivos),
                                "confianca": round(best_conf, 4),
                                "area_mascara_pct": mask_area_pct,
                            }
                        )

                    new_rows.append(
                        {
                            "path": str(item["final_crop"]),
                            "original_path": str(item["src_path"]),
                            "mask_path": str(item["final_mask"]) if mask_saved else "",
                            "species": item["species"],
                            "label": item["label"],
                            "status": "ok",
                        }
                    )
                    pbar.update(1)

                # Evita acumular memória RAM com centenas de gravações pendentes
                if len(pending_writes) >= batch_size * 4:
                    for fut in pending_writes:
                        fut.result()
                    pending_writes.clear()

            for fut in pending_writes:
                fut.result()
            pending_writes.clear()
            pbar.close()

            # Sincroniza o split concluído do SSD local para o Google Drive em paralelo
            if staging_root != out_dir and len(pending_items) > 0:
                copied_crops = _sync_directory_parallel(
                    staging_root / "crops" / split_name,
                    out_dir / "crops" / split_name,
                    workers=io_workers,
                )
                copied_masks = (
                    _sync_directory_parallel(
                        staging_root / "masks" / split_name,
                        out_dir / "masks" / split_name,
                        workers=io_workers,
                    )
                    if use_sam
                    else 0
                )
                print(f"Sincronizado para o Drive ({split_name}): {copied_crops} crops, {copied_masks} masks")

            out_csv = out_dir / f"split_{split_name}_cropped.csv"
            pd.DataFrame(new_rows).to_csv(out_csv, index=False)
            print(f"Split salvo: {out_csv} ({len(new_rows)} imagens)")

    if splits_processed == 0:
        raise FileNotFoundError(
            f"Nenhum arquivo split_train.csv / split_validation.csv / split_test.csv encontrado em: {splits_dir}\n"
            "Passe o caminho correto do seu Google Drive em --splits-dir (ou edite DEFAULT_SPLITS_DIR) "
            "e salve a saída no Drive em --out-dir (ou DEFAULT_OUT_DIR)."
        )

    review_csv = out_dir / "revisao_manual.csv"
    pd.DataFrame(review_rows).to_csv(review_csv, index=False)
    elapsed_min = (time.perf_counter() - t_global) / 60.0
    print(f"\nConcluído em {elapsed_min:.1f} min! Casos para revisão manual: {len(review_rows)} -> {review_csv}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Auto-segmentação turbo de peixes (YOLO-World + SAM 2) com batch FP16 e staging local."
    )
    parser.add_argument("--splits-dir", type=Path, default=Path(DEFAULT_SPLITS_DIR), help="Pasta com split_train/validation/test.csv")
    parser.add_argument("--out-dir", type=Path, default=Path(DEFAULT_OUT_DIR), help="Pasta de saída para crops, masks e CSVs")
    parser.add_argument("--yolo-weights", type=str, default="yolov8l-worldv2.pt", help="Peso do YOLO-World (s/m/l/x)")
    parser.add_argument("--sam-weights", type=str, default="sam2.1_t.pt", help="Peso do SAM 2 (sam2.1_t.pt = 3x mais rápido)")
    parser.add_argument("--conf", type=float, default=0.08, help="Limiar mínimo de detecção do YOLO-World (passada 1)")
    parser.add_argument("--review-thresh", type=float, default=0.25, help="Abaixo disso envia para revisao_manual.csv")
    parser.add_argument("--margin", type=float, default=0.15, help="Margem extra ao redor do peixe (0.15 = 15%)")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="Imagens por lote no YOLO-World")
    parser.add_argument("--max-infer-side", type=int, default=DEFAULT_MAX_INFER_SIDE, help="Lado máximo na inferência (0 = original)")
    parser.add_argument("--io-workers", type=int, default=DEFAULT_IO_WORKERS, help="Threads paralelas de leitura/escrita")
    parser.add_argument("--no-sam", action="store_true", default=not DEFAULT_USE_SAM, help="Desliga o SAM 2 (recorte ultrarrápido)")
    parser.add_argument("--no-staging", action="store_true", help="Escreve direto em --out-dir sem SSD local")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Limita quantidade por split para teste rápido")
    # parse_known_args() ignora argumentos internos do kernel do Google Colab (-f kernel.json)
    args, _ = parser.parse_known_args()
    return args


if __name__ == "__main__":
    # Monta automaticamente o Google Drive se estiver rodando dentro do Google Colab
    try:
        from google.colab import drive
        if not Path("/content/drive/MyDrive").exists():
            drive.mount("/content/drive")
    except ImportError:
        pass

    args = parse_args()
    run_segmentation(
        splits_dir=args.splits_dir,
        out_dir=args.out_dir,
        yolo_weights=args.yolo_weights,
        sam_weights=args.sam_weights,
        conf_thresh=args.conf,
        review_thresh=args.review_thresh,
        margin_ratio=args.margin,
        use_sam=not args.no_sam,
        limit=args.limit,
        batch_size=args.batch_size,
        max_infer_side=args.max_infer_side,
        io_workers=args.io_workers,
        use_local_staging=not args.no_staging,
    )
