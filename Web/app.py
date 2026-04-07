from __future__ import annotations

import atexit
import sys
import time
from pathlib import Path

from flask import Flask, Response, jsonify, render_template

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
    serial_port="/dev/ttyUSB0",
    baudrate=9600,
)
print("[*] Starting controller...")
controller.start()
print("[OK] Application ready")


@app.route("/")
def index():
    return render_template("index.html")


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


@app.route("/latest_frame")
def latest_frame():
    frame = controller.get_preview_jpeg()
    if frame is None:
        # Uncomment for debugging:
        # print("[DEBUG] /latest_frame: Camera returned None")
        return "", 204
    return Response(frame, mimetype="image/jpeg")


@app.route("/result")
def result():
    payload = controller.get_result_payload()
    if payload["last_image"]:
        payload["last_image_url"] = f"/static/{payload['last_image']}"
    else:
        payload["last_image_url"] = ""
    return jsonify(payload)


@app.route("/get_data")
def get_data():
    payload = controller.get_result_payload()
    return jsonify(
        {
            "counts": payload["counts"],
            "last_image": f"/static/{payload['last_image']}" if payload["last_image"] else "",
            "last_result": payload["last_result"],
            "queue_size": payload["queue_size"],
        }
    )


@app.route("/trigger", methods=["POST"])
def trigger():
    payload = controller.process_detected()
    if payload is None:
        return jsonify({"status": "error", "message": "capture_failed"}), 500
    payload["status"] = "success"
    if payload["last_image"]:
        payload["last_image_url"] = f"/static/{payload['last_image']}"
    return jsonify(payload)


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