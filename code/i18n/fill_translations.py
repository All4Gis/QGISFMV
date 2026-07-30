#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fill QGIS FMV .ts translation files for Transifex upload.

Usage (from repo root):
    python3 code/i18n/fill_translations.py
    python3 code/i18n/fill_translations.py --no-auto   # manual dict + en only

Requires ``deep-translator`` for automatic fill of new languages (pip install deep-translator).
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

I18N_DIR = Path(__file__).resolve().parent

LANG_FILES = {
    "en": "qgisfmv_en.ts",
    "es": "qgisfmv_es.ts",
    "ca": "qgisfmv_ca.ts",
    "gl": "qgisfmv_gl.ts",
    "fr": "qgisfmv_fr.ts",
    "it": "qgisfmv_it.ts",
    "fa": "qgisfmv_fa.ts",
    "de": "qgisfmv_de.ts",
    "pt": "qgisfmv_pt.ts",
    "pt_BR": "qgisfmv_pt_BR.ts",
    "nl": "qgisfmv_nl.ts",
    "ru": "qgisfmv_ru.ts",
    "pl": "qgisfmv_pl.ts",
    "uk": "qgisfmv_uk.ts",
    "zh_CN": "qgisfmv_zh_CN.ts",
    "ja": "qgisfmv_ja.ts",
    "ar": "qgisfmv_ar.ts",
}

# Google Translate target codes
GT_LANG = {
    "en": "en",
    "es": "es",
    "ca": "ca",
    "gl": "gl",
    "fr": "fr",
    "it": "it",
    "fa": "fa",
    "de": "de",
    "pt": "pt",
    "pt_BR": "pt",
    "nl": "nl",
    "ru": "ru",
    "pl": "pl",
    "uk": "uk",
    "zh_CN": "zh-CN",
    "ja": "ja",
    "ar": "ar",
}

# FMV-specific overrides (keep brand terms / acronyms consistent)
KEEP_LITERAL = re.compile(
    r"^(FMV|UAV|YOLO|ONNX|VisDrone|COCO|OpenCV|CSV|PDF|KML|GPX|HUD|"
    r"NRVI|VARI|ExG|ExR|CLAHE|MOG2|MISB|KLV|FFmpeg|ffprobe|EPSG|"
    r"Ctrl\+|Alt\+|UDP|TCP|RTP|RTSP|DJI|APP-6D|QGIS|STANAG|"
    r"\d+[,.]?\d*\s*(MB|ms|px|m|km|%|°)|"
    r"about:blank|\{\}|\.ts|\.onnx|\.csv|\.txt|\.log|"
    r"3,4,5,8,9|0,1|2,3,5,7|0\.15|0\.45|640)$",
    re.I,
)

