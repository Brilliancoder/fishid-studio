from __future__ import annotations

import base64
import hashlib
import html
import io
import json
import math
import os
import random
import subprocess
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageDraw, ImageFont, ImageOps

# =============================================================================
# Configurações via Variáveis de Ambiente (.env ou Streamlit Secrets)
# =============================================================================
def _get_setting(key: str, default: str = "") -> str:
    val = os.getenv(key)
    if val is not None and val.strip() != "":
        return val.strip()
    try:
        if key in st.secrets:
            return str(st.secrets[key]).strip()
    except Exception:
        pass
    return default


BACKEND_URL: str = _get_setting("BACKEND_URL", "http://localhost:8000").rstrip("/")
GDRIVE_FOLDER_URL: str = _get_setting("GDRIVE_FOLDER_URL", "")
GITHUB_URL: str = _get_setting("GITHUB_URL", "https://github.com/viniciusscience")
CONTACT_EMAIL: str = _get_setting("CONTACT_EMAIL", "jose.8797080@edu.univali.br")
CONTACT_URL: str = _get_setting("CONTACT_URL", f"mailto:{CONTACT_EMAIL}")
SUPPORT_URL: str = _get_setting("SUPPORT_URL", "")
PIX_KEY: str = _get_setting("PIX_KEY", "")
PIX_PAYLOAD: str = _get_setting("PIX_PAYLOAD", "")
if not PIX_PAYLOAD and PIX_KEY.startswith("000201"):
    PIX_PAYLOAD = PIX_KEY
    PIX_KEY = ""

AUTHOR_NAME: str = "José Vinícius da Silva de Souza"
COAUTHOR_NAME: str = _get_setting("COAUTHOR_NAME", "Prof. Dr. Rodrigo Sant'Ana")
INSTITUTION_NAME: str = "UNIVALI · Universidade do Vale do Itajaí"
LAB_NAME: str = "LEMA · Laboratório de Estudos Marinhos Aplicados"
RESEARCH_TITLE: str = "Pesquisa de Mestrado em Computação Aplicada · Modelo Deep Learning para Identificação de Espécies de Peixes"

SPECIES_CATALOG_FALLBACK: list[dict[str, str]] = [
    {"scientific": "Coryphaena hippurus", "common_pt": "Dourado-do-mar", "group": "Pelágico"},
    {"scientific": "Istiophorus platypterus", "common_pt": "Agulhão-vela (Peixe-vela)", "group": "Peixe de bico"},
    {"scientific": "Kajikia albida", "common_pt": "Agulhão-branco (Marlim-branco)", "group": "Peixe de bico"},
    {"scientific": "Katsuwonus pelamis", "common_pt": "Bonito-listrado", "group": "Atum"},
    {"scientific": "Makaira nigricans", "common_pt": "Agulhão-negro (Marlim-azul)", "group": "Peixe de bico"},
    {"scientific": "Tetrapturus pfluegeri", "common_pt": "Agulhão-verde (Bico-longo)", "group": "Peixe de bico"},
    {"scientific": "Thunnus alalunga", "common_pt": "Albacora-branca", "group": "Atum"},
    {"scientific": "Thunnus albacares", "common_pt": "Albacora-laje", "group": "Atum"},
    {"scientific": "Thunnus obesus", "common_pt": "Albacora-bandolim", "group": "Atum"},
    {"scientific": "Xiphias gladius", "common_pt": "Espadarte (Meca)", "group": "Peixe de bico"},
]

# =============================================================================
# Internacionalização (PT-BR · EN · ES)
# =============================================================================
LANG_OPTIONS: list[tuple[str, str, str]] = [
    ("pt", "PT", "🇧🇷 Português"),
    ("en", "EN", "🇺🇸 English"),
    ("es", "ES", "🇪🇸 Español"),
]

SPECIES_I18N: dict[str, dict[str, str]] = {
    "coryphaena hippurus": {
        "pt": "Dourado-do-mar",
        "en": "Mahi-mahi (Dolphinfish)",
        "es": "Dorado (Llampuqa)",
    },
    "istiophorus platypterus": {
        "pt": "Agulhão-vela (Peixe-vela)",
        "en": "Sailfish",
        "es": "Pez vela",
    },
    "kajikia albida": {
        "pt": "Agulhão-branco (Marlim-branco)",
        "en": "White Marlin",
        "es": "Aguja blanca (Marlín blanco)",
    },
    "katsuwonus pelamis": {
        "pt": "Bonito-listrado",
        "en": "Skipjack Tuna",
        "es": "Barrilete (Listado)",
    },
    "makaira nigricans": {
        "pt": "Agulhão-negro (Marlim-azul)",
        "en": "Atlantic Blue Marlin",
        "es": "Aguja azul (Marlín azul)",
    },
    "tetrapturus pfluegeri": {
        "pt": "Agulhão-verde (Bico-longo)",
        "en": "Longbill Spearfish",
        "es": "Aguja picuda",
    },
    "thunnus alalunga": {
        "pt": "Albacora-branca",
        "en": "Albacore Tuna",
        "es": "Atún blanco (Albacora)",
    },
    "thunnus albacares": {
        "pt": "Albacora-laje",
        "en": "Yellowfin Tuna",
        "es": "Atún aleta amarilla (Rabil)",
    },
    "thunnus obesus": {
        "pt": "Albacora-bandolim",
        "en": "Bigeye Tuna",
        "es": "Atún patudo (Ojo grande)",
    },
    "xiphias gladius": {
        "pt": "Espadarte (Meca)",
        "en": "Swordfish",
        "es": "Pez espada",
    },
}

GROUP_I18N: dict[str, dict[str, str]] = {
    "pelágico": {"pt": "Pelágico", "en": "Pelagic", "es": "Pelágico"},
    "peixe de bico": {"pt": "Peixe de bico", "en": "Billfish", "es": "Pez de pico"},
    "atum": {"pt": "Atum", "en": "Tuna", "es": "Atún"},
    "marinho": {"pt": "Marinho", "en": "Marine", "es": "Marino"},
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "pt": {
        "nav_support": "☕ Apoie a Pesquisa",
        "nav_about": "📖 Sobre & ODS",
        "nav_lang_title": "Idioma / Language",
        "support_title": "#### ☕ Pague um café para a pesquisa!",
        "support_body": "Mestrando sobrevive à base de **café e horas de GPU**! Apoie a pesquisa aberta de **{author}** (UNIVALI · LEMA) em IA marinha (**ODS 14**).",
        "pix_scan": "Escaneie com o app do seu banco (Pix)",
        "pix_sub": "{author} · Mestrado em Computação Aplicada · UNIVALI",
        "pix_copy_label": "**Pix Copia e Cola** *(clique no ícone à direita para copiar)*:",
        "pix_key_label": "**Chave Pix (e-mail):**",
        "support_ext_btn": "☕ Apoiar via link externo",
        "support_missing": "Defina `PIX_PAYLOAD`, `PIX_KEY` ou `SUPPORT_URL` no arquivo `.env` para habilitar o apoio aqui.",
        "about_coauthor": "Coautor e Orientador",
        "about_institution": "Instituição",
        "about_lab": "Laboratório",
        "about_lab_val": "LEMA · Laboratório de Estudos Marinhos Aplicados",
        "about_research_title": "Pesquisa de Mestrado em Computação Aplicada · Modelo Deep Learning para Identificação de Espécies de Peixes",
        "about_desc": "Pesquisa aplicada em visão computacional e redes neurais profundas (*Deep Learning*) voltada à identificação automatizada de grandes peixes migratórios, monitoramento pesqueiro e ciência cidadã.",
        "about_sdg_heading": "#### 🌊 Objetivos de Desenvolvimento Sustentável (ONU)",
        "about_sdg_list": (
            "- **ODS 14 — Vida na Água:** conservação e uso sustentável dos oceanos e recursos marinhos.\n"
            "- **ODS 9 — Indústria, Inovação e Infraestrutura:** IA aplicada e acessível para o setor pesqueiro.\n"
            "- **ODS 12 — Consumo e Produção Responsáveis:** apoio à rastreabilidade do pescado."
        ),
        "about_bib_heading": "#### 📚 Bibliografia de Referência",
        "about_open_bases": "- **Bases abertas:** iNaturalist & FishBase.",
        "hero_pill_brand": "Mestrado em Computação Aplicada · UNIVALI",
        "hero_pill_ods": "ODS 14 · Vida na Água (ONU)",
        "hero_pill_tech": "Deep Learning & Visão Computacional",
        "hero_pill_em": "Monitoramento Eletrônico (EM)",
        "hero_status_online": "Sistema Online",
        "hero_title": "Identificação Inteligente de Espécies Marinhas",
        "hero_author_prefix": "Autor",
        "hero_coauthor_prefix": "Coautor & Orientador",
        "hero_desc_rest": "Fotografe pelo celular, envie uma imagem ou analise vídeos para reconhecer grandes peixes migratórios em segundos.",
        "hero_inst_label": "Instituição & Laboratório",
        "hero_inst_sub": "UNIVALI · Laboratório de Estudos Marinhos Aplicados",
        "stat_species_val": "{n} Espécies",
        "stat_species_lbl": "Atuns, peixes de bico e pelágicos",
        "stat_realtime_val": "Tempo Real",
        "stat_realtime_lbl": "Identificação por foto e vídeo",
        "stat_em_val": "Monitoramento (EM)",
        "stat_em_lbl": "Contagem e biometria no convés",
        "stat_dl_val": "Deep Learning",
        "stat_dl_lbl": "Visão computacional aplicada",
        "stat_open_lbl": "Ciência aberta · Agenda 2030",
        "footer_degree": "Mestrado em Computação Aplicada",
        "tab_photo": "📷 Identificar Imagem (Espécie)",
        "tab_video": "🎥 Vídeo Rápido (Espécie)",
        "tab_em": "📊 Monitoramento de Convés (EM)",
        "catalog_hide": "▲ Ocultar as {n} espécies reconhecidas hoje",
        "catalog_show": "🐠 Ver as {n} espécies que o sistema identifica hoje  ▾",
        "catalog_eyebrow": "Espécies identificadas atualmente ({n})",
        "cta_title": "Quer que o FishID Studio identifique mais espécies?",
        "cta_sub": "Sua empresa ou projeto precisa reconhecer outras espécies marinhas? Entre em contato com {author}!",
        "cta_btn": "✉️ Entre em contato",
        "mode_carousel": "🐠 Carrossel de Espécies",
        "mode_camera": "📸 Câmera (Celular)",
        "mode_upload": "📁 Enviar Foto",
        "gallery_header": "Galeria de Espécies · Clique para identificar",
        "gallery_error": "Não foi possível carregar a galeria de exemplos no momento.",
        "gallery_filter_label": "Filtrar por espécie",
        "gallery_all": "Todas as espécies",
        "gallery_shuffle": "🔀 Sortear",
        "gallery_empty": "Nenhuma foto encontrada para esse filtro.",
        "gallery_img_unavail": "Imagem indisponível",
        "gallery_identify": "Identificar · {name}",
        "gallery_open_err": "Erro ao abrir {filename}",
        "gallery_prev": "◀ Anterior",
        "gallery_next": "Próxima ▶",
        "gallery_page": "Página {page} de {total}",
        "camera_tip": "📱 <strong>Captura mobile:</strong> centralize o peixe inteiro com boa iluminação e clique para fotografar. A espécie aparece automaticamente abaixo.",
        "camera_input": "Fotografar peixe",
        "upload_label": "Arraste uma foto aqui ou toque para selecionar (JPG, PNG ou WEBP)",
        "preview_eyebrow": "Pré-visualização",
        "empty_photo_title": "Pronto para identificar 🐟",
        "empty_photo_sub": "Escolha uma espécie no carrossel acima, abra a câmera do celular ou envie uma foto do seu dispositivo.",
        "result_eyebrow": "Espécie identificada",
        "result_mode": "IA Marinha · Deep Learning",
        "conf_high": "Confiança alta",
        "conf_high_guide": "Padrões morfológicos bem definidos para esta espécie.",
        "conf_mid": "Confiança moderada",
        "conf_mid_guide": "Boa identificação inicial. Fotos laterais com boa luz aumentam ainda mais a precisão.",
        "conf_low": "Confiança baixa · tente outro ângulo",
        "conf_low_guide": "Iluminação ou enquadramento pode estar dificultando a leitura. Tente fotografar o peixe inteiro.",
        "meta_response": "Resposta",
        "meta_model": "Modelo",
        "meta_resolution": "Resolução",
        "contrib_eyebrow": "🤝 Aprendizado contínuo · Ajude a IA a evoluir",
        "contrib_caption": "Autorize o envio desta foto para o banco científico do mestrado — você ajuda a melhorar a acurácia e adicionar novas espécies ao portfólio.",
        "contrib_success": "Foto enviada com sucesso para a pesquisa (ID `{sample_id}` · destino `{backend}`). Obrigado por contribuir!",
        "contrib_offline": "Conecte o backend para ativar o salvamento automático no storage configurado.",
        "contrib_ok_btn": "✅ Acertou! Enviar para pesquisa",
        "contrib_fix_btn": "✏️ Corrigir / Nova espécie",
        "contrib_other_opt": "➕ Outra espécie (nova no catálogo)",
        "contrib_select": "Qual é a espécie correta?",
        "contrib_custom_lbl": "Digite o nome popular ou científico:",
        "contrib_custom_ph": "Ex.: Garoupa-verdadeira (Epinephelus marginatus)",
        "contrib_send_fix": "Enviar correção para pesquisa",
        "contrib_warn_empty": "Informe o nome da espécie antes de enviar.",
        "contrib_save_err": "Não foi possível salvar agora: {exc}",
        "video_upload": "Envie um vídeo curto de peixes (MP4 ou MOV)",
        "video_slider": "Frequência da análise (classificar a cada N frames)",
        "video_run_btn": "▶ Processar vídeo",
        "video_err": "Falha ao processar o vídeo: {exc}",
        "video_prog_start": "Analisando frames do vídeo...",
        "video_prog_frame": "Analisando frame {idx} de {total}...",
        "video_prog_h264": "Convertendo vídeo para H.264...",
        "video_prog_done": "Vídeo pronto!",
        "video_annotated_eyebrow": "Vídeo anotado (H.264)",
        "video_predom_eyebrow": "Espécie predominante no vídeo",
        "video_meta_frames": "Frames analisados",
        "video_meta_dur": "Duração / FPS",
        "video_meta_lat": "Latência média",
        "video_summary_eyebrow": "Resumo por espécie",
        "video_col_species": "Espécie",
        "video_col_frames": "Frames analisados",
        "video_col_share": "Participação (%)",
        "video_col_avg_conf": "Confiança média (%)",
        "video_col_max_conf": "Confiança máxima (%)",
        "video_download": "⬇ Baixar vídeo anotado (MP4)",
        "video_empty_title": "Análise automática em vídeo 🎥",
        "video_empty_sub": "Envie um arquivo MP4 ou MOV acima para anotar cada cena automaticamente e baixar o resultado.",
    },
    "en": {
        "nav_support": "☕ Support Research",
        "nav_about": "📖 About & SDGs",
        "nav_lang_title": "Language / Idioma",
        "support_title": "#### ☕ Buy a coffee for research!",
        "support_body": "A graduate researcher runs on **coffee and GPU hours**! Support **{author}**'s open-science research (UNIVALI · LEMA) in marine AI (**SDG 14**).",
        "pix_scan": "Scan with your Brazilian banking app (Pix)",
        "pix_sub": "{author} · M.Sc. in Applied Computing · UNIVALI",
        "pix_copy_label": "**Pix Copy & Paste** *(click the icon on the right to copy)*:",
        "pix_key_label": "**Pix Key (email):**",
        "support_ext_btn": "☕ Support via external link",
        "support_missing": "Set `PIX_PAYLOAD`, `PIX_KEY`, or `SUPPORT_URL` in `.env` to enable support links here.",
        "about_coauthor": "Co-author & Advisor",
        "about_institution": "Institution",
        "about_lab": "Laboratory",
        "about_lab_val": "LEMA · Laboratory of Applied Marine Studies",
        "about_research_title": "M.Sc. Research in Applied Computing · Deep Learning Model for Marine Fish Species Identification",
        "about_desc": "Applied computer vision and deep neural networks (*Deep Learning*) research dedicated to automated identification of large migratory fish, fisheries monitoring, and citizen science.",
        "about_sdg_heading": "#### 🌊 UN Sustainable Development Goals",
        "about_sdg_list": (
            "- **SDG 14 — Life Below Water:** conservation and sustainable use of oceans and marine resources.\n"
            "- **SDG 9 — Industry, Innovation and Infrastructure:** accessible applied AI for the fisheries sector.\n"
            "- **SDG 12 — Responsible Consumption and Production:** supporting seafood traceability."
        ),
        "about_bib_heading": "#### 📚 Reference Bibliography",
        "about_open_bases": "- **Open datasets:** iNaturalist & FishBase.",
        "hero_pill_brand": "M.Sc. in Applied Computing · UNIVALI",
        "hero_pill_ods": "SDG 14 · Life Below Water (UN)",
        "hero_pill_tech": "Deep Learning & Computer Vision",
        "hero_pill_em": "Electronic Monitoring (EM)",
        "hero_status_online": "System Online",
        "hero_title": "Intelligent Marine Species Identification",
        "hero_author_prefix": "Author",
        "hero_coauthor_prefix": "Co-author & Advisor",
        "hero_desc_rest": "Take a photo on your phone, upload an image, or analyze videos to recognize large migratory fish in seconds.",
        "hero_inst_label": "Institution & Laboratory",
        "hero_inst_sub": "UNIVALI · Laboratory of Applied Marine Studies (LEMA)",
        "stat_species_val": "{n} Species",
        "stat_species_lbl": "Tunas, billfish, and pelagics",
        "stat_realtime_val": "Real-Time",
        "stat_realtime_lbl": "Photo and video identification",
        "stat_em_val": "Monitoring (EM)",
        "stat_em_lbl": "Deck counting and morphometry",
        "stat_dl_val": "Deep Learning",
        "stat_dl_lbl": "Applied computer vision",
        "stat_open_lbl": "Open science · Agenda 2030",
        "footer_degree": "M.Sc. in Applied Computing",
        "tab_photo": "📷 Identify Image (Species)",
        "tab_video": "🎥 Quick Video (Species)",
        "tab_em": "📊 Deck Monitoring (EM)",
        "catalog_hide": "▲ Hide the {n} currently recognized species",
        "catalog_show": "🐠 View the {n} species currently identified by the system  ▾",
        "catalog_eyebrow": "Currently identified species ({n})",
        "cta_title": "Want FishID Studio to identify more species?",
        "cta_sub": "Does your organization or project need to recognize other marine species? Contact {author}!",
        "cta_btn": "✉️ Contact us",
        "mode_carousel": "🐠 Species Carousel",
        "mode_camera": "📸 Camera (Mobile)",
        "mode_upload": "📁 Upload Photo",
        "gallery_header": "Species Gallery · Click to identify",
        "gallery_error": "Unable to load the sample gallery right now.",
        "gallery_filter_label": "Filter by species",
        "gallery_all": "All species",
        "gallery_shuffle": "🔀 Shuffle",
        "gallery_empty": "No photos found for this filter.",
        "gallery_img_unavail": "Image unavailable",
        "gallery_identify": "Identify · {name}",
        "gallery_open_err": "Error opening {filename}",
        "gallery_prev": "◀ Previous",
        "gallery_next": "Next ▶",
        "gallery_page": "Page {page} of {total}",
        "camera_tip": "📱 <strong>Mobile capture:</strong> center the entire fish under good lighting and tap to shoot. The species appears automatically below.",
        "camera_input": "Photograph fish",
        "upload_label": "Drag a photo here or tap to browse (JPG, PNG, or WEBP)",
        "preview_eyebrow": "Preview",
        "empty_photo_title": "Ready to identify 🐟",
        "empty_photo_sub": "Pick a species from the carousel above, open your mobile camera, or upload a photo from your device.",
        "result_eyebrow": "Identified species",
        "result_mode": "Marine AI · Deep Learning",
        "conf_high": "High confidence",
        "conf_high_guide": "Well-defined morphological patterns for this species.",
        "conf_mid": "Moderate confidence",
        "conf_mid_guide": "Good initial match. Well-lit lateral photos further improve accuracy.",
        "conf_low": "Low confidence · try another angle",
        "conf_low_guide": "Lighting or framing may be affecting recognition. Try capturing the full fish.",
        "meta_response": "Latency",
        "meta_model": "Model",
        "meta_resolution": "Resolution",
        "contrib_eyebrow": "🤝 Continuous learning · Help the AI improve",
        "contrib_caption": "Authorize sharing this photo with our master's scientific dataset — helping improve accuracy and expand to new species.",
        "contrib_success": "Photo successfully sent to research (ID `{sample_id}` · target `{backend}`). Thank you for contributing!",
        "contrib_offline": "Connect the backend to enable automatic saving to the configured storage.",
        "contrib_ok_btn": "✅ Correct! Send to research",
        "contrib_fix_btn": "✏️ Correct / New species",
        "contrib_other_opt": "➕ Another species (new to catalog)",
        "contrib_select": "What is the correct species?",
        "contrib_custom_lbl": "Enter common or scientific name:",
        "contrib_custom_ph": "E.g.: Dusky grouper (Epinephelus marginatus)",
        "contrib_send_fix": "Submit correction for research",
        "contrib_warn_empty": "Please enter the species name before submitting.",
        "contrib_save_err": "Could not save right now: {exc}",
        "video_upload": "Upload a short fish video (MP4 or MOV)",
        "video_slider": "Analysis frequency (classify every N frames)",
        "video_run_btn": "▶ Process video",
        "video_err": "Failed to process video: {exc}",
        "video_prog_start": "Analyzing video frames...",
        "video_prog_frame": "Analyzing frame {idx} of {total}...",
        "video_prog_h264": "Encoding video to H.264...",
        "video_prog_done": "Video ready!",
        "video_annotated_eyebrow": "Annotated video (H.264)",
        "video_predom_eyebrow": "Predominant species in video",
        "video_meta_frames": "Analyzed frames",
        "video_meta_dur": "Duration / FPS",
        "video_meta_lat": "Avg. latency",
        "video_summary_eyebrow": "Species breakdown",
        "video_col_species": "Species",
        "video_col_frames": "Analyzed frames",
        "video_col_share": "Share (%)",
        "video_col_avg_conf": "Avg. confidence (%)",
        "video_col_max_conf": "Max confidence (%)",
        "video_download": "⬇ Download annotated video (MP4)",
        "video_empty_title": "Automated video analysis 🎥",
        "video_empty_sub": "Upload an MP4 or MOV file above to automatically annotate each scene and download the result.",
    },
    "es": {
        "nav_support": "☕ Apoyar la Investigación",
        "nav_about": "📖 Acerca y ODS",
        "nav_lang_title": "Idioma / Language",
        "support_title": "#### ☕ ¡Invita un café a la investigación!",
        "support_body": "Un investigador de maestría vive a base de **café y horas de GPU**. Apoya la investigación abierta de **{author}** (UNIVALI · LEMA) en IA marina (**ODS 14**).",
        "pix_scan": "Escanea con la app de tu banco (Pix)",
        "pix_sub": "{author} · Maestría en Computación Aplicada · UNIVALI",
        "pix_copy_label": "**Pix Copiar y Pegar** *(haz clic en el icono a la derecha para copiar)*:",
        "pix_key_label": "**Clave Pix (correo):**",
        "support_ext_btn": "☕ Apoyar mediante enlace externo",
        "support_missing": "Define `PIX_PAYLOAD`, `PIX_KEY` o `SUPPORT_URL` en `.env` para habilitar el apoyo aquí.",
        "about_coauthor": "Coautor y Director",
        "about_institution": "Institución",
        "about_lab": "Laboratorio",
        "about_lab_val": "LEMA · Laboratorio de Estudios Marinos Aplicados",
        "about_research_title": "Investigación de Maestría en Computación Aplicada · Modelo Deep Learning para Identificación de Especies de Peces",
        "about_desc": "Investigación aplicada en visión por computadora y redes neuronales profundas (*Deep Learning*) orientada a la identificación automatizada de grandes peces migratorios, monitoreo pesquero y ciencia ciudadana.",
        "about_sdg_heading": "#### 🌊 Objetivos de Desarrollo Sostenible (ONU)",
        "about_sdg_list": (
            "- **ODS 14 — Vida Submarina:** conservación y uso sostenible de los océanos y recursos marinos.\n"
            "- **ODS 9 — Industria, Innovación e Infraestructura:** IA aplicada y accesible para el sector pesquero.\n"
            "- **ODS 12 — Producción y Consumo Responsables:** apoyo a la trazabilidad pesquera."
        ),
        "about_bib_heading": "#### 📚 Bibliografía de Referencia",
        "about_open_bases": "- **Bases abiertas:** iNaturalist y FishBase.",
        "hero_pill_brand": "Maestría en Computación Aplicada · UNIVALI",
        "hero_pill_ods": "ODS 14 · Vida Submarina (ONU)",
        "hero_pill_tech": "Deep Learning y Visión por Computadora",
        "hero_pill_em": "Monitoreo Electrónico (EM)",
        "hero_status_online": "Sistema en Línea",
        "hero_title": "Identificación Inteligente de Especies Marinas",
        "hero_author_prefix": "Autor",
        "hero_coauthor_prefix": "Coautor y Director",
        "hero_desc_rest": "Fotografía con tu celular, sube una imagen o analiza videos para reconocer grandes peces migratorios en segundos.",
        "hero_inst_label": "Institución y Laboratorio",
        "hero_inst_sub": "UNIVALI · Laboratorio de Estudios Marinos Aplicados (LEMA)",
        "stat_species_val": "{n} Especies",
        "stat_species_lbl": "Atunes, peces de pico y pelágicos",
        "stat_realtime_val": "Tiempo Real",
        "stat_realtime_lbl": "Identificación por foto y video",
        "stat_em_val": "Monitoreo (EM)",
        "stat_em_lbl": "Conteo y biometría en cubierta",
        "stat_dl_val": "Deep Learning",
        "stat_dl_lbl": "Visión por computadora aplicada",
        "stat_open_lbl": "Ciencia abierta · Agenda 2030",
        "footer_degree": "Maestría en Computación Aplicada",
        "tab_photo": "📷 Identificar Imagen (Especie)",
        "tab_video": "🎥 Video Rápido (Especie)",
        "tab_em": "📊 Monitoreo de Cubierta (EM)",
        "catalog_hide": "▲ Ocultar las {n} especies reconocidas hoy",
        "catalog_show": "🐠 Ver las {n} especies que el sistema identifica hoy  ▾",
        "catalog_eyebrow": "Especies identificadas actualmente ({n})",
        "cta_title": "¿Quieres que FishID Studio identifique más especies?",
        "cta_sub": "¿Tu empresa o proyecto necesita reconocer otras especies marinas? ¡Ponte en contacto con {author}!",
        "cta_btn": "✉️ Contáctanos",
        "mode_carousel": "🐠 Carrusel de Especies",
        "mode_camera": "📸 Cámara (Celular)",
        "mode_upload": "📁 Subir Foto",
        "gallery_header": "Galería de Especies · Haz clic para identificar",
        "gallery_error": "No fue posible cargar la galería de ejemplos en este momento.",
        "gallery_filter_label": "Filtrar por especie",
        "gallery_all": "Todas las especies",
        "gallery_shuffle": "🔀 Aleatorio",
        "gallery_empty": "No se encontraron fotos para este filtro.",
        "gallery_img_unavail": "Imagen no disponible",
        "gallery_identify": "Identificar · {name}",
        "gallery_open_err": "Error al abrir {filename}",
        "gallery_prev": "◀ Anterior",
        "gallery_next": "Siguiente ▶",
        "gallery_page": "Página {page} de {total}",
        "camera_tip": "📱 <strong>Captura móvil:</strong> centra el pez completo con buena iluminación y pulsa para fotografiar. La especie aparece automáticamente abajo.",
        "camera_input": "Fotografiar pez",
        "upload_label": "Arrastra una foto aquí o pulsa para seleccionar (JPG, PNG o WEBP)",
        "preview_eyebrow": "Vista previa",
        "empty_photo_title": "Listo para identificar 🐟",
        "empty_photo_sub": "Elige una especie en el carrusel de arriba, abre la cámara del celular o sube una foto desde tu dispositivo.",
        "result_eyebrow": "Especie identificada",
        "result_mode": "IA Marina · Deep Learning",
        "conf_high": "Confianza alta",
        "conf_high_guide": "Patrones morfológicos bien definidos para esta especie.",
        "conf_mid": "Confianza moderada",
        "conf_mid_guide": "Buena identificación inicial. Fotos laterales con buena luz aumentan aún más la precisión.",
        "conf_low": "Confianza baja · prueba otro ángulo",
        "conf_low_guide": "La iluminación o el encuadre pueden dificultar la lectura. Intenta fotografiar el pez completo.",
        "meta_response": "Respuesta",
        "meta_model": "Modelo",
        "meta_resolution": "Resolución",
        "contrib_eyebrow": "🤝 Aprendizaje continuo · Ayuda a la IA a evolucionar",
        "contrib_caption": "Autoriza el envío de esta foto al banco científico de la maestría: ayudas a mejorar la precisión y añadir nuevas especies.",
        "contrib_success": "Foto enviada con éxito a la investigación (ID `{sample_id}` · destino `{backend}`). ¡Gracias por contribuir!",
        "contrib_offline": "Conecta el backend para activar el guardado automático en el almacenamiento configurado.",
        "contrib_ok_btn": "✅ ¡Acertó! Enviar a investigación",
        "contrib_fix_btn": "✏️ Corregir / Nueva especie",
        "contrib_other_opt": "➕ Otra especie (nueva en el catálogo)",
        "contrib_select": "¿Cuál es la especie correcta?",
        "contrib_custom_lbl": "Escribe el nombre común o científico:",
        "contrib_custom_ph": "Ej.: Mero pardo (Epinephelus marginatus)",
        "contrib_send_fix": "Enviar corrección a investigación",
        "contrib_warn_empty": "Indica el nombre de la especie antes de enviar.",
        "contrib_save_err": "No se pudo guardar ahora: {exc}",
        "video_upload": "Sube un video corto de peces (MP4 o MOV)",
        "video_slider": "Frecuencia del análisis (clasificar cada N cuadros)",
        "video_run_btn": "▶ Procesar video",
        "video_err": "Error al procesar el video: {exc}",
        "video_prog_start": "Analizando cuadros del video...",
        "video_prog_frame": "Analizando cuadro {idx} de {total}...",
        "video_prog_h264": "Convirtiendo video a H.264...",
        "video_prog_done": "¡Video listo!",
        "video_annotated_eyebrow": "Video anotado (H.264)",
        "video_predom_eyebrow": "Especie predominante en el video",
        "video_meta_frames": "Cuadros analizados",
        "video_meta_dur": "Duración / FPS",
        "video_meta_lat": "Latencia media",
        "video_summary_eyebrow": "Resumen por especie",
        "video_col_species": "Especie",
        "video_col_frames": "Cuadros analizados",
        "video_col_share": "Participación (%)",
        "video_col_avg_conf": "Confianza media (%)",
        "video_col_max_conf": "Confianza máxima (%)",
        "video_download": "⬇ Descargar video anotado (MP4)",
        "video_empty_title": "Análisis automático en video 🎥",
        "video_empty_sub": "Sube un archivo MP4 o MOV arriba para anotar cada escena automáticamente y descargar el resultado.",
    },
}


