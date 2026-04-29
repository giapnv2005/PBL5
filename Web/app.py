from __future__ import annotations

import atexit
import os
import sys
import time
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.controller import SystemController

app = Flask(__name__, template_folder="teamplates", static_folder="static")

print("[*] Initializing SystemController...")
controller = SystemController(
    model_path=str(PROJECT_ROOT / "Models" / "my_model.tflite"),
    labels_path=str(PROJECT_ROOT / "Models" / "labels.txt"),
    capture_dir=str(BASE_DIR / "static" / "captures"),
    database_path=str(PROJECT_ROOT / "data" / "PBL5.db"),
    serial_port="/dev/ttyUSB0",
    baudrate=9600,
)
print("[*] Starting controller...")
controller.start()
print("[OK] Application ready")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/history")
def history():
    return render_template("history.html")


def _frame_generator():
    while True:
        frame = controller.get_preview_stream_frame()
        if frame is None:
            time.sleep(0.05)
            continue
        yield b"--frame\r\nContent-Type: image/png\r\n\r\n" + frame + b"\r\n"


@app.route("/video_feed")
def video_feed():
    return Response(_frame_generator(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/result")
def result():
    payload = controller.get_result_payload()
    if payload["last_image"]:
        payload["last_image_url"] = f"/static/{payload['last_image']}"
    else:
        payload["last_image_url"] = ""
    return jsonify(payload)


@app.route("/trigger", methods=["POST"])
def trigger():
    payload = controller.process_detected()
    if payload is None:
        return jsonify({"status": "error", "message": "capture_failed"}), 500
    payload["status"] = "success"
    if payload["last_image"]:
        payload["last_image_url"] = f"/static/{payload['last_image']}"
    return jsonify(payload)


def _normalize_image_url(image_path: str) -> str:
    if not image_path:
        return ""

    path = Path(image_path)
    static_dir = BASE_DIR / "static"

    if path.is_absolute():
        try:
            relative_path = path.resolve().relative_to(static_dir.resolve())
            return f"/static/{relative_path.as_posix()}"
        except Exception:
            return ""

    normalized = image_path.lstrip("/")
    if normalized.startswith("static/"):
        normalized = normalized[len("static/") :]
    return f"/static/{normalized}"


@app.route("/history-data")
def history_data():
    query = request.args.get("q", "")
    page = request.args.get("page", 1)
    page_size = request.args.get("page_size", 8)
    payload = controller.database.get_history_page(query=query, page=page, page_size=page_size)
    history = []
    for record in payload["rows"]:
        history.append(
            {
                "id": record["id"],
                "accessory": record["accessory"],
                "confident": record["confident"],
                "timestamp": record["timestamp"],
                "image_path": record["image_path"],
                "image_url": _normalize_image_url(record["image_path"]),
            }
        )
    return jsonify(
        {
            "history": history,
            "total": payload["total"],
            "page": payload["page"],
            "page_size": payload["page_size"],
            "total_pages": payload["total_pages"],
            "query": payload["query"],
        }
    )


@app.route("/history-delete", methods=["POST"])
def history_delete():
    image_paths = controller.database.delete_all_detections()
    removed_files = 0
    for image_path in image_paths:
        try:
            if image_path and os.path.exists(image_path):
                os.remove(image_path)
                removed_files += 1
        except OSError:
            pass
    return jsonify({"status": "success", "deleted": len(image_paths), "removed_files": removed_files})


@app.route("/start", methods=["POST"])
def start_system():
    controller.start()
    return jsonify({"status": "running"})


@app.route("/stop", methods=["POST"])
def stop_system():
    controller.stop()
    return jsonify({"status": "stopped"})


@atexit.register
def _shutdown() -> None:
    controller.stop()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)