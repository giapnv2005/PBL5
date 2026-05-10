"""Configuration and initialization for PBL5 AI+IoT System.

Centralizes all configuration and controller initialization
to decouple from Flask application.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.controller import SystemController


class Config:
    """Application configuration."""

    # Model paths
    MODEL_PATH: str = "Models/my_model.tflite"
    LABELS_PATH: str = "Models/labels.txt"

    # Capture and database
    CAPTURE_DIR: str = "Web/static/captures"
    DATABASE_PATH: str = "data/PBL5.db"

    # Serial communication
    SERIAL_PORT: str = "/dev/ttyUSB0"
    BAUDRATE: int = 9600

    # Camera settings
    CAMERA_WIDTH: int = 640
    CAMERA_HEIGHT: int = 480

    # Flask settings
    HOST: str = "0.0.0.0"
    PORT: int = 5000
    DEBUG: bool = False

    @classmethod
    def from_root(cls, root_path: Path) -> Config:
        """Create config with root path context."""
        config = cls()
        config.MODEL_PATH = str(root_path / cls.MODEL_PATH)
        config.LABELS_PATH = str(root_path / cls.LABELS_PATH)
        config.CAPTURE_DIR = str(root_path / cls.CAPTURE_DIR)
        config.DATABASE_PATH = str(root_path / cls.DATABASE_PATH)
        return config


class ControllerFactory:
    """Factory for creating SystemController instances."""

    _instance: Optional[SystemController] = None

    @classmethod
    def create(cls, config: Config) -> SystemController:
        """
        Create a SystemController instance.

        Args:
            config: Configuration object

        Returns:
            SystemController instance
        """
        controller = SystemController(
            model_path=config.MODEL_PATH,
            labels_path=config.LABELS_PATH,
            capture_dir=config.CAPTURE_DIR,
            database_path=config.DATABASE_PATH,
            serial_port=config.SERIAL_PORT,
            baudrate=config.BAUDRATE,
        )
        return controller

    @classmethod
    def get_or_create(cls, config: Config) -> SystemController:
        """
        Get singleton instance or create new one.

        Args:
            config: Configuration object

        Returns:
            SystemController instance
        """
        if cls._instance is None:
            cls._instance = cls.create(config)
        return cls._instance

    @classmethod
    def set_instance(cls, controller: SystemController) -> None:
        """Set controller instance (for testing)."""
        cls._instance = controller

    @classmethod
    def reset(cls) -> None:
        """Reset instance (for testing)."""
        if cls._instance is not None:
            cls._instance.stop()
        cls._instance = None