def get_lang() -> str:
    lang = str(st.session_state.get("lang", "pt")).lower()
    return lang if lang in TRANSLATIONS else "pt"


def t(key: str, **kwargs: Any) -> str:
    lang = get_lang()
    text = TRANSLATIONS.get(lang, TRANSLATIONS["pt"]).get(key, TRANSLATIONS["pt"].get(key, key))
    return text.format(**kwargs) if kwargs else text


def get_species_common(scientific: str, fallback: str = "") -> str:
    lang = get_lang()
    sci_key = (scientific or "").strip().lower()
    if sci_key in SPECIES_I18N:
        return SPECIES_I18N[sci_key].get(lang, fallback or SPECIES_I18N[sci_key]["pt"])
    return fallback or scientific


def get_species_group(group_pt: str) -> str:
    lang = get_lang()
    key = (group_pt or "").strip().lower()
    if key in GROUP_I18N:
        return GROUP_I18N[key].get(lang, group_pt)
    return group_pt

ASSETS_DIR: Path = Path(__file__).resolve().parent / "assets"
BG_FISH_DIR: Path = ASSETS_DIR / "bg"
LOGOS_DIR: Path = ASSETS_DIR / "logos"
GDRIVE_CACHE_ROOT: Path = Path("/tmp/fishid_gdrive_samples")
MAX_GDRIVE_SAMPLES: int = 6
SUPPORTED_IMAGE_EXTS: set[str] = {".jpg", ".jpeg", ".png", ".webp"}