# Curated overrides per language (high-visibility UI + AI strings)
MANUAL: dict[str, dict[str, str]] = {
    "es": {
        "AI Detection": "Detección IA",
        "YOLO (VisDrone) + smart CV for FMV / UAV imagery": "YOLO (VisDrone) + CV inteligente para vídeo FMV / UAV",
        "Building (CV + AI)": "Edificios (CV + IA)",
        "Road (CV + AI)": "Carretera (CV + IA)",
        "Vehicle (YOLO AI)": "Vehículos (YOLO IA)",
        "Person (YOLO AI)": "Personas (YOLO IA)",
        "Fire (CV + AI)": "Incendio (CV + IA)",
        "Smoke (CV + AI)": "Humo (CV + IA)",
        "Flood (CV + AI)": "Inundación (CV + IA)",
        "Use YOLO/ONNX for segmentation filters": "Usar YOLO/ONNX en filtros de segmentación",
        "Download VisDrone aerial model (~6 MB + ONNX export)": "Descargar modelo aéreo VisDrone (~6 MB + export ONNX)",
        "Download YOLOv8n COCO (~13 MB, ground-level)": "Descargar YOLOv8n COCO (~13 MB, nivel suelo)",
        "Aerial (VisDrone, FMV/UAV)": "Aéreo (VisDrone, FMV/UAV)",
        "Ground-level (COCO)": "Nivel suelo (COCO)",
        "Custom class IDs": "IDs de clase personalizados",
        "VisDrone model ready": "Modelo VisDrone listo",
        "YOLO model ready": "Modelo YOLO listo",
        "FMV Settings": "Ajustes FMV",
        "Mosaic": "Mosaico",
        "Filters": "Filtros",
        "FMV Tools": "Herramientas FMV",
        "Building structures — smart CV with optional custom YOLO ONNX (FMV Settings).": "Estructuras/edificios — CV inteligente con YOLO ONNX opcional (Ajustes FMV).",
        "Road/asphalt segmentation — smart CV with optional custom YOLO ONNX.": "Segmentación de carretera/asfalto — CV inteligente con YOLO ONNX opcional.",
        "VisDrone YOLO detection for aerial vehicles; falls back to smart CV when YOLO finds nothing.": "Detección YOLO VisDrone de vehículos aéreos; pasa a CV inteligente si YOLO no encuentra nada.",
        "VisDrone YOLO person detection for FMV; smart CV fallback when no ONNX hits.": "Detección de personas YOLO VisDrone; fallback CV inteligente sin detecciones ONNX.",
        "For FMV and UAV video use VisDrone (aerial profile). YOLOv8n COCO is for ground-level imagery. Building, road, fire, smoke and flood still use classical CV unless you add a custom ONNX.": "Para vídeo FMV/UAV use VisDrone (perfil aéreo). YOLOv8n COCO es para imágenes a nivel de suelo. Edificio, carretera, fuego, humo e inundación usan CV clásico salvo que añada un ONNX personalizado.",
    },
    "ca": {
        "AI Detection": "Detecció IA",
        "Filters": "Filtres",
        "FMV Settings": "Configuració FMV",
        "Building (CV + AI)": "Edificis (CV + IA)",
        "Vehicle (YOLO AI)": "Vehicles (YOLO IA)",
        "Person (YOLO AI)": "Persones (YOLO IA)",
    },
    "fr": {
        "AI Detection": "Détection IA",
        "Filters": "Filtres",
        "FMV Settings": "Paramètres FMV",
        "Building (CV + AI)": "Bâtiments (CV + IA)",
        "Vehicle (YOLO AI)": "Véhicules (YOLO IA)",
        "Person (YOLO AI)": "Personnes (YOLO IA)",
    },
    "it": {
        "AI Detection": "Rilevamento IA",
        "Filters": "Filtri",
        "FMV Settings": "Impostazioni FMV",
        "Building (CV + AI)": "Edifici (CV + IA)",
        "Vehicle (YOLO AI)": "Veicoli (YOLO IA)",
        "Person (YOLO AI)": "Persone (YOLO IA)",
    },
    "gl": {
        "AI Detection": "Detección IA",
        "Filters": "Filtros",
        "FMV Settings": "Axustes FMV",
    },
    "de": {
        "AI Detection": "KI-Erkennung",
        "Filters": "Filter",
        "FMV Settings": "FMV-Einstellungen",
        "Building (CV + AI)": "Gebäude (CV + KI)",
        "Vehicle (YOLO AI)": "Fahrzeuge (YOLO KI)",
        "Person (YOLO AI)": "Personen (YOLO KI)",
    },
    "pt": {
        "AI Detection": "Deteção IA",
        "Filters": "Filtros",
        "FMV Settings": "Definições FMV",
        "Building (CV + AI)": "Edifícios (CV + IA)",
        "Vehicle (YOLO AI)": "Veículos (YOLO IA)",
        "Person (YOLO AI)": "Pessoas (YOLO IA)",
    },
    "pt_BR": {
        "AI Detection": "Detecção IA",
        "Filters": "Filtros",
        "FMV Settings": "Configurações FMV",
        "Building (CV + AI)": "Edifícios (CV + IA)",
        "Vehicle (YOLO AI)": "Veículos (YOLO IA)",
        "Person (YOLO AI)": "Pessoas (YOLO IA)",
    },
}


def collect_sources(ts_path: Path) -> list[str]:
    """Return unique source strings from a Qt .ts translation file."""
    tree = ET.parse(ts_path)
    sources = []
    seen = set()
    for msg in tree.getroot().iter("message"):
        src = msg.find("source")
        if src is None or not src.text:
            continue
        text = src.text
        if text not in seen:
            seen.add(text)
            sources.append(text)
    return sources


