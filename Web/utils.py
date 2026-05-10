"""Web utilities - Helper functions for Flask app."""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def normalize_image_url(image_path: Optional[str], static_dir: Path) -> str:
    """
    Normalize image path to serve from static folder.

    Args:
        image_path: Original image file path (absolute or relative)
        static_dir: Static directory path

    Returns:
        Normalized URL path for web serving
    """
    if not image_path:
        return ""

    path = Path(image_path)

    # Handle absolute paths
    if path.is_absolute():
        try:
            relative_path = path.resolve().relative_to(static_dir.resolve())
            return f"/static/{relative_path.as_posix()}"
        except Exception:
            return ""

    # Handle relative paths
    normalized = image_path.lstrip("/")
    if normalized.startswith("static/"):
        normalized = normalized[len("static/") :]
    return f"/static/{normalized}"