st.set_page_config(
    page_title="FishID Studio · Inteligência Artificial Marinha",
    page_icon="🐟",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =============================================================================
# Fundo oceânico sutil + Design System SaaS Executivo (Stripe / Linear / Marine-Tech)
# =============================================================================
@st.cache_resource
def load_real_bg_fish_pngs() -> dict[str, str]:
    """Carrega sprites fotorrealistas transparentes (PNG) de grandes peixes pelágicos."""
    fish_uris: dict[str, str] = {}
    if not BG_FISH_DIR.exists():
        return fish_uris
    for png_path in sorted(BG_FISH_DIR.glob("*_real.png")):
        try:
            encoded = base64.b64encode(png_path.read_bytes()).decode("ascii")
            fish_uris[png_path.stem] = f"data:image/png;base64,{encoded}"
        except OSError:
            continue
    return fish_uris


@st.cache_resource
def load_institutional_logos() -> dict[str, str]:
    """Carrega as logos institucionais (UNIVALI e LEMA) em base64 para exibição nítida."""
    logos: dict[str, str] = {}
    if not LOGOS_DIR.exists():
        return logos
    for key, filename in (("univali", "univali_logo.png"), ("lema", "lema_logo.png")):
        logo_path = LOGOS_DIR / filename
        if logo_path.is_file():
            try:
                encoded = base64.b64encode(logo_path.read_bytes()).decode("ascii")
                logos[key] = f"data:image/png;base64,{encoded}"
            except OSError:
                continue
    return logos


def inject_enterprise_css() -> None:
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&family=Inter:wght@400;500;600&display=swap');

            html, body, [class*="css"] {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                color: #0F172A;
                -webkit-font-smoothing: antialiased;
            }

            h1, h2, h3, .hero-title, .result-species {
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
            }

            .stApp {
                background: radial-gradient(1100px 520px at 10% -5%, rgba(14, 165, 233, 0.08), transparent 60%),
                            radial-gradient(900px 480px at 92% 4%, rgba(10, 56, 92, 0.08), transparent 60%),
                            linear-gradient(180deg, #F6FAFC 0%, #F8FAFC 55%, #EFF6FA 100%) !important;
                background-attachment: fixed;
            }

            [data-testid="stAppViewContainer"],
            [data-testid="stMain"] {
                background: transparent !important;
            }

            /* Oculta completamente a barra nativa do Streamlit (botão Deploy e toolbar) */
            [data-testid="stHeader"],
            [data-testid="stToolbar"],
            [data-testid="stAppDeployButton"],
            [data-testid="stDecoration"],
            header[data-testid="stHeader"] {
                display: none !important;
                height: 0 !important;
                visibility: hidden !important;
            }

            #MainMenu, footer { visibility: hidden; }

            [data-testid="stMainBlockContainer"] {
                max-width: 1180px;
                padding-top: 4.85rem !important;
                padding-bottom: 3.5rem;
            }

            [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"] {
                position: relative;
                z-index: 2;
            }

            /* ================= MODAL FULLSCREEN DE FOTOS (ACIMA DE TUDO, SEM BUG) ================= */
            .stApp:has(button[aria-label="Close fullscreen"]) .st-key-top_navbar,
            .stApp:has(button[aria-label="Close fullscreen"]) [data-testid="stElementContainer"]:has(.st-key-top_navbar) {
                opacity: 0 !important;
                pointer-events: none !important;
                z-index: 1 !important;
            }

            [data-testid="stElementContainer"]:has(button[aria-label="Close fullscreen"]),
            [data-testid="stColumn"]:has(button[aria-label="Close fullscreen"]),
            [data-testid="stHorizontalBlock"]:has(button[aria-label="Close fullscreen"]),
            [data-testid="stVerticalBlock"]:has(button[aria-label="Close fullscreen"]),
            [data-testid="stVerticalBlockBorderWrapper"]:has(button[aria-label="Close fullscreen"]),
            [data-testid="stTabs"]:has(button[aria-label="Close fullscreen"]),
            [data-testid="stTabPanel"]:has(button[aria-label="Close fullscreen"]) {
                z-index: 99998 !important;
                backdrop-filter: none !important;
                -webkit-backdrop-filter: none !important;
                transform: none !important;
                filter: none !important;
            }

            [data-testid="stFullScreenFrame"]:has(button[aria-label="Close fullscreen"]) {
                position: fixed !important;
                inset: 0 !important;
                width: 100vw !important;
                height: 100vh !important;
                z-index: 99999 !important;
                background: rgba(4, 20, 32, 0.94) !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                padding: 1.5rem !important;
            }

            [data-testid="stFullScreenFrame"]:has(button[aria-label="Close fullscreen"]) button[aria-label="Close fullscreen"] {
                position: fixed !important;
                top: 16px !important;
                right: 16px !important;
                z-index: 100000 !important;
                width: 42px !important;
                height: 42px !important;
                border-radius: 999px !important;
                background: #FFFFFF !important;
                color: #0F172A !important;
                border: 2px solid #0A385C !important;
                box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45) !important;
                cursor: pointer !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
            }

            [data-testid="stFullScreenFrame"]:has(button[aria-label="Close fullscreen"]) button[aria-label="Close fullscreen"]:hover {
                background: #F0F7FC !important;
                transform: scale(1.06) !important;
            }

            [data-testid="stMainBlockContainer"] [data-testid="stElementContainer"]:has(.ocean-bg),
            [data-testid="stMainBlockContainer"] [data-testid="stElementContainer"]:has(> div > style),
            [data-testid="stMainBlockContainer"] [data-testid="stElementContainer"]:has(style) {
                position: absolute !important;
                top: 0 !important;
                left: 0 !important;
                width: 0 !important;
                height: 0 !important;
                z-index: 0 !important;
                margin: 0 !important;
                padding: 0 !important;
                pointer-events: none !important;
            }

            /* Aquário WebGL (PixiJS v8) fixo em tela cheia atrás de toda a interface */
            [data-testid="stMainBlockContainer"] [data-testid="stElementContainer"]:has(.st-key-aquarium_bg_host),
            .st-key-aquarium_bg_host,
            .st-key-aquarium_bg_host [data-testid="stElementContainer"],
            .st-key-aquarium_bg_host [data-testid="stIFrame"],
            .st-key-aquarium_bg_host iframe {
                position: fixed !important;
                top: 0 !important;
                left: 0 !important;
                right: 0 !important;
                bottom: 0 !important;
                width: 100vw !important;
                height: 100vh !important;
                z-index: 0 !important;
                pointer-events: none !important;
                border: none !important;
                margin: 0 !important;
                padding: 0 !important;
                background: transparent !important;
            }

            [data-testid="stMainBlockContainer"] [data-testid="stElementContainer"]:has(.st-key-top_navbar) {
                position: static !important;
                z-index: auto !important;
                margin: 0 !important;
                padding: 0 !important;
                height: 0 !important;
            }

            /* ================= AQUÁRIO CINEMATOGRÁFICO (RAIOS DE SOL + PROFUNDIDADE) ================= */
            .ocean-bg {
                position: fixed;
                inset: 0;
                z-index: 0;
                pointer-events: none;
                overflow: hidden;
            }

            .aqua-rays {
                position: absolute;
                top: -18%;
                left: -15%;
                width: 130%;
                height: 62%;
                background:
                    conic-gradient(from 155deg at 22% 0%, transparent 0deg, rgba(14, 165, 233, 0.11) 14deg, transparent 28deg, rgba(14, 116, 155, 0.09) 42deg, transparent 58deg),
                    conic-gradient(from 165deg at 74% 0%, transparent 0deg, rgba(14, 116, 155, 0.09) 16deg, transparent 34deg, rgba(56, 189, 248, 0.09) 48deg, transparent 65deg);
                animation: raySway 18s ease-in-out infinite alternate;
                filter: blur(4px);
            }

            @keyframes raySway {
                0% { transform: translateX(-2%) rotate(-1.5deg); opacity: 0.72; }
                100% { transform: translateX(2.5%) rotate(1.5deg); opacity: 1; }
            }

            .aqua-floor-wave {
                position: absolute;
                bottom: -24px;
                left: -6%;
                width: 112%;
                height: 92px;
                border-radius: 50% 50% 0 0 / 38px 38px 0 0;
                background: linear-gradient(180deg, rgba(10, 56, 92, 0.08), rgba(6, 33, 53, 0.03));
                animation: floorWave 13s ease-in-out infinite alternate;
            }

            .aqua-floor-wave-2 {
                bottom: -34px;
                height: 84px;
                background: linear-gradient(180deg, rgba(14, 165, 233, 0.08), rgba(10, 56, 92, 0.02));
                animation: floorWave 17s ease-in-out infinite alternate-reverse;
            }

            @keyframes floorWave {
                0% { transform: translateX(-2.5%) translateY(0); }
                100% { transform: translateX(2.5%) translateY(7px); }
            }

            .fish-lane {
                position: absolute;
                left: 0;
                will-change: transform;
                pointer-events: none;
            }

            .fish-ltr { animation: swimLTR var(--dur, 34s) linear var(--delay, 0s) infinite; }
            .fish-rtl { animation: swimRTL var(--dur, 36s) linear var(--delay, 0s) infinite; }
            .fish-bob { animation: gentleBob var(--bob-dur, 5s) ease-in-out infinite alternate; }
            .fish-rtl .fish-flip { transform: scaleX(-1); }

            .fish-sprite {
                display: block;
                width: var(--w, 116px);
                height: auto;
                opacity: var(--op, 0.32);
                filter: blur(var(--blur, 0px)) drop-shadow(0 8px 16px rgba(6, 40, 61, 0.14));
                user-select: none;
            }

            @keyframes swimLTR {
                0% { transform: translateX(-200px); }
                100% { transform: translateX(calc(100vw + 200px)); }
            }

            @keyframes swimRTL {
                0% { transform: translateX(calc(100vw + 200px)); }
                100% { transform: translateX(-200px); }
            }

            @keyframes gentleBob {
                0% { transform: translateY(-6px) rotate(-1.2deg); }
                100% { transform: translateY(6px) rotate(1.2deg); }
            }

            .ocean-bubble {
                position: absolute;
                bottom: -30px;
                left: var(--x, 50%);
                width: var(--s, 9px);
                height: var(--s, 9px);
                border-radius: 50%;
                background: radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.9), rgba(14, 165, 233, 0.14));
                border: 1px solid rgba(10, 56, 92, 0.14);
                animation: bubbleRise var(--bdur, 16s) ease-in var(--bdelay, 0s) infinite;
            }

            @keyframes bubbleRise {
                0% { transform: translateY(0) translateX(0) scale(0.75); opacity: 0; }
                15% { opacity: 0.5; }
                50% { transform: translateY(-50vh) translateX(10px) scale(1); }
                88% { opacity: 0.35; }
                100% { transform: translateY(-106vh) translateX(-8px) scale(1.08); opacity: 0; }
            }

            /* ================= EXECUTIVE HERO BANNER (PALETA OCEÂNICA UNIFICADA) ================= */
            .exec-hero {
                position: relative;
                overflow: hidden;
                border-radius: 20px;
                padding: 1.65rem 2rem 1.5rem 2rem;
                margin-top: 0.25rem;
                margin-bottom: 1.05rem;
                background:
                    radial-gradient(620px 260px at 88% 12%, rgba(56, 189, 248, 0.16), transparent 65%),
                    radial-gradient(480px 260px at 14% 95%, rgba(14, 165, 233, 0.14), transparent 65%),
                    linear-gradient(135deg, #051D33 0%, #0A385C 55%, #0E5673 100%);
                color: #FFFFFF;
                box-shadow: 0 20px 44px rgba(5, 29, 51, 0.22), 0 2px 6px rgba(5, 29, 51, 0.12);
                border: 1px solid rgba(255, 255, 255, 0.14);
            }

            .hero-top-row {
                display: flex;
                align-items: center;
                justify-content: space-between;
                flex-wrap: wrap;
                gap: 0.65rem;
                margin-bottom: 0.95rem;
            }

            .hero-pills {
                display: flex;
                align-items: center;
                flex-wrap: wrap;
                gap: 0.45rem;
            }

            .pill-brand,
            .pill-ods,
            .pill-tech,
            .pill-em {
                display: inline-flex;
                align-items: center;
                gap: 0.35rem;
                background: rgba(255, 255, 255, 0.10);
                border: 1px solid rgba(255, 255, 255, 0.20);
                backdrop-filter: blur(8px);
                color: #E6F2F8;
                padding: 0.26rem 0.74rem;
                border-radius: 999px;
                font-size: 0.73rem;
                font-weight: 600;
                letter-spacing: 0.02em;
            }

            .pill-brand {
                font-weight: 700;
                letter-spacing: 0.03em;
                text-transform: uppercase;
                background: rgba(255, 255, 255, 0.14);
                color: #FFFFFF;
            }

            .pill-em {
                font-weight: 700;
                background: rgba(16, 185, 129, 0.22);
                border-color: rgba(110, 231, 183, 0.45);
                color: #ECFDF5;
            }

            .pill-status {
                display: inline-flex;
                align-items: center;
                gap: 0.42rem;
                background: rgba(5, 29, 51, 0.50);
                border: 1px solid rgba(255, 255, 255, 0.18);
                color: #E2E8F0;
                padding: 0.28rem 0.75rem;
                border-radius: 999px;
                font-size: 0.76rem;
                font-weight: 600;
            }

            .dot-live { width: 8px; height: 8px; border-radius: 50%; background: #34D399; box-shadow: 0 0 0 3px rgba(52, 211, 153, 0.25); }
            .dot-demo { width: 8px; height: 8px; border-radius: 50%; background: #FBBF24; box-shadow: 0 0 0 3px rgba(251, 191, 36, 0.25); }

            .hero-title {
                font-size: 1.95rem;
                font-weight: 800;
                letter-spacing: -0.03em;
                line-height: 1.15;
                margin: 0 0 0.55rem 0;
                color: #FFFFFF;
            }

            .hero-desc {
                font-size: 0.95rem;
                line-height: 1.55;
                color: rgba(226, 240, 248, 0.90);
                max-width: 820px;
                margin: 0 0 1.1rem 0;
            }

            .hero-author-row {
                display: flex;
                align-items: center;
                flex-wrap: wrap;
                gap: 0.5rem;
                margin: 0.15rem 0 0.8rem 0;
            }

            .hero-author-badge,
            .hero-coauthor-badge {
                display: inline-flex;
                align-items: center;
                gap: 0.45rem;
                background: rgba(255, 255, 255, 0.11);
                border: 1px solid rgba(186, 230, 253, 0.34);
                color: #FFFFFF !important;
                text-decoration: none !important;
                padding: 0.34rem 0.9rem;
                border-radius: 999px;
                font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
                font-size: 0.88rem;
                font-weight: 700;
                letter-spacing: -0.01em;
                transition: transform 0.15s ease, background 0.15s ease, border-color 0.15s ease;
            }

            .hero-author-badge:hover {
                transform: translateY(-1px);
                background: rgba(255, 255, 255, 0.18);
                border-color: rgba(186, 230, 253, 0.65);
            }

            .hero-author-prefix {
                font-weight: 500;
                color: #BAE6FD;
                font-size: 0.82rem;
            }

            .hero-main-grid {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 1.4rem;
                margin-bottom: 1.05rem;
            }

            .hero-main-left {
                flex: 1 1 auto;
                min-width: 0;
            }

            .hero-main-left .hero-desc {
                margin-bottom: 0;
            }

            .hero-inst-card {
                flex: 0 0 auto;
                background: rgba(248, 252, 255, 0.96);
                border: 1px solid rgba(255, 255, 255, 0.78);
                border-radius: 16px;
                padding: 0.78rem 1.2rem 0.68rem 1.2rem;
                box-shadow: 0 12px 28px rgba(5, 29, 51, 0.26);
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 0.48rem;
                min-width: 270px;
            }

            .hero-inst-label {
                font-size: 0.66rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                color: #0A385C;
            }

            .hero-inst-logos {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 0.95rem;
            }

            .hero-logo-univali {
                height: 48px;
                width: auto;
                display: block;
                object-fit: contain;
            }

            .hero-logo-lema {
                height: 44px;
                width: auto;
                display: block;
                object-fit: contain;
            }

            .hero-inst-sep {
                width: 1px;
                height: 36px;
                background: #CBD5E1;
            }

            .hero-inst-sub {
                font-size: 0.69rem;
                font-weight: 600;
                color: #475569;
                text-align: center;
                line-height: 1.25;
            }

            .hero-stats {
                display: grid;
                grid-template-columns: repeat(5, minmax(0, 1fr));
                gap: 0.7rem;
                padding-top: 1rem;
                border-top: 1px solid rgba(255, 255, 255, 0.14);
            }

            .hero-stat {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 12px;
                padding: 0.65rem 0.85rem;
            }

            .hero-stat-val {
                font-family: 'Plus Jakarta Sans', sans-serif;
                font-size: 1.08rem;
                font-weight: 700;
                color: #FFFFFF;
                line-height: 1.2;
            }

            .hero-stat-lbl {
                font-size: 0.74rem;
                color: rgba(203, 213, 225, 0.88);
                margin-top: 0.12rem;
            }

            /* ================= BARRA DE NAVEGAÇÃO SUPERIOR FIXA (CABEÇALHO) ================= */
            .st-key-top_navbar {
                position: fixed !important;
                top: 0 !important;
                left: 0 !important;
                right: 0 !important;
                width: 100% !important;
                box-sizing: border-box !important;
                z-index: 990 !important;
                background: rgba(255, 255, 255, 0.95) !important;
                backdrop-filter: blur(18px) !important;
                -webkit-backdrop-filter: blur(18px) !important;
                border: none !important;
                border-bottom: 1px solid rgba(203, 213, 225, 0.88) !important;
                border-radius: 0 !important;
                box-shadow: 0 4px 20px rgba(4, 28, 44, 0.07) !important;
                padding: 0.48rem 1.5rem !important;
                margin: 0 !important;
            }

            .st-key-top_navbar [data-testid="stHorizontalBlock"] {
                max-width: 1180px !important;
                margin: 0 auto !important;
                width: 100% !important;
                align-items: center !important;
                gap: 0.6rem !important;
            }

            .st-key-top_navbar [data-testid="stElementContainer"] {
                margin-bottom: 0 !important;
            }

            .st-key-top_navbar button,
            .st-key-top_navbar .stLinkButton > a {
                min-height: 36px !important;
                height: 36px !important;
                padding: 0 0.85rem !important;
                font-size: 0.83rem !important;
                border-radius: 9px !important;
                white-space: nowrap !important;
                border-color: #CBD5E1 !important;
                background: rgba(248, 250, 252, 0.92) !important;
                color: #0F172A !important;
            }

            .st-key-top_navbar button:hover,
            .st-key-top_navbar .stLinkButton > a:hover {
                border-color: #0A385C !important;
                color: #0A385C !important;
                background: #F0F7FC !important;
            }

            .topnav-brand {
                display: flex;
                align-items: center;
                flex-wrap: wrap;
                gap: 0.6rem;
                min-height: 36px;
            }

            .topnav-logo {
                display: inline-flex;
                align-items: center;
                gap: 0.42rem;
                font-family: 'Plus Jakarta Sans', sans-serif;
                font-size: 1.08rem;
                font-weight: 800;
                color: #062135;
                letter-spacing: -0.025em;
                white-space: nowrap;
            }

            .topnav-divider {
                display: inline-block;
                width: 1px;
                height: 22px;
                background: #CBD5E1;
            }

            .topnav-inst-logos {
                display: inline-flex;
                align-items: center;
                gap: 0.65rem;
            }

            .topnav-inst-logo {
                display: block;
                width: auto;
                object-fit: contain;
            }

            .topnav-inst-logo-univali { height: 24px; }
            .topnav-inst-logo-lema { height: 22px; }

            .popover-inst-banner {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 0.9rem;
                background: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 12px;
                padding: 0.65rem 0.9rem;
                margin-bottom: 0.75rem;
            }

            .popover-inst-banner img.pop-univali { height: 34px; width: auto; display: block; }
            .popover-inst-banner img.pop-lema { height: 30px; width: auto; display: block; }
            .popover-inst-sep { width: 1px; height: 28px; background: #CBD5E1; }

            .inst-footer {
                margin-top: 1.75rem;
                background: rgba(255, 255, 255, 0.92);
                backdrop-filter: blur(14px);
                -webkit-backdrop-filter: blur(14px);
                border: 1px solid rgba(226, 232, 240, 0.95);
                border-radius: 16px;
                padding: 1.05rem 1.45rem;
                box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
                display: flex;
                align-items: center;
                justify-content: space-between;
                flex-wrap: wrap;
                gap: 1rem;
            }

            .inst-footer-logos {
                display: flex;
                align-items: center;
                gap: 0.95rem;
            }

            .inst-footer-univali { height: 38px; width: auto; display: block; object-fit: contain; }
            .inst-footer-lema { height: 34px; width: auto; display: block; object-fit: contain; }
            .inst-footer-sep { width: 1px; height: 30px; background: #CBD5E1; }

            .inst-footer-text {
                font-size: 0.82rem;
                color: #334155;
                line-height: 1.48;
                text-align: right;
            }

            .inst-footer-title {
                font-family: 'Plus Jakarta Sans', sans-serif;
                font-weight: 700;
                color: #062135;
                font-size: 0.88rem;
            }

            .pix-qr-card {
                background: linear-gradient(180deg, #F0F7FC 0%, #FFFFFF 100%);
                border: 1px solid #BAE6FD;
                border-radius: 14px;
                padding: 0.7rem;
                text-align: center;
                margin: 0.35rem 0 0.55rem 0;
            }

            .pix-qr-img {
                display: block;
                margin: 0 auto 0.4rem auto;
                width: 164px;
                height: 164px;
                border-radius: 10px;
                border: 1px solid #E2E8F0;
                background: #FFFFFF;
                padding: 5px;
                box-shadow: 0 4px 14px rgba(5, 29, 51, 0.08);
            }

            .pix-qr-caption {
                font-size: 0.78rem;
                font-weight: 600;
                color: #0A385C;
                line-height: 1.25;
            }

            .pix-qr-sub {
                font-size: 0.72rem;
                color: #64748B;
                margin-top: 0.12rem;
            }

            .cta-contact-box {
                margin-top: 0.9rem;
                padding: 0.9rem 1.05rem;
                border-radius: 12px;
                background: linear-gradient(135deg, #F0F7FC 0%, #EFF6FF 100%);
                border: 1px solid #BAE6FD;
                display: flex;
                align-items: center;
                justify-content: space-between;
                flex-wrap: wrap;
                gap: 0.75rem;
            }

            .cta-contact-title {
                font-size: 0.9rem;
                font-weight: 700;
                color: #062135;
            }

            .cta-contact-sub {
                font-size: 0.8rem;
                color: #475569;
                margin-top: 0.12rem;
            }

            .cta-contact-btn {
                display: inline-flex;
                align-items: center;
                gap: 0.4rem;
                background: #0A385C;
                color: #FFFFFF !important;
                text-decoration: none !important;
                font-size: 0.82rem;
                font-weight: 600;
                padding: 0.48rem 0.95rem;
                border-radius: 9px;
                box-shadow: 0 3px 10px rgba(10, 56, 92, 0.22);
            }

            .cta-contact-btn:hover {
                background: #062844;
            }

            /* ================= ABAS MODERNAS BEM ESPAÇADAS ================= */
            .stTabs [data-baseweb="tab-list"] {
                gap: 0.9rem !important;
                background: rgba(255, 255, 255, 0.92) !important;
                backdrop-filter: blur(12px);
                padding: 0.5rem 0.65rem !important;
                border-radius: 14px !important;
                border: 1px solid #E2E8F0 !important;
                box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
                margin-top: 0.5rem;
                margin-bottom: 1.2rem;
                flex-wrap: wrap;
            }

            .stTabs button[data-baseweb="tab"] {
                height: auto !important;
                min-height: 44px !important;
                padding: 0.55rem 1.35rem !important;
                margin: 0 !important;
                font-size: 0.93rem !important;
                font-weight: 600 !important;
                color: #475569 !important;
                background: #F8FAFC !important;
                border: 1px solid #E2E8F0 !important;
                border-radius: 10px !important;
                transition: all 0.16s ease;
            }

            .stTabs button[data-baseweb="tab"] p {
                margin: 0 !important;
                font-size: 0.93rem !important;
                font-weight: 600 !important;
            }

            .stTabs button[data-baseweb="tab"]:hover {
                background: #F0F7FC !important;
                color: #0A385C !important;
                border-color: #BAE6FD !important;
            }

            .stTabs button[data-baseweb="tab"][aria-selected="true"] {
                background: #0A385C !important;
                color: #FFFFFF !important;
                border-color: #0A385C !important;
                box-shadow: 0 4px 12px rgba(10, 56, 92, 0.25) !important;
            }

            .stTabs button[data-baseweb="tab"][aria-selected="true"] p {
                color: #FFFFFF !important;
            }

            .stTabs [data-baseweb="tab-highlight"],
            .stTabs [data-baseweb="tab-border"] { display: none !important; }

            /* ================= CARDS ELEVADOS DE ALTO CONTRASTE ================= */
            .studio-card {
                background: rgba(255, 255, 255, 0.89);
                backdrop-filter: blur(14px);
                -webkit-backdrop-filter: blur(14px);
                border: 1px solid rgba(226, 232, 240, 0.92);
                border-radius: 16px;
                padding: 1.35rem 1.45rem;
                box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05), 0 1px 2px rgba(15, 23, 42, 0.04);
                margin-bottom: 1rem;
            }

            [data-testid="stVerticalBlockBorderWrapper"] {
                background: rgba(255, 255, 255, 0.89) !important;
                backdrop-filter: blur(14px);
                -webkit-backdrop-filter: blur(14px);
                border: 1px solid rgba(226, 232, 240, 0.92) !important;
                border-radius: 16px !important;
                box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05), 0 1px 2px rgba(15, 23, 42, 0.04);
                padding: 0.5rem 0.65rem;
            }

            .eyebrow {
                font-size: 0.72rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.07em;
                color: #0A385C;
                margin-bottom: 0.5rem;
            }

            /* Spotlight de Resultado */
            .result-spotlight {
                background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%);
                border: 1px solid #CBD5E1;
                border-top: 4px solid #0A385C;
                border-radius: 16px;
                padding: 1.45rem 1.5rem;
                box-shadow: 0 14px 32px rgba(10, 56, 92, 0.08);
                margin-bottom: 1rem;
            }

            .result-species {
                font-size: 1.65rem;
                font-weight: 800;
                letter-spacing: -0.025em;
                color: #0F172A;
                line-height: 1.2;
                margin: 0.15rem 0 0.2rem 0;
            }

            .result-scientific {
                font-size: 0.94rem;
                font-style: italic;
                color: #475569;
                margin-bottom: 0.95rem;
            }

            .conf-bar-wrap {
                background: #F1F5F9;
                border-radius: 999px;
                height: 10px;
                overflow: hidden;
                margin: 0.45rem 0 0.75rem 0;
            }

            .conf-bar-fill {
                height: 100%;
                border-radius: 999px;
                background: linear-gradient(90deg, #0A385C 0%, #0E749B 100%);
                animation: growWidth 0.7s cubic-bezier(0.22, 1, 0.36, 1) forwards;
            }

            @keyframes growWidth { from { width: 0%; } }

            .conf-row {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 0.5rem;
                flex-wrap: wrap;
            }

            .conf-pct-big {
                font-family: 'Plus Jakarta Sans', sans-serif;
                font-size: 1.25rem;
                font-weight: 800;
                color: #0A385C;
                font-variant-numeric: tabular-nums;
            }

            .conf-pill {
                display: inline-flex;
                align-items: center;
                padding: 0.26rem 0.72rem;
                border-radius: 999px;
                font-size: 0.76rem;
                font-weight: 700;
            }

            .conf-high { background: #ECFDF5; color: #065F46; border: 1px solid #A7F3D0; }
            .conf-mid  { background: #FFFBEB; color: #92400E; border: 1px solid #FDE68A; }
            .conf-low  { background: #FEF2F2; color: #991B1B; border: 1px solid #FECACA; }

            .meta-strip {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 0.6rem;
                padding-top: 0.85rem;
                margin-top: 0.85rem;
                border-top: 1px solid #E2E8F0;
            }

            .meta-k { font-size: 0.71rem; color: #64748B; text-transform: uppercase; letter-spacing: 0.04em; font-weight: 600; }
            .meta-v { font-size: 0.9rem; font-weight: 600; color: #0F172A; margin-top: 0.1rem; font-variant-numeric: tabular-nums; }

            /* Chips das 10 espécies */
            .species-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
                gap: 0.55rem;
                margin-top: 0.35rem;
            }

            .species-item {
                background: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-left: 3px solid #0A385C;
                border-radius: 10px;
                padding: 0.55rem 0.75rem;
            }

            .species-pt { font-size: 0.85rem; font-weight: 600; color: #0F172A; line-height: 1.25; }
            .species-sci { font-size: 0.75rem; font-style: italic; color: #64748B; margin-top: 0.1rem; }
            .species-grp {
                display: inline-block;
                font-size: 0.66rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.04em;
                color: #0A385C;
                background: #F0F7FC;
                padding: 0.1rem 0.42rem;
                border-radius: 999px;
                margin-top: 0.25rem;
            }

            .spec-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(215px, 1fr));
                gap: 0.8rem;
                margin-top: 0.35rem;
            }

            .spec-box {
                background: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 12px;
                padding: 0.85rem 1rem;
            }

            .spec-label { font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #64748B; margin-bottom: 0.25rem; }
            .spec-value { font-size: 0.94rem; font-weight: 600; color: #0F172A; word-break: break-word; }

            .empty-stage {
                background: rgba(255, 255, 255, 0.86);
                border: 1.5px dashed #CBD5E1;
                border-radius: 16px;
                padding: 2rem 1.4rem;
                text-align: center;
                color: #64748B;
                margin-top: 0.6rem;
            }

            .camera-tip {
                font-size: 0.83rem;
                color: #0A385C;
                background: #F0F7FC;
                border: 1px solid #BAE6FD;
                border-radius: 11px;
                padding: 0.65rem 0.9rem;
                margin-bottom: 0.75rem;
            }

            .subtle-notice {
                font-size: 0.82rem;
                color: #475569;
                background: rgba(255, 255, 255, 0.86);
                border: 1px solid #E2E8F0;
                border-left: 3.5px solid #0A385C;
                border-radius: 10px;
                padding: 0.58rem 0.9rem;
                margin-bottom: 0.85rem;
            }

            .stButton > button, .stDownloadButton > button, .stLinkButton > a {
                border-radius: 10px;
                font-weight: 600;
                min-height: 43px;
                transition: transform 0.14s ease, box-shadow 0.14s ease;
            }

            .stButton > button:hover, .stDownloadButton > button:hover { transform: translateY(-1px); }

            .stButton > button[kind="primary"],
            .stDownloadButton > button[kind="primary"],
            .stButton > button[data-testid="stBaseButton-primary"],
            .stDownloadButton > button[data-testid="stBaseButton-primary"] {
                background: linear-gradient(135deg, #062844 0%, #0A385C 55%, #0E5673 100%) !important;
                border: none !important;
                color: #FFFFFF !important;
                box-shadow: 0 4px 14px rgba(10, 56, 92, 0.26) !important;
            }

            @media (max-width: 768px) {
                [data-testid="stMainBlockContainer"] {
                    padding-top: 0.45rem !important;
                    padding-left: 0.75rem !important;
                    padding-right: 0.75rem !important;
                }
                [data-testid="stMainBlockContainer"] [data-testid="stElementContainer"]:has(.st-key-top_navbar) {
                    height: auto !important;
                    position: sticky !important;
                    top: 0.3rem !important;
                    z-index: 990 !important;
                    margin-bottom: 0.55rem !important;
                }
                .st-key-top_navbar {
                    position: relative !important;
                    top: auto !important;
                    left: auto !important;
                    right: auto !important;
                    width: 100% !important;
                    margin: 0 !important;
                    padding: 0.65rem 0.7rem 0.6rem 0.7rem !important;
                    border: 1px solid rgba(203, 213, 225, 0.9) !important;
                    border-radius: 14px !important;
                }
                .st-key-top_navbar [data-testid="stHorizontalBlock"] {
                    display: flex !important;
                    flex-direction: row !important;
                    flex-wrap: wrap !important;
                    align-items: stretch !important;
                    justify-content: center !important;
                    row-gap: 0.5rem !important;
                    column-gap: 0.4rem !important;
                }
                .st-key-top_navbar [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child {
                    flex: 1 0 100% !important;
                    width: 100% !important;
                    min-width: 100% !important;
                    height: auto !important;
                    padding-bottom: 0.25rem !important;
                }
                .st-key-top_navbar [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child [data-testid="stVerticalBlock"],
                .st-key-top_navbar [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child [data-testid="stElementContainer"],
                .st-key-top_navbar [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child [data-testid="stMarkdown"] {
                    height: auto !important;
                    min-height: 30px !important;
                }
                .st-key-top_navbar [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:not(:first-child) {
                    flex: 1 1 auto !important;
                    width: auto !important;
                    min-width: fit-content !important;
                }
                .topnav-brand {
                    justify-content: center !important;
                    align-items: center !important;
                    height: auto !important;
                    min-height: 28px !important;
                    padding: 0.1rem 0 0.2rem 0 !important;
                    line-height: 1.3 !important;
                }
                .topnav-logo {
                    font-size: 1.04rem !important;
                    line-height: 1.25 !important;
                }
                .topnav-inst-logo-univali { height: 20px !important; }
                .topnav-inst-logo-lema { height: 18px !important; }
                .st-key-top_navbar button,
                .st-key-top_navbar .stLinkButton > a {
                    min-height: 36px !important;
                    height: 36px !important;
                    padding: 0 0.72rem !important;
                    font-size: 0.79rem !important;
                }
                .exec-hero { padding: 1.15rem 1.1rem !important; border-radius: 16px !important; }
                .hero-main-grid { flex-direction: column; align-items: stretch; gap: 0.85rem; }
                .hero-inst-card { min-width: 0; width: 100%; box-sizing: border-box; padding: 0.68rem 0.9rem; }
                .hero-logo-univali { height: 38px; }
                .hero-logo-lema { height: 34px; }
                .exec-hero h1.hero-title, .hero-title { font-size: 1.35rem !important; line-height: 1.2 !important; }
                .hero-desc { font-size: 0.85rem !important; margin-bottom: 0.2rem !important; }
                .hero-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.5rem; }
                .inst-footer { flex-direction: column; align-items: center; text-align: center; }
                .inst-footer-text { text-align: center; }
                .stTabs button[data-baseweb="tab"] { padding: 0.45rem 0.85rem !important; font-size: 0.84rem !important; min-height: 42px !important; }
                .meta-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
                .result-species { font-size: 1.35rem; }
                .species-grid { grid-template-columns: 1fr; }
                .cta-contact-box { flex-direction: column; align-items: flex-start; }
                .stButton > button, .stDownloadButton > button { min-height: 44px; }
                .fish-sprite { width: calc(var(--w, 112px) * 0.58); opacity: calc(var(--op, 0.24) * 0.75); }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource
def build_pixi_aquarium_html() -> str:
    """Monta o aquário WebGL 60fps em PixiJS v8 com malha deformável MeshRope e peixes fotorrealistas."""
    fish_uris = load_real_bg_fish_pngs()
    assets_json = json.dumps(fish_uris, ensure_ascii=True)

    template = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<style>
  html, body {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
    background:
      radial-gradient(1100px 540px at 14% -8%, rgba(14, 165, 233, 0.16), transparent 62%),
      radial-gradient(950px 520px at 88% 6%, rgba(14, 116, 155, 0.13), transparent 60%),
      linear-gradient(180deg, #E2F3F9 0%, #EEF7FA 48%, #DCEFF4 100%);
  }
  canvas {
    display: block;
    width: 100vw;
    height: 100vh;
    pointer-events: none;
  }
</style>
<script src="https://cdn.jsdelivr.net/npm/pixi.js@8.6.6/dist/pixi.min.js"></script>
</head>
<body>
<script>
(async function () {
  const FISH_URIS = __FISH_ASSETS_JSON__;
  const isMobile = window.innerWidth <= 768;

  // Plano realista em 3 camadas de profundidade (fundo distante desfocado, plano médio e primeiro plano)
  const SWIM_SPEC = isMobile
    ? [
        { key: "marlin_real",   depth: 0, yFrac: 0.16, scale: 0.34, dir:  1, speed: 0.42, alpha: 0.24, tailAmp: 5.5, tailFreq: 0.065, startFrac: 0.12 },
        { key: "sailfish_real", depth: 1, yFrac: 0.36, scale: 0.48, dir: -1, speed: 0.62, alpha: 0.44, tailAmp: 7.5, tailFreq: 0.080, startFrac: 0.72 },
        { key: "tuna_real",     depth: 1, yFrac: 0.62, scale: 0.44, dir:  1, speed: 0.78, alpha: 0.40, tailAmp: 8.5, tailFreq: 0.095, startFrac: 0.35 },
        { key: "mahi_real",     depth: 2, yFrac: 0.84, scale: 0.50, dir: -1, speed: 0.86, alpha: 0.48, tailAmp: 9.0, tailFreq: 0.090, startFrac: 0.85 },
      ]
    : [
        { key: "tuna_real",     depth: 0, yFrac: 0.14, scale: 0.40, dir:  1, speed: 0.46, alpha: 0.22, tailAmp: 6.0, tailFreq: 0.070, startFrac: 0.10 },
        { key: "marlin_real",   depth: 0, yFrac: 0.68, scale: 0.44, dir: -1, speed: 0.40, alpha: 0.20, tailAmp: 6.0, tailFreq: 0.062, startFrac: 0.62 },
        { key: "sailfish_real", depth: 1, yFrac: 0.25, scale: 0.66, dir: -1, speed: 0.72, alpha: 0.42, tailAmp: 9.5, tailFreq: 0.078, startFrac: 0.78 },
        { key: "mahi_real",     depth: 1, yFrac: 0.52, scale: 0.60, dir:  1, speed: 0.88, alpha: 0.44, tailAmp: 10.5, tailFreq: 0.092, startFrac: 0.24 },
        { key: "tuna_real",     depth: 1, yFrac: 0.79, scale: 0.58, dir:  1, speed: 0.96, alpha: 0.42, tailAmp: 11.0, tailFreq: 0.105, startFrac: 0.52 },
        { key: "marlin_real",   depth: 2, yFrac: 0.39, scale: 0.78, dir:  1, speed: 1.05, alpha: 0.46, tailAmp: 11.5, tailFreq: 0.082, startFrac: 0.04 },
        { key: "sailfish_real", depth: 2, yFrac: 0.89, scale: 0.74, dir: -1, speed: 0.84, alpha: 0.44, tailAmp: 10.0, tailFreq: 0.076, startFrac: 0.90 },
      ];

  function loadHtmlImage(src) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = src;
    });
  }

  const loadedImgs = {};
  await Promise.all(
    Object.entries(FISH_URIS).map(async ([k, uri]) => {
      try { loadedImgs[k] = await loadHtmlImage(uri); } catch (e) {}
    })
  );

  // ================= MOTOR PRIMÁRIO: PIXIJS v8 WebGL + MeshRope =================
  async function startPixiAquarium() {
    if (!window.PIXI) throw new Error("PixiJS unavailable");
    const app = new PIXI.Application();
    await app.init({
      resizeTo: window,
      backgroundAlpha: 0,
      antialias: true,
      autoDensity: true,
      resolution: Math.min(window.devicePixelRatio || 1, 2),
      powerPreference: "high-performance",
    });
    document.body.appendChild(app.canvas);

    const raysLayer = new PIXI.Container();
    const farLayer = new PIXI.Container();
    const midLayer = new PIXI.Container();
    const nearLayer = new PIXI.Container();
    const bubblesLayer = new PIXI.Container();
    app.stage.addChild(raysLayer, farLayer, midLayer, nearLayer, bubblesLayer);

    // 1) Raios cáusticos de luz solar atravessando a superfície da água
    const rays = [];
    const rayConfigs = [
      { xFrac: 0.12, topW: 85,  botW: 250, hFrac: 0.72, alpha: 0.16, speed: 0.008, phase: 0.0 },
      { xFrac: 0.30, topW: 65,  botW: 210, hFrac: 0.65, alpha: 0.13, speed: 0.011, phase: 1.4 },
      { xFrac: 0.52, topW: 110, botW: 310, hFrac: 0.78, alpha: 0.15, speed: 0.007, phase: 2.7 },
      { xFrac: 0.74, topW: 75,  botW: 230, hFrac: 0.68, alpha: 0.14, speed: 0.010, phase: 4.1 },
      { xFrac: 0.90, topW: 60,  botW: 190, hFrac: 0.60, alpha: 0.12, speed: 0.009, phase: 5.2 },
    ];
    if (PIXI.BlurFilter) {
      raysLayer.filters = [new PIXI.BlurFilter({ strength: 16, quality: 2 })];
    }
    for (const rc of rayConfigs) {
      const g = new PIXI.Graphics();
      const h = Math.max(window.innerHeight * rc.hFrac, 420);
      g.poly([
        -rc.topW * 0.5, -20,
         rc.topW * 0.5, -20,
         rc.botW * 0.65, h,
        -rc.botW * 0.35, h,
      ]).fill({ color: 0xFFFFFF, alpha: 1 });
      g.x = window.innerWidth * rc.xFrac;
      g.y = 0;
      g.alpha = rc.alpha;
      raysLayer.addChild(g);
      rays.push({ g, cfg: rc });
    }

    // 2) Peixes pelágicos fotorrealistas com malha flexível PIXI.MeshRope
    const textures = {};
    for (const [k, img] of Object.entries(loadedImgs)) {
      textures[k] = PIXI.Texture.from(img);
    }

    if (PIXI.BlurFilter) {
      farLayer.filters = [new PIXI.BlurFilter({ strength: 1.6, quality: 2 })];
    }

    const SEGMENTS = 16;
    const fishes = [];
    for (const sp of SWIM_SPEC) {
      const tex = textures[sp.key];
      if (!tex) continue;

      const segLen = tex.width / (SEGMENTS - 1);
      const points = [];
      for (let i = 0; i < SEGMENTS; i++) {
        points.push(new PIXI.Point(i * segLen, 0));
      }

      const rope = new PIXI.MeshRope({ texture: tex, points });
      rope.x = -tex.width * 0.5;

      const holder = new PIXI.Container();
      holder.addChild(rope);
      holder.scale.set(sp.dir * sp.scale, sp.scale);
      holder.alpha = sp.alpha;
      if (sp.depth === 0) {
        rope.tint = 0xB8DCE8; // Atenuação cromática oceânica de profundidade
      }

      const startX = sp.startFrac * (window.innerWidth + 420) - 210;
      const baseY = sp.yFrac * window.innerHeight;
      holder.x = startX;
      holder.y = baseY;

      const targetLayer = sp.depth === 0 ? farLayer : (sp.depth === 1 ? midLayer : nearLayer);
      targetLayer.addChild(holder);

      fishes.push({
        holder,
        points,
        texW: tex.width,
        scale: sp.scale,
        dir: sp.dir,
        speed: sp.speed,
        yFrac: sp.yFrac,
        baseY,
        phase: Math.random() * Math.PI * 2,
        glidePhase: Math.random() * Math.PI * 2,
        glideAmp: 12 + Math.random() * 14,
        glideSpeed: 0.008 + Math.random() * 0.007,
        tailAmp: sp.tailAmp,
        tailFreq: sp.tailFreq,
      });
    }

    // 3) Bolhas vítreas realistas (colunas suaves tipo aerador + microbolhas difusas)
    const bubbles = [];
    const bubbleCount = isMobile ? 38 : 68;
    const diffuserZones = [0.08, 0.24, 0.76, 0.92];
    for (let i = 0; i < bubbleCount; i++) {
      const isStream = i < Math.floor(bubbleCount * 0.58);
      const zoneX = diffuserZones[i % diffuserZones.length];
      const tier = Math.random();
      const r = tier < 0.55 ? (1.6 + Math.random() * 2.1)
              : tier < 0.88 ? (3.6 + Math.random() * 2.6)
              : (6.2 + Math.random() * 3.2);
      const g = new PIXI.Graphics();
      const rimAlpha = tier > 0.85 ? 0.42 : 0.32;
      const fillAlpha = tier > 0.85 ? 0.26 : 0.34;
      g.circle(0, 0, r)
        .fill({ color: 0xFFFFFF, alpha: fillAlpha })
        .stroke({ width: r > 5 ? 1.25 : 0.9, color: 0x0EA5E9, alpha: rimAlpha });
      // Brilho especular duplo (reflexo da luz na bolha real)
      g.circle(-r * 0.32, -r * 0.32, Math.max(0.7, r * 0.28)).fill({ color: 0xFFFFFF, alpha: 0.92 });
      if (r > 4.2) {
        g.circle(r * 0.26, r * 0.28, r * 0.14).fill({ color: 0xBAE6FD, alpha: 0.65 });
      }
      g.x = isStream
        ? (zoneX * window.innerWidth + (Math.random() - 0.5) * 95)
        : (Math.random() * window.innerWidth);
      g.y = Math.random() * window.innerHeight;
      bubblesLayer.addChild(g);
      bubbles.push({
        g,
        r,
        isStream,
        zoneX,
        vy: 0.42 + (r * 0.085) + Math.random() * 0.55,
        wobblePhase: Math.random() * Math.PI * 2,
        wobbleSpeed: 0.018 + Math.random() * 0.028,
        wobbleAmp: 0.35 + Math.random() * 0.75,
        pulsePhase: Math.random() * Math.PI * 2,
      });
    }

    let elapsed = 0;
    app.ticker.add((ticker) => {
      const dt = Math.min(ticker.deltaTime || 1, 2.5);
      elapsed += dt;
      const W = app.screen.width;
      const H = app.screen.height;

      for (const r of rays) {
        const s = Math.sin(elapsed * r.cfg.speed + r.cfg.phase);
        r.g.x = W * r.cfg.xFrac + s * 28;
        r.g.rotation = s * 0.045;
        r.g.alpha = r.cfg.alpha * (0.78 + 0.22 * Math.cos(elapsed * r.cfg.speed * 0.8 + r.cfg.phase));
      }

      for (const f of fishes) {
        f.phase += dt * f.tailFreq;
        f.glidePhase += dt * f.glideSpeed;

        // Nado carangiforme realista: cabeça firme (i = SEGMENTS-1), cauda ondula (i = 0)
        for (let i = 0; i < SEGMENTS; i++) {
          const tailFactor = 1.0 - (i / (SEGMENTS - 1));
          const flex = Math.pow(tailFactor, 1.75);
          f.points[i].y = Math.sin(f.phase - tailFactor * 4.2) * f.tailAmp * flex;
        }

        f.holder.x += f.dir * f.speed * dt;
        const targetBaseY = f.yFrac * H;
        const vy = Math.cos(f.glidePhase) * f.glideAmp * f.glideSpeed;
        f.holder.y = targetBaseY + Math.sin(f.glidePhase) * f.glideAmp;
        f.holder.rotation = f.dir * Math.max(-0.07, Math.min(0.07, vy * 0.55));

        const margin = f.texW * f.scale * 0.72 + 40;
        if (f.dir > 0 && f.holder.x > W + margin) {
          f.holder.x = -margin;
        } else if (f.dir < 0 && f.holder.x < -margin) {
          f.holder.x = W + margin;
        }
      }

      for (const b of bubbles) {
        b.wobblePhase += dt * b.wobbleSpeed;
        b.pulsePhase += dt * 0.055;
        b.g.y -= b.vy * dt;
        b.g.x += Math.sin(b.wobblePhase) * b.wobbleAmp * dt;
        if (b.r > 4.5) {
          const sq = 0.06 * Math.sin(b.pulsePhase);
          b.g.scale.set(1 + sq, 1 - sq);
        }
        if (b.g.y < -18) {
          b.g.y = H + 12 + Math.random() * 30;
          b.g.x = b.isStream
            ? (b.zoneX * W + (Math.random() - 0.5) * 95)
            : (Math.random() * W);
        }
      }
    });
  }

  // ================= FALLBACK CANVAS 2D COM ONDULAÇÃO POR FATIAS =================
  function startCanvas2DFallback() {
    const canvas = document.createElement("canvas");
    document.body.appendChild(canvas);
    const ctx = canvas.getContext("2d");
    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(window.innerWidth * dpr);
      canvas.height = Math.floor(window.innerHeight * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    const fishes = SWIM_SPEC.map((sp) => ({
      ...sp,
      img: loadedImgs[sp.key],
      x: sp.startFrac * (window.innerWidth + 360) - 180,
      phase: Math.random() * Math.PI * 2,
      glidePhase: Math.random() * Math.PI * 2,
    })).filter((f) => f.img);

    const diffuserZones = [0.08, 0.24, 0.76, 0.92];
    const bubbles = Array.from({ length: isMobile ? 34 : 56 }, (_, idx) => {
      const isStream = idx < 34;
      const zoneX = diffuserZones[idx % diffuserZones.length];
      const r = 1.6 + Math.random() * 6.2;
      return {
        x: isStream ? (zoneX * window.innerWidth + (Math.random() - 0.5) * 90) : (Math.random() * window.innerWidth),
        y: Math.random() * window.innerHeight,
        r,
        isStream,
        zoneX,
        vy: 0.42 + r * 0.08 + Math.random() * 0.55,
        p: Math.random() * Math.PI * 2,
      };
    });

    let t = 0;
    function frame() {
      t += 1;
      const W = window.innerWidth;
      const H = window.innerHeight;
      ctx.clearRect(0, 0, W, H);

      // Raios solares subaquáticos suaves
      ctx.save();
      for (let i = 0; i < 4; i++) {
        const rx = W * (0.15 + i * 0.24) + Math.sin(t * 0.008 + i) * 24;
        const grad = ctx.createLinearGradient(rx, 0, rx + 70, H * 0.72);
        grad.addColorStop(0, "rgba(255,255,255,0.22)");
        grad.addColorStop(1, "rgba(255,255,255,0)");
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.moveTo(rx - 40, 0);
        ctx.lineTo(rx + 40, 0);
        ctx.lineTo(rx + 150, H * 0.72);
        ctx.lineTo(rx - 70, H * 0.72);
        ctx.closePath();
        ctx.fill();
      }
      ctx.restore();

      // Peixes fotorrealistas com ondulação suave por fatias verticais
      const SLICES = 18;
      for (const f of fishes) {
        f.phase += f.tailFreq;
        f.glidePhase += 0.01;
        f.x += f.dir * f.speed;
        const drawW = f.img.width * f.scale;
        const drawH = f.img.height * f.scale;
        const cy = f.yFrac * H + Math.sin(f.glidePhase) * 14;

        ctx.save();
        ctx.globalAlpha = f.alpha;
        ctx.translate(f.x, cy);
        ctx.scale(f.dir, 1);
        const srcSliceW = f.img.width / SLICES;
        const dstSliceW = drawW / SLICES;
        for (let s = 0; s < SLICES; s++) {
          const tailFactor = 1.0 - s / (SLICES - 1);
          const dy = Math.sin(f.phase - tailFactor * 4.2) * f.tailAmp * Math.pow(tailFactor, 1.75) * f.scale;
          ctx.drawImage(
            f.img,
            s * srcSliceW, 0, srcSliceW + 0.6, f.img.height,
            -drawW * 0.5 + s * dstSliceW, -drawH * 0.5 + dy, dstSliceW + 0.8, drawH
          );
        }
        ctx.restore();

        const margin = drawW * 0.7 + 40;
        if (f.dir > 0 && f.x > W + margin) f.x = -margin;
        if (f.dir < 0 && f.x < -margin) f.x = W + margin;
      }

      // Microbolhas
      for (const b of bubbles) {
        b.y -= b.vy;
        b.p += 0.02;
        b.x += Math.sin(b.p) * 0.4;
        if (b.y < -12) { b.y = H + 12; b.x = Math.random() * W; }
        ctx.beginPath();
        ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(255,255,255,0.34)";
        ctx.strokeStyle = "rgba(14,165,233,0.24)";
        ctx.lineWidth = 1;
        ctx.fill();
        ctx.stroke();
      }
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  try {
    await startPixiAquarium();
  } catch (err) {
    startCanvas2DFallback();
  }
})();
</script>
</body>
</html>
"""
    return template.replace("__FISH_ASSETS_JSON__", assets_json)


def render_animated_ocean_background() -> None:
    """Injeta o aquário WebGL PixiJS v8 com peixes marinhos fotorrealistas atrás da interface."""
    with st.container(key="aquarium_bg_host", border=False):
        components.html(build_pixi_aquarium_html(), height=0, width=0, scrolling=False)


# =============================================================================
# Comunicação com Backend + Fallback Demo + Pipeline de Coleta
# =============================================================================
@st.cache_data(ttl=15, show_spinner=False)
def fetch_backend_info(backend_url: str) -> dict[str, Any]:
    if not backend_url:
        return {
            "connected": False,
            "mode": "demo",
            "status": "Modo Demonstração",
            "species_catalog": SPECIES_CATALOG_FALLBACK,
            "storage_backend": "local",
        }
    try:
        resp = requests.get(f"{backend_url}/info", timeout=4)
        resp.raise_for_status()
        data = resp.json()
        data["connected"] = True
        return data
    except Exception as exc:
        return {
            "connected": False,
            "mode": "demo",
            "status": "Modo Demonstração (Backend offline)",
            "load_error": str(exc),
            "model_path": "models/modelo.keras",
            "input_size": [320, 320],
            "total_params": None,
            "trainable_params": None,
            "normalize_div_255": True,
            "preserve_aspect_ratio": True,
            "species_catalog": SPECIES_CATALOG_FALLBACK,
            "storage_backend": "local",
        }


def _local_demo_predict(image_rgb: np.ndarray, hint_species: str | None = None) -> dict[str, Any]:
    thumb = cv2.resize(image_rgb, (16, 16), interpolation=cv2.INTER_AREA)
    digest = hashlib.sha256(thumb.tobytes()).digest()
    seed = int.from_bytes(digest[:4], "big")
    rng = np.random.default_rng(seed)

    catalog = SPECIES_CATALOG_FALLBACK
    logits = rng.normal(loc=0.0, scale=0.72, size=len(catalog))
    winner_idx = int(seed % len(catalog))
    if hint_species:
        for i, item in enumerate(catalog):
            if hint_species in (item["scientific"], item["common_pt"]):
                winner_idx = i
                break
    logits[winner_idx] += float(rng.uniform(2.6, 4.0))
    shifted = logits - np.max(logits)
    probs = np.exp(shifted) / np.sum(np.exp(shifted))

    ordered = sorted(
        [
            {
                "scientific": item["scientific"],
                "common_pt": item["common_pt"],
                "species": f"{item['common_pt']} ({item['scientific']})",
                "probability": float(p),
            }
            for item, p in zip(catalog, probs)
        ],
        key=lambda item: item["probability"],
        reverse=True,
    )
    top = ordered[0]
    return {
        "mode": "demo",
        "top_species": top["common_pt"],
        "scientific_name": top["scientific"],
        "display_name": top["species"],
        "confidence": top["probability"],
        "latency_ms": round(float(rng.uniform(18.5, 39.0)), 1),
        "probabilities": ordered,
    }


def predict_via_backend(
    image: Image.Image,
    backend_info: dict[str, Any],
    hint_species: str | None = None,
) -> dict[str, Any]:
    if backend_info.get("connected") and BACKEND_URL:
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=92)
        files = {"file": ("image.jpg", buf.getvalue(), "image/jpeg")}
        data = {"hint_species": hint_species} if hint_species else {}
        try:
            resp = requests.post(f"{BACKEND_URL}/predict", files=files, data=data, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            pass
    return _local_demo_predict(np.asarray(image), hint_species=hint_species)


def contribute_photo_to_backend(
    image: Image.Image,
    result: dict[str, Any],
    user_confirmed: bool,
    user_suggested_species: str,
    source: str,
) -> dict[str, Any]:
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=92)
    files = {"file": ("contribuicao.jpg", buf.getvalue(), "image/jpeg")}
    data = {
        "predicted_scientific": str(result.get("scientific_name", "")),
        "predicted_common_pt": str(result.get("top_species", "")),
        "confidence": str(float(result.get("confidence", 0.0))),
        "user_confirmed": "true" if user_confirmed else "false",
        "user_suggested_species": user_suggested_species,
        "source": source,
    }
    resp = requests.post(f"{BACKEND_URL}/contribute", files=files, data=data, timeout=20)
    resp.raise_for_status()
    return resp.json()


# =============================================================================
# Badge limpo nas imagens/vídeos
# =============================================================================
@st.cache_resource
def _load_badge_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=font_size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=font_size)
    except TypeError:
        return ImageFont.load_default()


def draw_clean_top_badge(
    image: Image.Image,
    species: str,
    confidence: float,
    is_demo: bool = False,
    ref_min_dim: int | None = None,
) -> Image.Image:
    base = image.convert("RGBA")
    width, height = base.size
    min_dim = ref_min_dim if ref_min_dim is not None else min(width, height)

    font_size = max(14, min(34, int(min_dim * 0.036)))
    font = _load_badge_font(font_size)

    label = f"{species}  •  {confidence * 100:.1f}%"

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    bbox = draw.textbbox((0, 0), label, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    pad_x = max(12, int(font_size * 0.72))
    pad_y = max(7, int(font_size * 0.42))
    margin = max(12, int(min_dim * 0.025))

    x0, y0 = margin, margin
    x1 = min(width - margin, x0 + text_w + pad_x * 2)
    y1 = min(height - 4, y0 + text_h + pad_y * 2)
    radius = max(10, int((y1 - y0) / 2))

    draw.rounded_rectangle((x0, y0 + 2, x1, y1 + 2), radius=radius, fill=(6, 33, 53, 85))
    draw.rounded_rectangle(
        (x0, y0, x1, y1),
        radius=radius,
        fill=(10, 56, 92, 240),
        outline=(255, 255, 255, 110),
        width=1,
    )
    draw.text((x0 + pad_x - bbox[0], y0 + pad_y - bbox[1]), label, font=font, fill=(255, 255, 255, 255))
    return Image.alpha_composite(base, overlay).convert("RGB")


def annotate_video_frame_bgr(
    frame_bgr: np.ndarray,
    species: str,
    confidence: float,
    is_demo: bool = False,
) -> np.ndarray:
    height, width = frame_bgr.shape[:2]
    strip_h = min(height, max(120, int(height * 0.25)))
    top_rgb = cv2.cvtColor(frame_bgr[:strip_h, :, :], cv2.COLOR_BGR2RGB)
    annotated_top = draw_clean_top_badge(
        Image.fromarray(top_rgb),
        species=species,
        confidence=confidence,
        is_demo=is_demo,
        ref_min_dim=min(width, height),
    )
    out = frame_bgr.copy()
    out[:strip_h, :, :] = cv2.cvtColor(np.asarray(annotated_top), cv2.COLOR_RGB2BGR)
    return out


# =============================================================================
# Galeria / Carrossel Sob Demanda (6.500+ fotos reais do Google Drive a R$ 0!)
# =============================================================================
SCIENTIFIC_TO_META: dict[str, dict[str, str]] = {
    item["scientific"].lower(): item for item in SPECIES_CATALOG_FALLBACK
}


@st.cache_resource(show_spinner="Carregando galeria de espécies...")
def load_gdrive_catalog_index(folder_url: str) -> tuple[list[dict[str, str]], str | None]:
    """Lista todas as imagens da pasta pública do Drive (sem baixar 6.000 arquivos) e faz cache em JSON."""
    url_hash = hashlib.md5(folder_url.encode("utf-8")).hexdigest()[:10]
    cache_dir = GDRIVE_CACHE_ROOT / url_hash
    cache_dir.mkdir(parents=True, exist_ok=True)
    index_file = cache_dir / "catalog_index.json"

    if index_file.is_file():
        try:
            cached = json.loads(index_file.read_text(encoding="utf-8"))
            if isinstance(cached, list) and cached:
                return cached, None
        except Exception:
            pass

    try:
        import gdown

        listed = gdown.download_folder(
            url=folder_url,
            skip_download=True,
            quiet=True,
            use_cookies=False,
        )
        by_species: dict[str, list[dict[str, str]]] = defaultdict(list)

        for entry in listed or []:
            rel_path = str(getattr(entry, "path", "") or "")
            file_id = str(getattr(entry, "id", "") or "")
            if not file_id or not rel_path:
                continue
            p_obj = Path(rel_path)
            if p_obj.suffix.lower() not in SUPPORTED_IMAGE_EXTS:
                continue

            folder_part = p_obj.parent.name if p_obj.parent.name else ""
            sci_clean = folder_part.replace("_", " ").strip()
            meta = SCIENTIFIC_TO_META.get(sci_clean.lower())
            common_pt = meta["common_pt"] if meta else (sci_clean or p_obj.stem)
            sci_name = meta["scientific"] if meta else sci_clean
            group = meta["group"] if meta else "Marinho"

            by_species[common_pt].append(
                {
                    "id": f"gd_{file_id}",
                    "file_id": file_id,
                    "name": common_pt,
                    "scientific": sci_name,
                    "group": group,
                    "filename": p_obj.name,
                    "hint_species": sci_name,
                }
            )

        # Intercala as espécies em round-robin para cada página mostrar diversidade real
        species_keys = sorted(by_species.keys())
        interleaved: list[dict[str, str]] = []
        max_len = max((len(v) for v in by_species.values()), default=0)
        for i in range(max_len):
            for sp in species_keys:
                bucket = by_species[sp]
                if i < len(bucket):
                    interleaved.append(bucket[i])

        if interleaved:
            index_file.write_text(json.dumps(interleaved, ensure_ascii=False), encoding="utf-8")
        return interleaved, None
    except Exception as exc:
        return [], str(exc)


@st.cache_data(ttl=3600, max_entries=160, show_spinner=False)
def fetch_gdrive_image(file_id: str, size: str = "w640") -> Image.Image | None:
    """Baixa sob demanda apenas a imagem exibida na página atual (rápido e cacheado)."""
    thumb_dir = GDRIVE_CACHE_ROOT / "thumbs"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    local_file = thumb_dir / f"{file_id}_{size}.jpg"

    if local_file.is_file():
        try:
            return Image.open(local_file).convert("RGB")
        except Exception:
            pass

    urls = [
        f"https://drive.google.com/thumbnail?id={file_id}&sz={size}",
        f"https://drive.google.com/uc?export=view&id={file_id}",
    ]
    for url in urls:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200 and resp.content:
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                img.save(local_file, format="JPEG", quality=90)
                return img
        except Exception:
            continue
    return None


def get_sample_gallery() -> tuple[list[dict[str, Any]], str, str | None]:
    if GDRIVE_FOLDER_URL:
        items, err = load_gdrive_catalog_index(GDRIVE_FOLDER_URL)
        return items, "Google Drive", err

    if ASSETS_DIR.exists():
        local_images = [
            {
                "id": f"local_{idx}_{p.name}",
                "path": p,
                "name": p.stem.replace("_", " ").replace("-", " ").title(),
                "scientific": "",
                "group": "Marinho",
                "filename": p.name,
                "hint_species": None,
            }
            for idx, p in enumerate(
                sorted(p for p in ASSETS_DIR.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_EXTS)
            )
        ]
        return local_images, "Pasta local", None

    return [], "Pasta local", None


@st.cache_resource
def build_demo_carousel_cards() -> list[dict[str, Any]]:
    demo_specs = [
        ("Agulhão-negro", "Makaira nigricans", "marlin_real.png", (10, 61, 88), (6, 33, 53)),
        ("Agulhão-vela", "Istiophorus platypterus", "sailfish_real.png", (6, 148, 162), (22, 78, 99)),
        ("Dourado-do-mar", "Coryphaena hippurus", "mahi_real.png", (13, 148, 136), (17, 94, 89)),
        ("Albacora-laje", "Thunnus albacares", "tuna_real.png", (14, 116, 144), (8, 51, 68)),
    ]
    cards: list[dict[str, Any]] = []
    w, h = 720, 450

    for idx, (species_pt, species_sci, gif_name, top_rgb, bot_rgb) in enumerate(demo_specs):
        y_grad = np.linspace(0.0, 1.0, h).reshape(h, 1, 1)
        bg = (
            np.array(top_rgb, dtype=np.float32) * (1.0 - y_grad)
            + np.array(bot_rgb, dtype=np.float32) * y_grad
        ).astype(np.uint8)
        scene = Image.fromarray(np.repeat(bg, w, axis=1), mode="RGB").convert("RGBA")
        draw = ImageDraw.Draw(scene, "RGBA")

        for rx in (95, 250, 430, 580):
            shift = (idx * 23) % 45
            draw.polygon(
                [(rx + shift, 0), (rx + shift + 55, 0), (rx + shift + 135, h), (rx + shift + 30, h)],
                fill=(255, 255, 255, 18),
            )
        for bx, by, br in [(540, 140, 11), (570, 102, 7), (175, 165, 8), (520, 82, 5)]:
            draw.ellipse((bx - br, by - br, bx + br, by + br), outline=(255, 255, 255, 110), width=2)

        gif_path = BG_FISH_DIR / gif_name
        if gif_path.is_file():
            with Image.open(gif_path) as g_img:
                g_img.seek(0)
                sprite = g_img.convert("RGBA")
                target_w = 430
                target_h = int(sprite.height * (target_w / max(sprite.width, 1)))
                sprite = sprite.resize((target_w, target_h), Image.Resampling.LANCZOS)
                scene.alpha_composite(sprite, ((w - target_w) // 2, (h - target_h) // 2 + 12))

        cards.append(
            {
                "id": f"demo_{idx}",
                "name": species_pt,
                "filename": f"{species_sci.lower().replace(' ', '_')}_demo.png",
                "image": scene.convert("RGB"),
                "hint_species": species_sci,
            }
        )
    return cards


@st.cache_data(show_spinner=False)
def generate_pix_qr_data_uri(payload: str) -> str | None:
    """Gera QR Code PNG de alta nitidez a partir do payload EMV Pix usando OpenCV nativo."""
    clean = (payload or "").strip()
    if not clean:
        return None
    try:
        encoder = cv2.QRCodeEncoder.create()
        matrix = encoder.encode(clean)
        scaled = cv2.resize(matrix, (318, 318), interpolation=cv2.INTER_NEAREST)
        bordered = cv2.copyMakeBorder(scaled, 22, 22, 22, 22, cv2.BORDER_CONSTANT, value=255)
        rgb = np.full((bordered.shape[0], bordered.shape[1], 3), 255, dtype=np.uint8)
        rgb[bordered < 128] = (6, 33, 53)  # Azul oceânico escuro de alto contraste
        buf = io.BytesIO()
        Image.fromarray(rgb, mode="RGB").save(buf, format="PNG", optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None


# =============================================================================
# Hero Executivo + Barra de Ação Fixa (Apoie a Pesquisa · Sobre & ODS · GitHub)
# =============================================================================
def render_top_navbar() -> None:
    """Cabeçalho superior fixo (colado no topo ao rolar): marca limpa, logos UNIVALI/LEMA, apoio Pix/QR, sobre/ODS, GitHub e seletor de idioma."""
    logos = load_institutional_logos()
    univali_uri = logos.get("univali", "")
    lema_uri = logos.get("lema", "")
    lang = get_lang()

    nav_logos_html = ""
    if univali_uri or lema_uri:
        imgs = []
        if univali_uri:
            imgs.append(f'<img src="{univali_uri}" alt="UNIVALI" class="topnav-inst-logo topnav-inst-logo-univali" />')
        if lema_uri:
            imgs.append(f'<img src="{lema_uri}" alt="LEMA" class="topnav-inst-logo topnav-inst-logo-lema" />')
        nav_logos_html = (
            '<span class="topnav-divider"></span>'
            f'<span class="topnav-inst-logos">{"".join(imgs)}</span>'
        )

    with st.container(key="top_navbar", border=False):
        c_msg, c_coffee, c_bib, c_git, c_lang = st.columns(
            [2.05, 1.18, 0.96, 0.68, 0.62],
            vertical_alignment="center",
            gap="small",
        )

        with c_msg:
            st.markdown(
                f"""
                <div class="topnav-brand">
                    <span class="topnav-logo">🐟 FishID Studio</span>
                    {nav_logos_html}
                </div>
                """,
                unsafe_allow_html=True,
            )

        with c_coffee:
            with st.popover(t("nav_support"), width="stretch"):
                st.markdown(t("support_title"))
                st.markdown(t("support_body", author=AUTHOR_NAME))
                qr_uri = generate_pix_qr_data_uri(PIX_PAYLOAD) if PIX_PAYLOAD else None
                if qr_uri:
                    st.markdown(
                        f"""
                        <div class="pix-qr-card">
                            <img class="pix-qr-img" src="{qr_uri}" alt="QR Code Pix" />
                            <div class="pix-qr-caption">{html.escape(t("pix_scan"))}</div>
                            <div class="pix-qr-sub">{html.escape(t("pix_sub", author=AUTHOR_NAME))}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                if PIX_PAYLOAD:
                    st.markdown(t("pix_copy_label"))
                    st.code(PIX_PAYLOAD, language=None)
                if PIX_KEY:
                    st.markdown(t("pix_key_label"))
                    st.code(PIX_KEY, language=None)
                if SUPPORT_URL:
                    st.link_button(t("support_ext_btn"), SUPPORT_URL, type="primary", width="stretch")
                if not PIX_PAYLOAD and not PIX_KEY and not SUPPORT_URL:
                    st.info(t("support_missing"))

        with c_bib:
            with st.popover(t("nav_about"), width="stretch"):
                if univali_uri or lema_uri:
                    pop_parts = []
                    if univali_uri:
                        pop_parts.append(f'<img src="{univali_uri}" alt="UNIVALI" class="pop-univali" />')
                    if univali_uri and lema_uri:
                        pop_parts.append('<span class="popover-inst-sep"></span>')
                    if lema_uri:
                        pop_parts.append(f'<img src="{lema_uri}" alt="LEMA" class="pop-lema" />')
                    st.markdown(
                        f'<div class="popover-inst-banner">{"".join(pop_parts)}</div>',
                        unsafe_allow_html=True,
                    )
                st.markdown(f"#### 👨‍💻 {AUTHOR_NAME}")
                if COAUTHOR_NAME:
                    st.markdown(f"**{t('about_coauthor')}:** {COAUTHOR_NAME}")
                st.markdown(
                    f"**{t('about_institution')}:** {INSTITUTION_NAME}  \n"
                    f"**{t('about_lab')}:** {t('about_lab_val')}  \n"
                    f"*{t('about_research_title')}*  \n"
                    f"{t('about_desc')}"
                )
                st.divider()
                st.markdown(t("about_sdg_heading"))
                st.markdown(t("about_sdg_list"))
                st.divider()
                st.markdown(t("about_bib_heading"))
                st.markdown(
                    "\n".join(
                        [
                            "- **Liu, Z. et al. (2022).** *A ConvNet for the 2020s (ConvNeXt).* CVPR.",
                            "- **Selvaraju, R. R. et al. (2017).** *Grad-CAM: Visual Explanations from Deep Networks.* ICCV.",
                            "- **Álvarez-Ellacuría, A. et al. (2019).** *Image-based, unsupervised estimation of fish size from commercial landings.* ICES JMS.",
                            "- **Froese, R. (2006).** *Cube law, condition factor and weight-length relationships.* J. Appl. Ichthyol.",
                            t("about_open_bases"),
                        ]
                    )
                )

        with c_git:
            st.link_button("💻 GitHub", GITHUB_URL, width="stretch")

        with c_lang:
            with st.popover(f"🌐 {lang.upper()}", width="stretch"):
                st.markdown(f"**{t('nav_lang_title')}**")
                for code, _short, full_label in LANG_OPTIONS:
                    if st.button(
                        full_label,
                        key=f"lang_btn_{code}",
                        type="primary" if lang == code else "secondary",
                        width="stretch",
                    ):
                        if lang != code:
                            st.session_state["lang"] = code
                            st.rerun()


def render_executive_hero(backend_info: dict[str, Any], total_gallery_photos: int = 0) -> None:
    dot_cls = "dot-live"
    status_txt = t("hero_status_online")
    catalog = backend_info.get("species_catalog") or SPECIES_CATALOG_FALLBACK
    logos = load_institutional_logos()
    univali_uri = logos.get("univali", "")
    lema_uri = logos.get("lema", "")

    coauthor_html = ""
    if COAUTHOR_NAME:
        coauthor_html = (
            '<span class="hero-coauthor-badge">'
            f'<span class="hero-author-prefix">{html.escape(t("hero_coauthor_prefix"))}</span>'
            f'<span>{html.escape(COAUTHOR_NAME)}</span>'
            '</span>'
        )

    inst_card_html = ""
    if univali_uri or lema_uri:
        logo_parts = []
        if univali_uri:
            logo_parts.append(f'<img src="{univali_uri}" alt="UNIVALI" class="hero-logo-univali" />')
        if univali_uri and lema_uri:
            logo_parts.append('<span class="hero-inst-sep"></span>')
        if lema_uri:
            logo_parts.append(
                f'<img src="{lema_uri}" alt="LEMA" class="hero-logo-lema" />'
            )
        inst_card_html = (
            '<div class="hero-inst-card">'
            f'<div class="hero-inst-label">{html.escape(t("hero_inst_label"))}</div>'
            f'<div class="hero-inst-logos">{"".join(logo_parts)}</div>'
            f'<div class="hero-inst-sub">{html.escape(t("hero_inst_sub"))}</div>'
            '</div>'
        )

    hero_html = "\n".join(
        line.strip()
        for line in f"""
        <div class="exec-hero">
            <div class="hero-top-row">
                <div class="hero-pills">
                    <span class="pill-brand">{html.escape(t("hero_pill_brand"))}</span>
                    <span class="pill-ods">{html.escape(t("hero_pill_ods"))}</span>
                    <span class="pill-tech">{html.escape(t("hero_pill_tech"))}</span>
                    <span class="pill-em">{html.escape(t("hero_pill_em"))}</span>
                </div>
                <span class="pill-status"><span class="{dot_cls}"></span>{html.escape(status_txt)}</span>
            </div>
            <div class="hero-main-grid">
                <div class="hero-main-left">
                    <h1 class="hero-title">{html.escape(t("hero_title"))}</h1>
                    <div class="hero-author-row">
                        <a class="hero-author-badge" href="{html.escape(GITHUB_URL)}" target="_blank" rel="noopener noreferrer">
                            <span class="hero-author-prefix">{html.escape(t("hero_author_prefix"))}</span>
                            <span>{html.escape(AUTHOR_NAME)}</span>
                        </a>
                        {coauthor_html}
                    </div>
                    <p class="hero-desc">
                        <strong>{html.escape(t("about_research_title"))}</strong>.
                        {html.escape(t("hero_desc_rest"))}
                    </p>
                </div>
                {inst_card_html}
            </div>
            <div class="hero-stats">
                <div class="hero-stat">
                    <div class="hero-stat-val">{html.escape(t("stat_species_val", n=len(catalog)))}</div>
                    <div class="hero-stat-lbl">{html.escape(t("stat_species_lbl"))}</div>
                </div>
                <div class="hero-stat">
                    <div class="hero-stat-val">{html.escape(t("stat_realtime_val"))}</div>
                    <div class="hero-stat-lbl">{html.escape(t("stat_realtime_lbl"))}</div>
                </div>
                <div class="hero-stat">
                    <div class="hero-stat-val">{html.escape(t("stat_em_val"))}</div>
                    <div class="hero-stat-lbl">{html.escape(t("stat_em_lbl"))}</div>
                </div>
                <div class="hero-stat">
                    <div class="hero-stat-val">{html.escape(t("stat_dl_val"))}</div>
                    <div class="hero-stat-lbl">{html.escape(t("stat_dl_lbl"))}</div>
                </div>
                <div class="hero-stat">
                    <div class="hero-stat-val">UNIVALI · LEMA</div>
                    <div class="hero-stat-lbl">{html.escape(t("stat_open_lbl"))}</div>
                </div>
            </div>
        </div>
        """.splitlines()
        if line.strip()
    )

    st.markdown(hero_html, unsafe_allow_html=True)


def render_institutional_footer() -> None:
    """Rodapé institucional com as logos da UNIVALI e do LEMA e créditos de autoria."""
    logos = load_institutional_logos()
    univali_uri = logos.get("univali", "")
    lema_uri = logos.get("lema", "")

    logo_parts = []
    if univali_uri:
        logo_parts.append(f'<img src="{univali_uri}" alt="UNIVALI" class="inst-footer-univali" />')
    if univali_uri and lema_uri:
        logo_parts.append('<span class="inst-footer-sep"></span>')
    if lema_uri:
        logo_parts.append(
            f'<img src="{lema_uri}" alt="LEMA" class="inst-footer-lema" />'
        )

    authors_line = f"<strong>{html.escape(t('hero_author_prefix'))}:</strong> {html.escape(AUTHOR_NAME)}"
    if COAUTHOR_NAME:
        authors_line += (
            f" &nbsp;·&nbsp; <strong>{html.escape(t('hero_coauthor_prefix'))}:</strong> {html.escape(COAUTHOR_NAME)}"
        )

    footer_html = "\n".join(
        line.strip()
        for line in f"""
        <div class="inst-footer">
            <div class="inst-footer-logos">
                {"".join(logo_parts)}
            </div>
            <div class="inst-footer-text">
                <div class="inst-footer-title">FishID Studio · {html.escape(INSTITUTION_NAME)}</div>
                <div>{html.escape(t("about_lab_val"))} · {html.escape(t("footer_degree"))}</div>
                <div>{authors_line}</div>
            </div>
        </div>
        """.splitlines()
        if line.strip()
    )
    st.markdown(footer_html, unsafe_allow_html=True)


def render_supported_species_catalog(backend_info: dict[str, Any]) -> None:
    catalog = backend_info.get("species_catalog") or SPECIES_CATALOG_FALLBACK
    if "show_species_catalog" not in st.session_state:
        st.session_state["show_species_catalog"] = False

    is_open = bool(st.session_state["show_species_catalog"])
    btn_label = t("catalog_hide", n=len(catalog)) if is_open else t("catalog_show", n=len(catalog))
    if st.button(btn_label, key="toggle_species_catalog", width="stretch"):
        st.session_state["show_species_catalog"] = not is_open
        st.rerun()

    if is_open:
        cards_html = "".join(
            f"""
            <div class="species-item">
                <div class="species-pt">{idx + 1}. {html.escape(get_species_common(item['scientific'], item['common_pt']))}</div>
                <div class="species-sci">{html.escape(item['scientific'])}</div>
                <span class="species-grp">{html.escape(get_species_group(item.get('group', 'Marinho')))}</span>
            </div>
            """
            for idx, item in enumerate(catalog)
        )
        contact_email_esc = html.escape(CONTACT_EMAIL)
        contact_href = html.escape(CONTACT_URL or f"mailto:{CONTACT_EMAIL}")
        st.markdown(
            f"""
            <div class="studio-card" style="margin-top: 0.45rem;">
                <div class="eyebrow">{html.escape(t("catalog_eyebrow", n=len(catalog)))}</div>
                <div class="species-grid">{cards_html}</div>
                <div class="cta-contact-box">
                    <div>
                        <div class="cta-contact-title">{html.escape(t("cta_title"))}</div>
                        <div class="cta-contact-sub">
                            {html.escape(t("cta_sub", author=AUTHOR_NAME))}
                        </div>
                    </div>
                    <div style="display:flex; align-items:center; flex-wrap:wrap; gap:0.55rem;">
                        <a class="cta-contact-btn" href="{contact_href}">
                            {html.escape(t("cta_btn"))}
                        </a>
                        <span style="font-size:0.82rem; font-weight:600; color:#0A385C; background:#FFFFFF; border:1px solid #BAE6FD; padding:0.42rem 0.72rem; border-radius:9px;">
                            {contact_email_esc}
                        </span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_result_card(result: dict[str, Any], image_size: tuple[int, int]) -> None:
    raw_sci = str(result.get("scientific_name", ""))
    raw_common = str(result.get("top_species", ""))
    top_species = html.escape(get_species_common(raw_sci, raw_common))
    scientific = html.escape(raw_sci)
    conf = float(result.get("confidence", 0.0))
    pct = conf * 100.0
    mode_label = html.escape(t("result_mode"))
    res_label = f"{image_size[0]} × {image_size[1]} px"

    if conf >= 0.80:
        conf_cls, conf_txt = "conf-high", t("conf_high")
        guidance = t("conf_high_guide")
    elif conf >= 0.55:
        conf_cls, conf_txt = "conf-mid", t("conf_mid")
        guidance = t("conf_mid_guide")
    else:
        conf_cls, conf_txt = "conf-low", t("conf_low")
        guidance = t("conf_low_guide")

    sci_html = f'<div class="result-scientific">{scientific}</div>' if scientific else ""

    st.markdown(
        f"""
        <div class="result-spotlight">
            <div class="eyebrow">{html.escape(t("result_eyebrow"))}</div>
            <div class="result-species">{top_species}</div>
            {sci_html}
            <div class="conf-row">
                <span class="conf-pct-big">{pct:.1f}%</span>
                <span class="conf-pill {conf_cls}">{html.escape(conf_txt)}</span>
            </div>
            <div class="conf-bar-wrap">
                <div class="conf-bar-fill" style="width: {max(2.0, min(100.0, pct)):.1f}%;"></div>
            </div>
            <p style="font-size: 0.88rem; color: #334155; margin: 0; line-height: 1.5;">
                {html.escape(guidance)}
            </p>
            <div class="meta-strip">
                <div>
                    <div class="meta-k">{html.escape(t("meta_response"))}</div>
                    <div class="meta-v">{float(result.get('latency_ms', 0.0)):.1f} ms</div>
                </div>
                <div>
                    <div class="meta-k">{html.escape(t("meta_model"))}</div>
                    <div class="meta-v">{mode_label}</div>
                </div>
                <div>
                    <div class="meta-k">{html.escape(t("meta_resolution"))}</div>
                    <div class="meta-v">{res_label}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_contribution_box(
    active_image: Image.Image,
    result: dict[str, Any],
    source: str,
    backend_info: dict[str, Any],
    photo_key: str,
) -> None:
    """Pipeline de coleta voluntária para retreinamento futuro e expansão de novas espécies."""
    catalog = backend_info.get("species_catalog") or SPECIES_CATALOG_FALLBACK
    sent_key = f"contrib_sent_{photo_key}"

    with st.container(border=True):
        st.markdown(f'<div class="eyebrow">{html.escape(t("contrib_eyebrow"))}</div>', unsafe_allow_html=True)
        st.caption(t("contrib_caption"))

        if st.session_state.get(sent_key):
            saved_info = st.session_state[sent_key]
            st.success(
                t(
                    "contrib_success",
                    sample_id=saved_info.get("sample_id", ""),
                    backend=saved_info.get("backend", "local"),
                )
            )
            return

        if not backend_info.get("connected"):
            st.caption(t("contrib_offline"))
            return

        col_yes, col_fix = st.columns([1.0, 1.0], gap="small")
        with col_yes:
            if st.button(t("contrib_ok_btn"), key=f"btn_ok_{photo_key}", type="primary", width="stretch"):
                try:
                    resp = contribute_photo_to_backend(
                        image=active_image,
                        result=result,
                        user_confirmed=True,
                        user_suggested_species=str(result.get("scientific_name", "")),
                        source=source,
                    )
                    st.session_state[sent_key] = resp
                    st.rerun()
                except Exception as exc:
                    st.error(t("contrib_save_err", exc=exc))

        with col_fix:
            with st.popover(t("contrib_fix_btn"), width="stretch"):
                other_opt = t("contrib_other_opt")
                options = [
                    f"{get_species_common(s['scientific'], s['common_pt'])} ({s['scientific']})" for s in catalog
                ] + [other_opt]
                choice = st.selectbox(t("contrib_select"), options=options, key=f"sel_fix_{photo_key}")
                custom_name = ""
                if choice == other_opt:
                    custom_name = st.text_input(
                        t("contrib_custom_lbl"),
                        placeholder=t("contrib_custom_ph"),
                        key=f"txt_new_{photo_key}",
                    ).strip()
                if st.button(t("contrib_send_fix"), key=f"btn_send_fix_{photo_key}", type="primary", width="stretch"):
                    suggested = custom_name if choice == other_opt else choice
                    if not suggested:
                        st.warning(t("contrib_warn_empty"))
                    else:
                        try:
                            resp = contribute_photo_to_backend(
                                image=active_image,
                                result=result,
                                user_confirmed=False,
                                user_suggested_species=suggested,
                                source=source,
                            )
                            st.session_state[sent_key] = resp
                            st.rerun()
                        except Exception as exc:
                            st.error(t("contrib_save_err", exc=exc))


# =============================================================================
# Processamento de vídeo (OpenCV + Backend + FFmpeg H.264)
# =============================================================================
def process_video_bytes(
    video_bytes: bytes,
    original_filename: str,
    frame_skip: int,
    backend_info: dict[str, Any],
) -> dict[str, Any]:
    is_demo = backend_info.get("mode") != "real"
    suffix = Path(original_filename).suffix or ".mp4"

    with tempfile.TemporaryDirectory(prefix="fishid_video_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        in_path = tmp_path / f"input{suffix}"
        raw_out_path = tmp_path / "annotated_raw.mp4"
        h264_out_path = tmp_path / "annotated_h264.mp4"
        in_path.write_bytes(video_bytes)

        cap = cv2.VideoCapture(str(in_path))
        if not cap.isOpened():
            raise RuntimeError("Não foi possível abrir o arquivo de vídeo enviado.")

        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        if fps <= 0.0 or np.isnan(fps):
            fps = 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames_est = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        if width <= 0 or height <= 0:
            cap.release()
            raise RuntimeError("Dimensões do vídeo inválidas.")

        writer = cv2.VideoWriter(str(raw_out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        if not writer.isOpened():
            cap.release()
            raise RuntimeError("Falha ao inicializar o gravador de vídeo OpenCV.")

        progress_bar = st.progress(0, text=t("video_prog_start"))
        records: list[dict[str, Any]] = []
        last_pred: dict[str, Any] | None = None
        frame_idx = 0

        try:
            while True:
                ret, frame_bgr = cap.read()
                if not ret:
                    break

                if frame_idx % frame_skip == 0 or last_pred is None:
                    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                    last_pred = predict_via_backend(Image.fromarray(frame_rgb), backend_info)
                    sp_display = get_species_common(
                        str(last_pred.get("scientific_name", "")),
                        str(last_pred.get("top_species", "")),
                    )
                    records.append(
                        {
                            "frame": frame_idx,
                            "species": sp_display,
                            "confidence": float(last_pred["confidence"]),
                            "latency_ms": float(last_pred.get("latency_ms", 0.0)),
                        }
                    )

                annotated_bgr = annotate_video_frame_bgr(
                    frame_bgr,
                    species=get_species_common(
                        str(last_pred.get("scientific_name", "")),
                        str(last_pred.get("top_species", "")),
                    ),
                    confidence=float(last_pred["confidence"]),
                    is_demo=is_demo,
                )
                writer.write(annotated_bgr)
                frame_idx += 1

                if total_frames_est > 0 and (frame_idx % max(1, frame_skip) == 0 or frame_idx == total_frames_est):
                    pct = min(85, int((frame_idx / total_frames_est) * 85))
                    progress_bar.progress(pct, text=t("video_prog_frame", idx=frame_idx, total=total_frames_est))
        finally:
            cap.release()
            writer.release()

        if frame_idx == 0:
            progress_bar.empty()
            raise RuntimeError("Nenhum frame foi lido do vídeo.")

        progress_bar.progress(90, text=t("video_prog_h264"))
        proc = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(raw_out_path),
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(h264_out_path),
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0 or not h264_out_path.exists():
            progress_bar.empty()
            raise RuntimeError(f"Erro na conversão FFmpeg para H.264: {proc.stderr[-400:]}")

        progress_bar.progress(100, text=t("video_prog_done"))
        final_bytes = h264_out_path.read_bytes()
        progress_bar.empty()

    rec_df = pd.DataFrame(records)
    total_analyzed = len(rec_df)
    grouped = (
        rec_df.groupby("species", as_index=False)
        .agg(
            frames_analisados=("frame", "count"),
            confianca_media=("confidence", "mean"),
            confianca_max=("confidence", "max"),
        )
        .sort_values("frames_analisados", ascending=False)
        .reset_index(drop=True)
    )
    grouped["participacao_pct"] = (grouped["frames_analisados"] / max(total_analyzed, 1)) * 100.0

    col_sp = t("video_col_species")
    summary_df = pd.DataFrame(
        {
            col_sp: grouped["species"],
            t("video_col_frames"): grouped["frames_analisados"],
            t("video_col_share"): grouped["participacao_pct"].round(1),
            t("video_col_avg_conf"): (grouped["confianca_media"] * 100.0).round(1),
            t("video_col_max_conf"): (grouped["confianca_max"] * 100.0).round(1),
        }
    )

    stem = Path(original_filename).stem
    return {
        "video_bytes": final_bytes,
        "output_filename": f"{stem}_fishid_anotado.mp4",
        "summary_df": summary_df,
        "top_species": str(summary_df.iloc[0][col_sp]),
        "total_frames": frame_idx,
        "analyzed_frames": total_analyzed,
        "fps": round(fps, 1),
        "duration_s": round(frame_idx / fps, 1),
        "avg_latency_ms": round(float(rec_df["latency_ms"].mean()), 1),
    }


# =============================================================================
# Abas do aplicativo
# =============================================================================
def _render_species_carousel(
    sample_items: list[dict[str, Any]],
    sample_origin: str,
    sample_error: str | None,
) -> tuple[Image.Image | None, str, str | None]:
    if sample_error:
        st.warning(t("gallery_error"))

    is_demo_catalog = len(sample_items) == 0
    items = build_demo_carousel_cards() if is_demo_catalog else sample_items

    header_label = t("gallery_header")

    def _item_display_name(it: dict[str, Any]) -> str:
        sci = str(it.get("scientific") or it.get("hint_species") or "")
        return get_species_common(sci, str(it.get("name", "")))

    with st.container(border=True):
        col_title, col_filter, col_rand = st.columns([1.45, 1.15, 0.72], vertical_alignment="center", gap="small")
        with col_title:
            st.markdown(f'<div class="eyebrow" style="margin-bottom:0;">{html.escape(header_label)}</div>', unsafe_allow_html=True)
        with col_filter:
            species_keys_map: dict[str, str] = {}
            for it in items:
                raw_key = str(it.get("scientific") or it.get("hint_species") or it.get("name") or "")
                if raw_key and raw_key not in species_keys_map:
                    species_keys_map[raw_key] = _item_display_name(it)
            sorted_keys = sorted(species_keys_map.keys(), key=lambda k: species_keys_map[k].lower())
            filter_options = ["__ALL__"] + sorted_keys
            saved_filter = st.session_state.get("carousel_species_filter_val", "__ALL__")
            default_idx = filter_options.index(saved_filter) if saved_filter in filter_options else 0
            selected_species_key = st.selectbox(
                t("gallery_filter_label"),
                options=filter_options,
                index=default_idx,
                format_func=lambda k: t("gallery_all") if k == "__ALL__" else species_keys_map.get(k, k),
                label_visibility="collapsed",
                key=f"carousel_species_filter_{get_lang()}",
            )
            st.session_state["carousel_species_filter_val"] = selected_species_key

        filtered = (
            items
            if selected_species_key == "__ALL__"
            else [
                it
                for it in items
                if str(it.get("scientific") or it.get("hint_species") or it.get("name") or "") == selected_species_key
            ]
        )

        per_page = 3
        total_pages = max(1, math.ceil(len(filtered) / per_page))
        if "carousel_page" not in st.session_state:
            st.session_state["carousel_page"] = 0

        with col_rand:
            if st.button(t("gallery_shuffle"), key="car_shuffle", width="stretch", disabled=total_pages <= 1):
                st.session_state["carousel_page"] = random.randint(0, total_pages - 1)
                st.rerun()

        if not filtered:
            st.info(t("gallery_empty"))
            return None, "", None

        st.session_state["carousel_page"] = min(st.session_state["carousel_page"], total_pages - 1)
        page = st.session_state["carousel_page"]

        page_items = filtered[page * per_page : (page + 1) * per_page]
        st.markdown(
            """
            <style>
            div[class*="st-key-car_card_"] [data-testid="stImage"] img {
                cursor: pointer !important;
                transition: opacity 0.16s ease;
            }
            div[class*="st-key-car_card_"] [data-testid="stImage"] img:hover {
                opacity: 0.90;
            }
            div[class*="st-key-car_card_"] [data-testid="StyledFullScreenButton"],
            div[class*="st-key-car_card_"] button[title="View fullscreen"] {
                display: none !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        components.html(
            """
            <script>
            (function() {
                try {
                    const pWin = window.parent;
                    const pDoc = pWin.document;
                    if (pWin.__fishidCarouselImgClickBound) return;
                    pWin.__fishidCarouselImgClickBound = true;
                    pDoc.addEventListener("click", function(ev) {
                        const img = ev.target && ev.target.closest ? ev.target.closest('div[class*="st-key-car_card_"] [data-testid="stImage"] img') : null;
                        if (!img) return;
                        const card = img.closest('div[class*="st-key-car_card_"]');
                        if (!card) return;
                        const btn = card.querySelector('[data-testid="stButton"] button');
                        if (btn) {
                            ev.preventDefault();
                            ev.stopPropagation();
                            btn.click();
                        }
                    }, true);
                } catch (e) {}
            })();
            </script>
            """,
            height=0,
            width=0,
            scrolling=False,
        )
        cols = st.columns(per_page, gap="small")
        selected_id = st.session_state.get("selected_carousel_id")

        for col_idx, item in enumerate(page_items):
            with cols[col_idx]:
                try:
                    raw_img: Image.Image | None = None
                    if "file_id" in item:
                        raw_img = fetch_gdrive_image(item["file_id"], size="w640")
                    elif "path" in item:
                        raw_img = Image.open(item["path"]).convert("RGB")
                    else:
                        raw_img = item.get("image")

                    if raw_img is None:
                        st.caption(t("gallery_img_unavail"))
                        continue

                    # Card clicável inteiro: clicar na foto OU no botão identifica o peixe
                    with st.container(key=f"car_card_{col_idx}"):
                        thumb_card = ImageOps.fit(raw_img, (480, 300), method=Image.Resampling.LANCZOS)
                        st.image(thumb_card, width="stretch")

                        is_sel = selected_id == item["id"]
                        short_name = _item_display_name(item)[:20]
                        label = f"✓ {short_name}" if is_sel else t("gallery_identify", name=short_name)
                        if st.button(
                            label,
                            key=f"car_btn_{item['id']}",
                            width="stretch",
                            type="primary" if is_sel else "secondary",
                        ):
                            st.session_state["selected_carousel_id"] = item["id"]
                            st.rerun()
                except Exception:
                    st.caption(t("gallery_open_err", filename=item.get("filename", "image")))

        if total_pages > 1:
            c_prev, c_info, c_next = st.columns([1, 1.5, 1], vertical_alignment="center")
            with c_prev:
                if st.button(t("gallery_prev"), key="car_prev", width="stretch", disabled=page <= 0):
                    st.session_state["carousel_page"] = max(0, page - 1)
                    st.rerun()
            with c_info:
                st.markdown(
                    f'<div style="text-align:center;font-size:0.82rem;color:#64748B;font-weight:500;">{html.escape(t("gallery_page", page=page + 1, total=total_pages))}</div>',
                    unsafe_allow_html=True,
                )
            with c_next:
                if st.button(t("gallery_next"), key="car_next", width="stretch", disabled=page >= total_pages - 1):
                    st.session_state["carousel_page"] = min(total_pages - 1, page + 1)
                    st.rerun()

    # Recupera imagem completa (sem recorte) do item selecionado para predição
    if selected_id:
        for item in items:
            if item["id"] == selected_id:
                if "file_id" in item:
                    img = fetch_gdrive_image(item["file_id"], size="w1000") or fetch_gdrive_image(item["file_id"], size="w640")
                    return img, item["filename"], item.get("hint_species")
                if "path" in item:
                    return Image.open(item["path"]).convert("RGB"), item["filename"], item.get("hint_species")
                return item.get("image"), item["filename"], item.get("hint_species")
    return None, "", None


def render_image_tab(
    backend_info: dict[str, Any],
    sample_items: list[dict[str, Any]],
    sample_origin: str,
    sample_error: str | None,
) -> None:
    is_demo = backend_info.get("mode") != "real"

    render_supported_species_catalog(backend_info)

    if "photo_input_mode_v2" not in st.session_state:
        st.session_state["photo_input_mode_v2"] = "carousel"

    st.markdown("<div style='height: 0.45rem;'></div>", unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3, gap="small")
    current_mode = st.session_state["photo_input_mode_v2"]
    with m1:
        if st.button(
            t("mode_carousel"),
            key="mode_btn_carousel",
            type="primary" if current_mode == "carousel" else "secondary",
            width="stretch",
        ):
            st.session_state["photo_input_mode_v2"] = "carousel"
            st.rerun()
    with m2:
        if st.button(
            t("mode_camera"),
            key="mode_btn_camera",
            type="primary" if current_mode == "camera" else "secondary",
            width="stretch",
        ):
            st.session_state["photo_input_mode_v2"] = "camera"
            st.rerun()
    with m3:
        if st.button(
            t("mode_upload"),
            key="mode_btn_upload",
            type="primary" if current_mode == "upload" else "secondary",
            width="stretch",
        ):
            st.session_state["photo_input_mode_v2"] = "upload"
            st.rerun()

    input_mode = st.session_state["photo_input_mode_v2"]

    active_image: Image.Image | None = None
    active_name: str = ""
    hint_species: str | None = None
    source_tag: str = input_mode

    if input_mode == "camera":
        st.markdown(
            f'<div class="camera-tip">{t("camera_tip")}</div>',
            unsafe_allow_html=True,
        )
        camera_photo = st.camera_input(t("camera_input"), key="fish_camera_input", width="stretch")
        if camera_photo is not None:
            active_image = Image.open(camera_photo).convert("RGB")
            active_name = f"captura_camera_{datetime.now().strftime('%H%M%S')}.jpg"

    elif input_mode == "upload":
        uploaded_file = st.file_uploader(
            t("upload_label"),
            type=["jpg", "jpeg", "png", "webp"],
            key="image_uploader",
        )
        if uploaded_file is not None:
            active_image = Image.open(uploaded_file).convert("RGB")
            active_name = uploaded_file.name
    else:
        active_image, active_name, hint_species = _render_species_carousel(
            sample_items=sample_items,
            sample_origin=sample_origin,
            sample_error=sample_error,
        )

    if active_image is not None:
        st.markdown("<div style='height: 0.45rem;'></div>", unsafe_allow_html=True)
        result = predict_via_backend(active_image, backend_info, hint_species=hint_species)
        badge_species = get_species_common(
            str(result.get("scientific_name", "")),
            str(result.get("top_species", "")),
        )
        annotated_img = draw_clean_top_badge(
            active_image,
            species=badge_species,
            confidence=float(result["confidence"]),
            is_demo=is_demo,
        )

        col_img, col_card = st.columns([1.18, 1.0], gap="large")
        with col_img:
            with st.container(border=True):
                st.markdown(
                    f'<div class="eyebrow">{html.escape(t("preview_eyebrow"))}</div>',
                    unsafe_allow_html=True,
                )
                st.image(annotated_img, width="stretch")
        with col_card:
            render_result_card(result, active_image.size)
            if source_tag in ("camera", "upload"):
                photo_hash = hashlib.md5(f"{active_name}_{active_image.size}".encode("utf-8")).hexdigest()[:8]
                render_contribution_box(
                    active_image=active_image,
                    result=result,
                    source=source_tag,
                    backend_info=backend_info,
                    photo_key=photo_hash,
                )
    else:
        st.markdown(
            f"""
            <div class="empty-stage">
                <div style="font-size: 1.05rem; font-weight: 700; color: #0F172A; margin-bottom: 0.25rem;">
                    {html.escape(t("empty_photo_title"))}
                </div>
                <div style="font-size: 0.88rem;">
                    {html.escape(t("empty_photo_sub"))}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_video_tab(backend_info: dict[str, Any]) -> None:
    uploaded_video = st.file_uploader(
        t("video_upload"),
        type=["mp4", "mov"],
        key="video_uploader",
    )

    col_slider, col_btn = st.columns([2.2, 1], vertical_alignment="bottom", gap="medium")
    with col_slider:
        frame_skip = st.slider(
            t("video_slider"),
            min_value=1,
            max_value=30,
            value=5,
            step=1,
        )
    with col_btn:
        run_video = st.button(t("video_run_btn"), type="primary", width="stretch", disabled=uploaded_video is None)

    if uploaded_video is not None and run_video:
        try:
            st.session_state["video_result"] = process_video_bytes(
                video_bytes=uploaded_video.getvalue(),
                original_filename=uploaded_video.name,
                frame_skip=frame_skip,
                backend_info=backend_info,
            )
        except Exception as exc:
            st.error(t("video_err", exc=exc))

    video_result = st.session_state.get("video_result")
    if video_result:
        st.markdown("<div style='height: 0.45rem;'></div>", unsafe_allow_html=True)
        col_player, col_summary = st.columns([1.2, 1.0], gap="large")
        with col_player:
            with st.container(border=True):
                st.markdown(f'<div class="eyebrow">{html.escape(t("video_annotated_eyebrow"))}</div>', unsafe_allow_html=True)
                st.video(video_result["video_bytes"])
        with col_summary:
            top_sp = html.escape(video_result["top_species"])
            st.markdown(
                f"""
                <div class="result-spotlight">
                    <div class="eyebrow">{html.escape(t("video_predom_eyebrow"))}</div>
                    <div class="result-species">{top_sp}</div>
                    <div class="meta-strip">
                        <div>
                            <div class="meta-k">{html.escape(t("video_meta_frames"))}</div>
                            <div class="meta-v">{video_result['analyzed_frames']} / {video_result['total_frames']}</div>
                        </div>
                        <div>
                            <div class="meta-k">{html.escape(t("video_meta_dur"))}</div>
                            <div class="meta-v">{video_result['duration_s']}s · {video_result['fps']} fps</div>
                        </div>
                        <div>
                            <div class="meta-k">{html.escape(t("video_meta_lat"))}</div>
                            <div class="meta-v">{video_result['avg_latency_ms']:.1f} ms</div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(f'<div class="eyebrow">{html.escape(t("video_summary_eyebrow"))}</div>', unsafe_allow_html=True)
            st.dataframe(video_result["summary_df"], width="stretch", hide_index=True)
            st.download_button(
                label=t("video_download"),
                data=video_result["video_bytes"],
                file_name=video_result["output_filename"],
                mime="video/mp4",
                width="stretch",
                type="primary",
            )
    elif uploaded_video is None:
        st.markdown(
            f"""
            <div class="empty-stage">
                <div style="font-size: 1.02rem; font-weight: 700; color: #0F172A; margin-bottom: 0.25rem;">
                    {html.escape(t("video_empty_title"))}
                </div>
                <div style="font-size: 0.88rem;">
                    {html.escape(t("video_empty_sub"))}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_about_tab(
    backend_info: dict[str, Any],
    sample_paths: list[Path],
    sample_origin: str,
) -> None:
    catalog = backend_info.get("species_catalog") or SPECIES_CATALOG_FALLBACK
    in_size = backend_info.get("input_size") or [320, 320]
    total_params = backend_info.get("total_params")
    trainable_params = backend_info.get("trainable_params")

    if total_params is not None:
        total_p = f"{int(total_params):,}".replace(",", ".")
        train_p = f"{int(trainable_params or 0):,}".replace(",", ".")
        params_text = f"{total_p} ({train_p} treináveis)"
    else:
        params_text = "— (aguardando backend/models/modelo.keras)"

    conn_text = f"Conectado ({BACKEND_URL})" if backend_info.get("connected") else "Offline (Modo Demo)"
    storage_txt = f"{backend_info.get('storage_backend', 'local').upper()} · {backend_info.get('storage_bucket', 'collected_data')}"
    samples_text = f"{sample_origin} · {len(sample_paths)} imagem(ns)"

    st.markdown(
        f"""
        <div class="studio-card">
            <div class="eyebrow">Ficha técnica do sistema</div>
            <div class="spec-grid">
                <div class="spec-box">
                    <div class="spec-label">Status do modelo</div>
                    <div class="spec-value">{html.escape(str(backend_info.get("status", "Modo Demonstração")))}</div>
                </div>
                <div class="spec-box">
                    <div class="spec-label">API Backend</div>
                    <div class="spec-value"><code>{html.escape(conn_text)}</code></div>
                </div>
                <div class="spec-box">
                    <div class="spec-label">Dimensão de entrada</div>
                    <div class="spec-value">{in_size[0]} × {in_size[1]} × 3</div>
                </div>
                <div class="spec-box">
                    <div class="spec-label">Total de parâmetros</div>
                    <div class="spec-value">{html.escape(params_text)}</div>
                </div>
                <div class="spec-box">
                    <div class="spec-label">Pipeline de coleta</div>
                    <div class="spec-value"><code>{html.escape(storage_txt)}</code></div>
                </div>
                <div class="spec-box">
                    <div class="spec-label">Origem dos exemplos</div>
                    <div class="spec-value">{html.escape(samples_text)}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cards_html = "".join(
        f"""
        <div class="species-item">
            <div class="species-pt">{html.escape(item['common_pt'])}</div>
            <div class="species-sci">{html.escape(item['scientific'])}</div>
            <span class="species-grp">{html.escape(item.get('group', 'Marinho'))}</span>
        </div>
        """
        for item in catalog
    )
    st.markdown(
        f"""
        <div class="studio-card">
            <div class="eyebrow">Catálogo oficial ({len(catalog)} espécies pelágicas migratórias)</div>
            <div class="species-grid">{cards_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _find_em_experiments_dir() -> Path | None:
    custom = _get_setting("EM_EXPERIMENTS_DIR", "")
    candidates = [
        Path(custom) if custom else None,
        Path(__file__).resolve().parent.parent / "experimentos_em",
        Path.cwd() / "experimentos_em",
    ]
    for p in candidates:
        if p is not None and p.is_dir():
            return p
    return None


@st.cache_data(ttl=15)
def _load_em_run_data(resumo_csv_str: str, mtime: float) -> pd.DataFrame:
    _ = mtime
    p = Path(resumo_csv_str)
    if not p.is_file() or p.stat().st_size < 10:
        return pd.DataFrame()
    try:
        return pd.read_csv(p)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=600)
def _ensure_browser_h264(video_path_str: str, mtime: float) -> str:
    """Converte MP4 (mp4v) para H.264 em /tmp para reprodução garantida no navegador."""
    src = Path(video_path_str)
    key = hashlib.md5(f"{video_path_str}:{mtime}".encode("utf-8")).hexdigest()[:12]
    dst = Path(tempfile.gettempdir()) / f"fishid_hud_{key}.mp4"
    if dst.is_file() and dst.stat().st_size > 1024:
        return str(dst)
    try:
        proc = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(src),
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(dst),
            ],
            capture_output=True,
            timeout=90,
            check=False,
        )
        if proc.returncode == 0 and dst.is_file() and dst.stat().st_size > 1024:
            return str(dst)
    except Exception:
        pass
    return str(src)


def _format_em_run_option(run_dir: Path, is_en: bool) -> tuple[str, int, str]:
    """Gera rótulo amigável e sem termos técnicos para o seletor de análises."""
    cfg: dict[str, Any] = {}
    cfg_path = run_dir / "config_experimento.json"
    if cfg_path.is_file():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}

    resumo_path = run_dir / "resumo_peixes.csv"
    df_tmp = _load_em_run_data(str(resumo_path), resumo_path.stat().st_mtime) if resumo_path.is_file() else pd.DataFrame()
    n_fish = len(df_tmp)
    has_hud = (run_dir / "video_anotado_hud.mp4").is_file()

    # Formata data/nome do vídeo (ex.: 30_06_2023.mp4 -> 30/06/2023)
    vid_stem = Path(str(cfg.get("video_name", run_dir.name))).stem
    parts = vid_stem.split("_")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        vid_label = f"{parts[0]}/{parts[1]}/{parts[2]}"
    else:
        vid_label = vid_stem.replace("_", " ").strip()

    # Janela horária curta (HH:MM–HH:MM)
    s_hms = str(cfg.get("start_hms", ""))
    e_hms = str(cfg.get("end_hms", ""))
    win_txt = f"{s_hms[:5]}–{e_hms[:5]}" if len(s_hms) >= 5 and len(e_hms) >= 5 else ""

    low = run_dir.name.lower()
    if "completo" in low or "completa" in low:
        scene = "Full trip" if is_en else "Viagem completa"
    elif "boia" in low:
        scene = "Deck with buoys" if is_en else "Convés com boias"
    elif "vazio" in low:
        scene = "Empty night deck" if is_en else "Convés vazio (noturno)"
    elif "madrugada" in low or "02h32" in low:
        scene = "Early morning haul" if is_en else "Recolhimento na madrugada"
    elif "multipeixe" in low or "05h04" in low:
        scene = "Multiple deck captures" if is_en else "Múltiplas capturas no convés"
    elif "12h" in low:
        scene = "Daytime haul" if is_en else "Recolhimento diurno"
    else:
        scene = "Video analysis" if is_en else "Análise de captura"

    # Hora curta da geração para diferenciar análises na mesma janela sem mostrar "run_..."
    created = str(cfg.get("created_at", ""))
    hhmm = created[11:16] if len(created) >= 16 else ""

    icon = "🎬" if has_hud else ("🐟" if n_fish > 0 else "⚪")
    fish_word = ("fish" if n_fish == 1 else "fish") if is_en else ("peixe" if n_fish == 1 else "peixes")
    hud_tag = (" · Vídeo" if not is_en else " · Video") if has_hud else ""
    win_part = f" ({win_txt})" if win_txt else ""
    time_part = f" [{hhmm}]" if hhmm else ""

    label = f"{icon} {vid_label} · {scene}{win_part} — {n_fish} {fish_word}{hud_tag}{time_part}"
    # Prioridade no dropdown: análises com vídeo HUD primeiro, depois com peixes, depois 0 peixes
    priority = (0 if has_hud else (1 if n_fish > 0 else 2))
    return label, priority, run_dir.name


def render_em_monitoring_tab() -> None:
    """Painel de Monitoramento Eletrônico (EM): contagem, classe, tamanho médio, erro ±% e calibração px->cm."""
    is_en = st.session_state.get("lang", "pt") == "en"
    title = "Electronic Monitoring — Counting & Morphometry (EM)" if is_en else "Monitoramento Eletrônico (EM) — Contagem & Biometria"
    subtitle = (
        "Audit consolidated video captures, inspect average fish length, error margin (±%), "
        "estimated class, and convert measurements to centimeters in real time."
        if is_en
        else "Audite capturas consolidadas em vídeo, visualize o tamanho médio, "
        "a margem de erro (±%), a classe estimada e converta pixels para centímetros em tempo real."
    )
    st.markdown(
        f"""
        <div class="studio-card">
            <div class="eyebrow">FishID Studio · EM Analytics</div>
            <h3 style="margin:0.2rem 0 0.4rem 0; color:#0F172A;">{html.escape(title)}</h3>
            <p style="margin:0; color:#475569; font-size:0.95rem;">{html.escape(subtitle)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    exp_dir = _find_em_experiments_dir()
    run_dirs: list[Path] = []
    if exp_dir is not None:
        run_dirs = sorted(
            [d for d in exp_dir.iterdir() if d.is_dir() and (d / "resumo_peixes.csv").is_file()],
            key=lambda p: p.name,
            reverse=True,
        )

    col_sel, col_cal = st.columns([1.35, 1.0], gap="medium")
    selected_run: Path | None = None
    df = pd.DataFrame()
    run_cfg: dict[str, Any] = {}

    with col_sel:
        if run_dirs:
            options_meta = [(_format_em_run_option(d, is_en), d) for d in run_dirs]
            options_meta.sort(key=lambda item: (item[0][1], item[1].name), reverse=False)
            # Dentro da mesma prioridade, mostra mais recentes primeiro
            options_meta.sort(key=lambda item: (item[0][1], -int(item[1].stat().st_mtime)))
            label_to_dir: dict[str, Path] = {}
            labels: list[str] = []
            for (lbl, _, _), d in options_meta:
                final_lbl = lbl
                suffix = 2
                while final_lbl in label_to_dir:
                    final_lbl = f"{lbl} ({suffix})"
                    suffix += 1
                label_to_dir[final_lbl] = d
                labels.append(final_lbl)

            choice = st.selectbox(
                "Select analysis" if is_en else "Selecionar análise",
                options=labels,
                index=0,
                key="em_run_select",
            )
            selected_run = label_to_dir[choice]
            resumo_path = selected_run / "resumo_peixes.csv"
            df = _load_em_run_data(str(resumo_path), resumo_path.stat().st_mtime)
            cfg_path = selected_run / "config_experimento.json"
            if cfg_path.is_file():
                try:
                    run_cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                except Exception:
                    run_cfg = {}
        else:
            up_csv = st.file_uploader(
                "Upload resumo_peixes.csv" if is_en else "Envie um arquivo resumo_peixes.csv",
                type=["csv"],
                key="em_csv_upload",
            )
            if up_csv is not None:
                try:
                    df = pd.read_csv(up_csv)
                except Exception:
                    df = pd.DataFrame()

    with col_cal:
        st.markdown(
            "**Escala física (cm ↔ px)**" if not is_en else "**Physical scale (cm ↔ px)**"
        )
        c_ref1, c_ref2 = st.columns(2)
        with c_ref1:
            ref_cm = st.number_input(
                "Reference (cm)" if is_en else "Referência real (cm)",
                min_value=10.0,
                max_value=500.0,
                value=100.0,
                step=5.0,
                help="Medida real do tapete ou referência conhecida no convés." if not is_en else "Real width/length of deck mat or reference.",
                key="em_ref_cm",
            )
        with c_ref2:
            ref_px = st.number_input(
                "Reference (px)" if is_en else "Na imagem (px)",
                min_value=50.0,
                max_value=3000.0,
                value=650.0,
                step=10.0,
                key="em_ref_px",
            )
        cm_por_px = float(ref_cm) / max(1.0, float(ref_px))
        st.caption(f"Escala ativa: **1 px = {cm_por_px:.3f} cm** (`{ref_cm:.0f} cm / {ref_px:.0f} px`)")

    if df.empty:
        st.info(
            "No fish recorded in this analysis (0 detections)."
            if is_en
            else "Nenhum peixe registrado nesta análise (0 detecções)."
        )
        return

    # Normaliza colunas para compatibilidade e calcula SEMPRE cm + px + faixa com erro
    size_col = "tamanho_medio_px" if "tamanho_medio_px" in df.columns else (
        "comprimento_curva_p75_px" if "comprimento_curva_p75_px" in df.columns else "comprimento_curva_mediana_px"
    )
    df_view = df.copy()
    sizes_px = pd.to_numeric(df_view[size_col], errors="coerce").fillna(0.0)
    if "erro_estimado_pct" in df_view.columns:
        errs_pct = pd.to_numeric(df_view["erro_estimado_pct"], errors="coerce").fillna(5.0)
    else:
        errs_pct = pd.Series(5.0, index=df_view.index)

    sizes_cm = sizes_px * cm_por_px
    margin_px = sizes_px * (errs_pct / 100.0)
    margin_cm = sizes_cm * (errs_pct / 100.0)

    df_view["tamanho_px"] = sizes_px.round(1)
    df_view["min_px"] = (sizes_px - margin_px).clip(lower=0.0).round(1)
    df_view["max_px"] = (sizes_px + margin_px).round(1)
    df_view["tamanho_cm"] = sizes_cm.round(1)
    df_view["min_cm"] = (sizes_cm - margin_cm).clip(lower=0.0).round(1)
    df_view["max_cm"] = (sizes_cm + margin_cm).round(1)
    df_view["fator_cm_por_px"] = round(cm_por_px, 4)

    df_view["faixa_cm_erro"] = [
        f"{lo:.1f} – {hi:.1f} cm (±{ep:.1f}%)"
        for lo, hi, ep in zip(df_view["min_cm"], df_view["max_cm"], errs_pct)
    ]
    df_view["faixa_px_erro"] = [
        f"{lo:.0f} – {hi:.0f} px"
        for lo, hi in zip(df_view["min_px"], df_view["max_px"])
    ]

    n_fish = len(df_view)
    avg_cm = float(df_view["tamanho_cm"].mean()) if n_fish else 0.0
    avg_px = float(df_view["tamanho_px"].mean()) if n_fish else 0.0
    avg_err = float(errs_pct.mean()) if n_fish else 0.0
    avg_lo_cm = max(0.0, avg_cm * (1.0 - avg_err / 100.0))
    avg_hi_cm = avg_cm * (1.0 + avg_err / 100.0)
    avg_lo_px = max(0.0, avg_px * (1.0 - avg_err / 100.0))
    avg_hi_px = avg_px * (1.0 + avg_err / 100.0)

    top_class = (
        str(df_view["classe_estimada"].value_counts().index[0])
        if "classe_estimada" in df_view.columns and not df_view["classe_estimada"].dropna().empty
        else "Peixe Pelágico"
    )
    high_q = (
        int(df_view["qualidade_medicao"].isin(["ALTA", "MEDIA"]).sum())
        if "qualidade_medicao" in df_view.columns
        else n_fish
    )

    k1, k2, k3, k4 = st.columns([0.85, 1.35, 1.15, 0.95])
    k1.metric("Peixes Contados" if not is_en else "Counted Fish", f"{n_fish}")
    k2.metric(
        "Tamanho Médio (cm)" if not is_en else "Avg Length (cm)",
        f"{avg_cm:.1f} cm",
        delta=f"Com erro (±{avg_err:.1f}%): {avg_lo_cm:.1f}–{avg_hi_cm:.1f} cm",
        delta_color="off",
    )
    k3.metric(
        "Tamanho Médio (px)" if not is_en else "Avg Length (px)",
        f"{avg_px:.0f} px",
        delta=f"Com erro: {avg_lo_px:.0f}–{avg_hi_px:.0f} px",
        delta_color="off",
    )
    k4.metric("Qualidade Alta/Média" if not is_en else "High/Med Quality", f"{high_q}/{n_fish} ({100*high_q/max(1,n_fish):.0f}%)")

    if run_cfg:
        st.caption(
            f"Classe predominante: **{top_class}** · Vídeo: `{run_cfg.get('video_name', '-')}` · "
            f"Janela: `{run_cfg.get('start_hms', '-')}` → `{run_cfg.get('end_hms', '-')}`"
        )

    # Vídeo anotado HUD (se gerado com --save-video)
    if selected_run is not None:
        hud_vid = selected_run / "video_anotado_hud.mp4"
        if hud_vid.is_file():
            with st.expander("🎬 Vídeo Anotado com HUD ao Vivo" if not is_en else "🎬 Annotated HUD Video", expanded=True):
                playable = _ensure_browser_h264(str(hud_vid), hud_vid.stat().st_mtime)
                st.video(playable)

    # Gráfico de comprimentos (cm + faixa) + composição por classe
    ch1, ch2 = st.columns([1.2, 1.0], gap="medium")
    with ch1:
        st.markdown("**Distribuição de comprimentos (cm — com mínimo e máximo do erro)**" if not is_en else "**Length distribution (cm — with error bounds)**")
        chart_df = pd.DataFrame(
            {
                "Indivíduo": [f"#{i}" for i in df_view.iloc[:, 0]],
                "Mínimo (cm)": df_view["min_cm"].values,
                "Estimado (cm)": df_view["tamanho_cm"].values,
                "Máximo (cm)": df_view["max_cm"].values,
            }
        ).set_index("Indivíduo")
        st.bar_chart(chart_df, height=250)
    with ch2:
        if "classe_estimada" in df_view.columns:
            st.markdown("**Composição por classe**" if not is_en else "**Composition by class**")
            cls_counts = df_view["classe_estimada"].value_counts().rename_axis("Classe").to_frame("Contagem")
            st.bar_chart(cls_counts, height=250)

    # Tabela limpa mostrando cm + faixa com erro + px + faixa com erro lado a lado
    table_df = pd.DataFrame()
    table_df["Indivíduo" if not is_en else "ID"] = [f"#{int(i)}" for i in df_view.iloc[:, 0]]
    if "classe_estimada" in df_view.columns:
        table_df["Classe" if not is_en else "Class"] = df_view["classe_estimada"]
    if "inicio_hms" in df_view.columns and "fim_hms" in df_view.columns:
        table_df["Janela" if not is_en else "Window"] = df_view["inicio_hms"].astype(str) + " → " + df_view["fim_hms"].astype(str)
    table_df["Tamanho (cm)" if not is_en else "Length (cm)"] = df_view["tamanho_cm"].map(lambda v: f"{v:.1f} cm")
    table_df["Faixa c/ erro (cm)" if not is_en else "Range w/ error (cm)"] = df_view["faixa_cm_erro"]
    table_df["Tamanho (px)" if not is_en else "Length (px)"] = df_view["tamanho_px"].map(lambda v: f"{v:.0f} px")
    table_df["Faixa c/ erro (px)" if not is_en else "Range w/ error (px)"] = df_view["faixa_px_erro"]
    if "qualidade_medicao" in df_view.columns:
        table_df["Qualidade" if not is_en else "Quality"] = df_view["qualidade_medicao"]

    st.dataframe(table_df, use_container_width=True, hide_index=True)

    st.download_button(
        label="⬇ Baixar planilha completa com cm, px e faixas de erro (CSV)" if not is_en else "⬇ Download full report with cm, px & error bounds (CSV)",
        data=df_view.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{selected_run.name if selected_run else 'fishid_em'}_calibrado.csv",
        mime="text/csv",
        key="em_dl_csv",
    )

    # Galeria visual dos cards de auditoria (contorno + biometria)
    if selected_run is not None and "imagem_auditoria" in df_view.columns:
        st.markdown("### 🔬 Auditoria Visual (Contorno e Biometria)" if not is_en else "### 🔬 Visual Audit (Contour & Morphometry)")
        for idx_r, row in df_view.iterrows():
            rel = str(row.get("imagem_auditoria", "")).strip()
            if not rel:
                continue
            img_path = selected_run / rel
            if img_path.is_file():
                ep = float(errs_pct.loc[idx_r])
                cap_txt = (
                    f"Indivíduo #{int(row.iloc[0])} · {row.get('classe_estimada', 'Peixe')} · "
                    f"{row['tamanho_cm']:.1f} cm (faixa: {row['min_cm']:.1f}–{row['max_cm']:.1f} cm) · "
                    f"{row['tamanho_px']:.0f} px (faixa: {row['min_px']:.0f}–{row['max_px']:.0f} px · ±{ep:.1f}%)"
                    + (f" · Qualidade: {row['qualidade_medicao']}" if "qualidade_medicao" in row else "")
                )
                st.image(str(img_path), caption=cap_txt, use_container_width=True)


def main() -> None:
    inject_enterprise_css()
    render_animated_ocean_background()

    backend_info = fetch_backend_info(BACKEND_URL)
    sample_items, sample_origin, sample_error = get_sample_gallery()

    render_top_navbar()
    render_executive_hero(backend_info=backend_info, total_gallery_photos=len(sample_items))

    tab_img, tab_vid, tab_em = st.tabs([t("tab_photo"), t("tab_video"), t("tab_em")])

    with tab_img:
        render_image_tab(
            backend_info=backend_info,
            sample_items=sample_items,
            sample_origin=sample_origin,
            sample_error=sample_error,
        )

    with tab_vid:
        render_video_tab(backend_info=backend_info)

    with tab_em:
        render_em_monitoring_tab()

    render_institutional_footer()


if __name__ == "__main__":
    main()
