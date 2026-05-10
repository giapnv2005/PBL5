"""Main Flask Application Entry Point.

This is kept for backward compatibility. Modern code should use
the Application Factory pattern via app_factory.py
"""

from __future__ import annotations

import atexit
from pathlib import Path

from Web.app_factory import create_app

# Create app using factory pattern
app = create_app(root_path=Path(__file__).resolve().parent.parent)


@atexit.register
def _shutdown() -> None:
    """Shutdown handler - stop controller on exit."""
    if hasattr(app, 'controller'):
        app.controller.stop()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
