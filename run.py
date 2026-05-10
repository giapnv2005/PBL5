"""Entry point for PBL5 AI+IoT System.

Starts Flask web server with system controller.
"""

from __future__ import annotations

import os
from pathlib import Path

from Web.app_factory import create_app


def main() -> None:
    """Run the application."""
    project_root = Path(__file__).resolve().parent
    app = create_app(root_path=project_root)
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