def should_keep_literal(text: str) -> bool:
    """Return True if *text* should be kept untranslated (URLs, punctuation, etc.)."""
    if not text.strip():
        return True
    if text.startswith("http") or "github" in text.lower():
        return True
    if KEEP_LITERAL.search(text.strip()):
        return True
    # Mostly punctuation / numbers
    if len(re.sub(r"[\W\d_]+", "", text)) < 2:
        return True
    return False


def auto_translate(sources: list[str], target: str) -> dict[str, str]:
    """Translate a list of source strings to *target* language via Google Translate."""
    from deep_translator import GoogleTranslator

    translator = GoogleTranslator(source="en", target=target)
    out: dict[str, str] = {}
    batch: list[str] = []
    batch_keys: list[str] = []

    def flush():
        nonlocal batch, batch_keys
        if not batch:
            return
        try:
            results = translator.translate_batch(batch)
            for key, val in zip(batch_keys, results):
                out[key] = val or key
        except Exception as exc:
            print(f"  batch translate error ({target}): {exc}", file=sys.stderr)
            for key in batch_keys:
                out[key] = key
        batch = []
        batch_keys = []
        time.sleep(0.3)

    for src in sources:
        if should_keep_literal(src):
            out[src] = src
            continue
        batch.append(src)
        batch_keys.append(src)
        if len(batch) >= 40:
            flush()
    flush()
    return out


def apply_translations(
    ts_path: Path, lang: str, mapping: dict[str, str]
) -> tuple[int, int]:
    """Apply *mapping* translations into a .ts file; returns (filled, kept_literal) counts."""
    tree = ET.parse(ts_path)
    root = tree.getroot()
    filled = kept = 0
    for msg in root.iter("message"):
        src_el = msg.find("source")
        tr_el = msg.find("translation")
        if src_el is None or tr_el is None:
            continue
        if tr_el.get("type") == "obsolete":
            continue
        source = src_el.text or ""
        existing = tr_el.text or ""
        if tr_el.get("type") != "unfinished" and existing.strip():
            kept += 1
            continue
        if lang == "en":
            text = source
        else:
            text = (
                MANUAL.get(lang, {}).get(source)
                or mapping.get(source)
                or existing
                or source
            )
        tr_el.text = text
        if tr_el.get("type") == "unfinished":
            del tr_el.attrib["type"]
        filled += 1
    if root.get("language") != lang.replace("_", "-") if lang == "zh_CN" else lang:
        root.set("language", "zh_CN" if lang == "zh_CN" else lang)
    tree.write(ts_path, encoding="utf-8", xml_declaration=True)
    return filled, kept


def main():
    """CLI entry point: auto-translate and fill all .ts files from the English source."""
    parser = argparse.ArgumentParser(description="Fill QGIS FMV translation TS files")
    parser.add_argument(
        "--no-auto", action="store_true", help="Skip Google auto-translate"
    )
    args = parser.parse_args()

    en_path = I18N_DIR / LANG_FILES["en"]
    sources = collect_sources(en_path)
    print(f"Unique sources: {len(sources)}")

    cache: dict[str, dict[str, str]] = {"en": {s: s for s in sources}}

    if not args.no_auto:
        try:
            from deep_translator import GoogleTranslator  # noqa: F401
        except ImportError:
            print(
                "Install deep-translator: pip install deep-translator", file=sys.stderr
            )
            sys.exit(1)
        for lang in LANG_FILES:
            if lang == "en":
                continue
            gt = GT_LANG[lang]
            print(f"Auto-translating -> {lang} ({gt})...")
            cache[lang] = auto_translate(sources, gt)
            # Re-apply manual overrides
            cache[lang].update(MANUAL.get(lang, {}))

    for lang, fname in LANG_FILES.items():
        path = I18N_DIR / fname
        if not path.exists():
            print(f"Skip missing {fname}")
            continue
        mapping = cache.get(lang, {})
        if lang == "en":
            mapping = {s: s for s in sources}
        filled, kept = apply_translations(path, lang, mapping)
        unfinished = sum(
            1
            for _ in ET.parse(path).getroot().iter("translation")
            if _.get("type") == "unfinished"
        )
        print(f"  {fname}: filled {filled}, kept {kept}, unfinished left {unfinished}")


if __name__ == "__main__":
    main()
