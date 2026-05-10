from __future__ import annotations

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import cv2

from src.queue import ResultQueue
from src.communication import SerialComm, ArduinoProtocol
from src.storage import DetectionDatabase
from src.camera import CameraManager

try:
    from src.model import ComponentClassifier
except Exception as exc:  # pragma: no cover
    ComponentClassifier = None
    print(f"[WARNING] AI classifier import failed: {exc}")


class SystemController:
    """Main orchestrator: camera -> AI -> queue -> Arduino + web state."""

    def __init__(
        self,
        model_path: str,
        labels_path: str,
        capture_dir: str,
        database_path: str,
        serial_port: str = "/dev/ttyUSB0",
        baudrate: int = 9600,
        camera_index: int = 0,
    ) -> None:
        self.classifier = None
        if ComponentClassifier is not None:
            try:
                self.classifier = ComponentClassifier(model_path=model_path, label_path=labels_path)
            except Exception as exc:
                print(f"[WARNING] AI classifier init failed: {exc}")
        else:
            print("[WARNING] AI classifier unavailable; system will run camera/serial only")

        label_entries = self._load_label_entries(labels_path)
        signal_by_label = {label: signal for signal, label in label_entries}
        labels = [label for _, label in label_entries]
        if self.classifier is not None and getattr(self.classifier, "labels", None):
            labels = list(self.classifier.labels)
        self._labels = list(labels)
        self._signal_by_label = dict(signal_by_label)

        self.queue = ResultQueue()
        self.serial = SerialComm(port=serial_port, baudrate=baudrate)
        self.database = DetectionDatabase(database_path)
        self.camera_manager = CameraManager(camera_width=640, camera_height=480)
        self.protocol = ArduinoProtocol(serial_send_callback=self.serial.send_signal)

        self.capture_dir = Path(capture_dir)
        self.capture_dir.mkdir(parents=True, exist_ok=True)

        # Legacy attributes for compatibility
        self.camera = None
        self.picam2 = None

        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._state_lock = threading.Lock()

        self._counts: Dict[str, int] = {label: 0 for label in labels}
        self._last_result: Dict[str, Any] = {
            "label": "N/A",
            "confidence": 0.0,
            "signal": "0",
            "timestamp": None,
            "probabilities": {},
        }
        self._last_image_rel = ""
        self._label_to_signal = {
            label: self._signal_by_label.get(label, str(index))
            for index, label in enumerate(labels)
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_label_entries(labels_path: str) -> list[tuple[str, str]]:
        parsed: list[tuple[str, str]] = []
        try:
            with open(labels_path, "r", encoding="utf-8") as handle:
                for line in handle:
                    raw = line.strip()
                    if not raw:
                        continue
                    parts = raw.split(maxsplit=1)
                    signal = parts[0]
                    label = parts[1] if len(parts) > 1 else parts[0]
                    parsed.append((signal, label))
        except OSError:
            pass
        return parsed

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self.camera_manager.initialize()
        self._running = True
        self.serial.connect()
        self._thread = threading.Thread(target=self._serial_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        self.serial.close()
        self.camera_manager.close()

    def _read_frame(self):
        """Read frame from camera manager."""
        return self.camera_manager.read_frame()

    # ------------------------------------------------------------------
    # Serial loop
    # ------------------------------------------------------------------

    def _serial_loop(self) -> None:
        while self._running:
            message = self.serial.read_message(timeout=0.1)
            if not message:
                time.sleep(0.01)
                continue

            if self.protocol.is_detect_message(message):
                payload = self.process_detected()
                self.protocol.handle_detect_message(payload)

            elif self.protocol.is_ready_message(message):
                self.protocol.handle_ready_message(self.process_ready_request)

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def get_preview_stream_frame(self) -> Optional[bytes]:
        frame = self._read_frame()
        if frame is None:
            return None
        try:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            ok, encoded = cv2.imencode(".png", frame_rgb)
            if not ok:
                return None
            return encoded.tobytes()
        except Exception as e:
            print(f"[ERROR] Exception during PNG encoding: {e}")
            return None

    def process_detected(self) -> Optional[Dict[str, Any]]:
        frame = self._read_frame()
        if frame is None:
            return None

        if self.classifier is None:
            timestamp = datetime.now()
            filename = f"capture_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
            file_path = self.capture_dir / filename
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            cv2.imwrite(str(file_path), frame_rgb)
            timestamp_text = timestamp.isoformat(timespec="seconds")
            self.database.add_detection(
                accessory="AI_UNAVAILABLE",
                confident=0.0,
                timestamp=timestamp_text,
                image_path=str(file_path),
            )
            with self._state_lock:
                self._last_result = {
                    "label": "AI_UNAVAILABLE",
                    "confidence": 0.0,
                    "signal": "0",
                    "timestamp": timestamp_text,
                    "probabilities": {},
                }
                self._last_image_rel = f"captures/{filename}"
            return self.get_result_payload()

        label, confidence, probs_dict = self.classifier.predict(frame)
        signal = self._label_to_signal.get(label, "0")
        
        # Only enqueue if not unknown
        if label != "unknown":
            self.queue.enqueue(signal)
        else:
            signal = ""

        timestamp = datetime.now()
        filename = f"capture_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        file_path = self.capture_dir / filename
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        cv2.imwrite(str(file_path), frame_rgb)
        timestamp_text = timestamp.isoformat(timespec="seconds")
        confidence_value = round(float(confidence), 4)
        self.database.add_detection(
            accessory=label,
            confident=confidence_value,
            timestamp=timestamp_text,
            image_path=str(file_path),
        )

        with self._state_lock:
            self._counts[label] = self._counts.get(label, 0) + 1
            self._last_result = {
                "label": label,
                "confidence": confidence_value,
                "signal": signal,
                "timestamp": timestamp_text,
                "probabilities": probs_dict,  # Thêm probability distribution
            }
            self._last_image_rel = f"captures/{filename}"

        return self.get_result_payload()

    def process_ready_request(self) -> str:
        """Dequeue next signal from queue."""
        signal = self.queue.dequeue(default=None)
        if not signal:
            return ""
        with self._state_lock:
            self._last_result["signal"] = signal
        return signal

    def get_result_payload(self) -> Dict[str, Any]:
        with self._state_lock:
            return {
                "labels": list(self._labels),
                "counts": dict(self._counts),
                "last_result": dict(self._last_result),
                "last_image": self._last_image_rel,
                "queue_size": self.queue.size(),
                "running": self._running,
                "serial_connected": self.serial.is_connected,
            }
