#!/usr/bin/env python3
# coding: utf-8
"""Create QGIS Plugin Zip for upload to QGIS Repository."""

import os
from configparser import ConfigParser
from fnmatch import fnmatch
from pathlib import Path
import ast
import shutil
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
CODE_DIR = REPO_ROOT / "code"
OUTPUT_DIR = SCRIPT_DIR / "Output"


# Directories and patterns to exclude from the plugin zip
EXCLUDE_PATTERNS = [
    # Directories
    "__pycache__",
    ".settings",
    "sql",
    "ui",
    "tests",
    ".git",
    "python_deps",  # legacy vendor dir — deps come from requirements.txt
    # File patterns
    "*.sh",
    "*.bat",
    "*.pro",
    "*.ts",
    "*.pyc",
    "*.bak",
    "*.yml",
    "*.ps1",
    "*.docx",
    "*.project",
    "*.pydevproject",
    ".gitignore",
    "settings.sample.ini",
    "requirement-dev.txt",
    "requirements-dev.txt",
]


def optimize_pngs(directory):
    """Optimize PNG images using Pillow (lossy reduction)."""
    try:
        from PIL import Image
    except ImportError:
        print("  [skip] Pillow not installed, PNG optimization skipped")
        return 0

    saved = 0
    for png in Path(directory).rglob("*.png"):
        original_size = png.stat().st_size
        try:
            img = Image.open(png)
            if img.mode == "RGBA":
                img = img.quantize(colors=256, method=2).convert("RGBA")
            else:
                img = img.quantize(colors=256, method=2).convert("RGB")
            img.save(png, optimize=True)
            new_size = png.stat().st_size
            saved += original_size - new_size
        except Exception:
            pass
    return saved


def optimize_svgs(directory):
    """Optimize SVG files by stripping metadata and comments."""
    try:
        from scour.scour import scourString, parse_args
    except ImportError:
        print("  [skip] scour not installed, SVG optimization skipped")
        return 0

    saved = 0
    for svg in Path(directory).rglob("*.svg"):
        original_size = svg.stat().st_size
        try:
            content = svg.read_text(encoding="utf-8")
            options = parse_args(
                [
                    "--enable-viewboxing",
                    "--enable-id-stripping",
                    "--enable-comment-stripping",
                    "--shorten-ids",
                    "--indent=none",
                    "--remove-metadata",
                ]
            )
            optimized = scourString(content, options=options)
            svg.write_text(optimized, encoding="utf-8")
            new_size = svg.stat().st_size
            saved += original_size - new_size
        except Exception:
            pass
    return saved


def strip_python_comments(directory):
    """Strip comments and docstrings from Python files."""
    saved = 0
    for py in Path(directory).rglob("*.py"):
        original_size = py.stat().st_size
        try:
            content = py.read_text(encoding="utf-8")
            tree = ast.parse(content)
            docstring_lines = set()
            for node in ast.walk(tree):
                if isinstance(
                    node,
                    (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module),
                ):
                    if (
                        node.body
                        and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, (ast.Constant, ast.Str))
                    ):
                        docstring_lines.add(node.body[0].lineno)

            lines = content.splitlines(keepends=True)
            new_lines = []
            in_docstring = False
            docstring_quote = None

            for i, line in enumerate(lines, 1):
                stripped = line.strip()

                if not in_docstring and i in docstring_lines:
                    for quote in ('"""', "'''"):
                        if quote in stripped:
                            count = stripped.count(quote)
                            if count == 1:
                                in_docstring = True
                                docstring_quote = quote
                                break
                            elif count >= 2:
                                break
                    if in_docstring:
                        continue

                if in_docstring:
                    if docstring_quote in stripped:
                        in_docstring = False
                    continue

                if stripped.startswith("#"):
                    continue

                new_lines.append(line)

            new_content = "".join(new_lines)
            if new_content != content:
                py.write_text(new_content, encoding="utf-8")
                new_size = py.stat().st_size
                saved += original_size - new_size
        except (SyntaxError, Exception):
            pass
    return saved


def make_ignore_fn(patterns):
    """Return a shutil.copytree ignore function."""

    def ignore(directory, contents):
        return {name for name in contents if any(fnmatch(name, p) for p in patterns)}

    return ignore


def copy_project_structure(patterns):
    """Copy project structure excluding dev/CI artifacts."""
    print("Copying structure...")
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    shutil.copytree(CODE_DIR, OUTPUT_DIR, ignore=make_ignore_fn(patterns))

    print(f"  -> {OUTPUT_DIR}")


def optimize_assets(directory):
    """Optimize images and strip Python comments in copied directory."""
    print("Optimizing assets...")
    total_saved = 0

    saved = optimize_pngs(directory)
    if saved > 0:
        print(f"  PNGs: saved {saved / 1024:.1f} KB")
        total_saved += saved

    saved = optimize_svgs(directory)
    if saved > 0:
        print(f"  SVGs: saved {saved / 1024:.1f} KB")
        total_saved += saved

    saved = strip_python_comments(directory)
    if saved > 0:
        print(f"  Python: saved {saved / 1024:.1f} KB")
        total_saved += saved

    if total_saved > 0:
        print(f"  Total saved: {total_saved / 1024:.1f} KB")
    else:
        print("  No optimization applied")


def create_zip(source_dir, zip_path):
    """Create a zip archive from source_dir."""
    print(f"Creating {zip_path.name}...")
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", source_dir)
    print(f"  -> {zip_path}")


def main():
    """Main build function."""
    metadata = CODE_DIR / "metadata.txt"
    if not metadata.exists():
        print(f"Error: {metadata} not found")
        sys.exit(1)

    cp = ConfigParser()
    with metadata.open() as f:
        cp.read_file(f)

    if not cp.has_option("general", "internal_name") or not cp.has_option(
        "general", "version"
    ):
        print("Error: metadata.txt missing required fields")
        sys.exit(1)

    internal_name = cp.get("general", "internal_name")
    version = cp.get("general", "version")

    copy_project_structure(EXCLUDE_PATTERNS)
    optimize_assets(OUTPUT_DIR)
    zip_path = OUTPUT_DIR.parent / f"{internal_name}_{version}.zip"
    create_zip(OUTPUT_DIR, zip_path)
    shutil.rmtree(OUTPUT_DIR)
    print("Done.")


if __name__ == "__main__":
    main()
