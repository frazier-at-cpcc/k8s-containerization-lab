from __future__ import annotations

import shutil
from pathlib import Path


def snapshot_python_artifacts(root: Path) -> set[Path]:
    """Capture Python cache artifacts under the repository root."""
    root = root.resolve()
    artifacts: set[Path] = set()

    for cache_dir in root.rglob("__pycache__"):
        if cache_dir.is_dir():
            artifacts.add(cache_dir)

    for pattern in ("*.pyc", "*.pyo"):
        for cache_file in root.rglob(pattern):
            if cache_file.is_file():
                artifacts.add(cache_file)

    return artifacts


def cleanup_python_artifacts(root: Path, baseline: set[Path] | None = None) -> None:
    """
    Remove Python cache artifacts created during test execution.

    If `baseline` is provided, only newly created artifacts are removed.
    """
    root = root.resolve()
    current = snapshot_python_artifacts(root)
    targets = current if baseline is None else {path for path in current if path not in baseline}

    files = sorted((path for path in targets if path.is_file()), key=lambda p: len(p.parts), reverse=True)
    for path in files:
        try:
            path.unlink()
        except OSError:
            continue

    dirs = sorted((path for path in targets if path.is_dir()), key=lambda p: len(p.parts), reverse=True)
    for path in dirs:
        shutil.rmtree(path, ignore_errors=True)
