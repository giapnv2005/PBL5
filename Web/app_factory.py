"""Flask Application Factory - Creates Flask app with proper initialization."""

from __future__ import annotations

from pathlib import Path

from flask import Flask

from src.config import Config, ControllerFactory


def create_app(root_path: Path = None) -> Flask:
    """
    Create and configure Flask application.

    Uses application factory pattern to separate app creation from
    business logic initialization, following AI+IoT best practices.

    Args:
        root_path: Project root directory

    Returns:
        Configured Flask application
    """
    if root_path is None:
        root_path = Path(__file__).resolve().parent.parent

    # Create Flask app with absolute paths
    template_dir = str(root_path / "Web" / "teamplates")
    static_dir = str(root_path / "Web" / "static")
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

    # Initialize config
    config = Config.from_root(root_path)

    # Store config in app context
    app.config.from_object({
        "ROOT_PATH": root_path,
        "CONFIG": config,
    })

    # Initialize controller (singleton)
    print("[*] Initializing SystemController...")
    controller = ControllerFactory.get_or_create(config)
    app.controller = controller
    print("[*] Starting controller...")
    controller.start()
    print("[OK] Application ready")

    # Register routes (import after app is created)
    from Web.routes import register_routes
    register_routes(app)

    return app
