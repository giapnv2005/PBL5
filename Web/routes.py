"""Flask Routes - API endpoints for PBL5 AI+IoT System."""

from __future__ import annotations

import os
import time
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

from Web.utils import normalize_image_url


def register_routes(app: Flask) -> None:
    """
    Register all API routes to Flask app.

    Args:
        app: Flask application instance
    """
    controller = app.controller
    root_path = Path(app.config.get("ROOT_PATH", Path(__file__).resolve().parent.parent))
    static_dir = root_path / "Web" / "static"

    # ====================================================================
    # Web Pages
    # ====================================================================

    @app.route("/")
    def index():
        """Dashboard main page."""
        return render_template("index.html")

    @app.route("/history")
    def history():
        """History page."""
        return render_template("history.html")

    # ====================================================================
    # Video Stream
    # ====================================================================

    def _frame_generator():
        """Generate frames for video stream."""
        while True:
            frame = controller.get_preview_stream_frame()
            if frame is None:
                time.sleep(0.05)
                continue
            yield b"--frame\r\nContent-Type: image/png\r\n\r\n" + frame + b"\r\n"

    @app.route("/video_feed")
    def video_feed():
        """Stream live camera frames."""
        return Response(
            _frame_generator(),
            mimetype="multipart/x-mixed-replace; boundary=frame"
        )

    # ====================================================================
    # API Endpoints - Status and Results
    # ====================================================================

    @app.route("/result")
    def result():
        """Get current system state and last detection result."""
        payload = controller.get_result_payload()
        if payload["last_image"]:
            payload["last_image_url"] = f"/static/{payload['last_image']}"
        else:
            payload["last_image_url"] = ""
        return jsonify(payload)

    @app.route("/trigger", methods=["POST"])
    def trigger():
        """Manually trigger one detection cycle (for testing)."""
        payload = controller.process_detected()
        if payload is None:
            return jsonify({"status": "error", "message": "capture_failed"}), 500
        payload["status"] = "success"
        if payload["last_image"]:
            payload["last_image_url"] = f"/static/{payload['last_image']}"
        return jsonify(payload)

    # ====================================================================
    # API Endpoints - History Management
    # ====================================================================

    @app.route("/history-data")
    def history_data():
        """Get paginated detection history."""
        query = request.args.get("q", "")
        page = request.args.get("page", 1)
        page_size = request.args.get("page_size", 8)

        payload = controller.database.get_history_page(
            query=query,
            page=page,
            page_size=page_size
        )

        history = []
        for record in payload["rows"]:
            history.append({
                "id": record["id"],
                "accessory": record["accessory"],
                "confident": record["confident"],
                "timestamp": record["timestamp"],
                "image_path": record["image_path"],
                "image_url": normalize_image_url(record["image_path"], static_dir),
            })

        return jsonify({
            "history": history,
            "total": payload["total"],
            "page": payload["page"],
            "page_size": payload["page_size"],
            "total_pages": payload["total_pages"],
            "query": payload["query"],
        })

    @app.route("/history-delete", methods=["POST"])
    def history_delete():
        """Delete all detection history and images."""
        image_paths = controller.database.delete_all_detections()
        removed_files = 0
        for image_path in image_paths:
            try:
                if image_path and os.path.exists(image_path):
                    os.remove(image_path)
                    removed_files += 1
            except OSError:
                pass
        return jsonify({
            "status": "success",
            "deleted": len(image_paths),
            "removed_files": removed_files
        })

    # ====================================================================
    # API Endpoints - System Control
    # ====================================================================

    @app.route("/start", methods=["POST"])
    def start_system():
        """Start the classification system."""
        controller.start()
        return jsonify({"status": "running"})

    @app.route("/stop", methods=["POST"])
    def stop_system():
        """Stop the classification system."""
        controller.stop()
        return jsonify({"status": "stopped"})
