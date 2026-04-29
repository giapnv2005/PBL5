from __future__ import annotations

import threading
import time
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import cv2

try:
    from picamera2 import Picamera2  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    # On Raspberry Pi, picamera2 is commonly installed via apt into
    # /usr/lib/python3/dist-packages, which is not visible in a local venv.
    dist_packages = "/usr/lib/python3/dist-packages"
    if dist_packages not in sys.path:
        sys.path.append(dist_packages)
    try:
        from picamera2 import Picamera2  # type: ignore[import-not-found]
    except ImportError:
        Picamera2 = None

from src.queue_manager import ResultQueue
from src.serial_comm import SerialComm
from src.database import DetectionDatabase

try:
    from src.image_processing import ComponentClassifier
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

        self.capture_dir = Path(capture_dir)
        self.capture_dir.mkdir(parents=True, exist_ok=True)

        self._camera_size = (640, 480)
        self._camera_format = "RGB888"
        self.camera = None          # giữ để không break code ngoài trỏ vào thuộc tính này
        self.picam2 = None
        self._camera_backend = "none"
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._state_lock = threading.Lock()
        self._camera_lock = threading.Lock()

        self._init_camera()

        self._counts: Dict[str, int] = {label: 0 for label in labels}
        self._last_result: Dict[str, Any] = {
            "label": "N/A",
            "confidence": 0.0,
            "signal": "0",
            "timestamp": None,
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
        with self._camera_lock:
            if self._camera_backend == "none":
                self._init_camera()
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
        with self._camera_lock:
            self._close_camera()

    # ------------------------------------------------------------------
    # Camera — chỉ dùng Picamera2 (camera CSI chính hãng Raspberry Pi)
    # ------------------------------------------------------------------

    def _init_camera(self) -> None:
        self._close_camera()

        if Picamera2 is None:
            print("[ERROR] Picamera2 không khả dụng — kiểm tra cài đặt libcamera")
            return

        picam2 = None
        try:
            picam2 = Picamera2()
            config = picam2.create_preview_configuration(
                main={"size": self._camera_size, "format": self._camera_format}
            )
            picam2.configure(config)
            picam2.start()

            # Chờ ISP hội tụ Auto Exposure và Auto White Balance
            # Camera Module V2 (IMX219) cần ~2 giây để ổn định
            time.sleep(2.0)

            frame = picam2.capture_array()
            if frame is not None:
                self.picam2 = picam2
                self._camera_backend = "picamera2"
                print("[OK] Camera ready với Picamera2 (ISP đã hội tụ)")
                return

            print("[ERROR] Picamera2 khởi động xong nhưng không capture được frame")

        except Exception as exc:
            print(f"[ERROR] Picamera2 init thất bại: {exc}")

        finally:
            # Nếu init thất bại thì dọn dẹp instance tạm
            if picam2 is not None and self.picam2 is None:
                try:
                    picam2.stop()
                except Exception:
                    pass
                try:
                    picam2.close()
                except Exception:
                    pass

    def _close_camera(self) -> None:
        if self.picam2 is not None:
            try:
                self.picam2.stop()
            except Exception:
                pass
            try:
                self.picam2.close()
            except Exception:
                pass
        self.picam2 = None
        self.camera = None
        self._camera_backend = "none"
        time.sleep(0.1)

    # ------------------------------------------------------------------
    # Frame capture
    # ------------------------------------------------------------------

    def _read_frame(self):
        with self._camera_lock:
            if self._camera_backend == "none":
                self._init_camera()

            if self._camera_backend == "picamera2" and self.picam2 is not None:
                try:
                    frame_rgb = self.picam2.capture_array()
                    if frame_rgb is not None:
                        # Picamera2 trả về RGB, chuyển sang BGR cho OpenCV/classifier
                        return cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                except Exception as exc:
                    print(f"[WARNING] Picamera2 capture thất bại: {exc}")
                    self._close_camera()

            return None

    # ------------------------------------------------------------------
    # Serial loop
    # ------------------------------------------------------------------

    def _serial_loop(self) -> None:
        while self._running:
            message = self.serial.read_message(timeout=0.1)
            if not message:
                time.sleep(0.01)
                continue

            if message == "DETECTED":
                payload = self.process_detected()
                signal = "0"
                if payload is not None:
                    signal = str(payload.get("last_result", {}).get("signal", "0"))
                # Compatibility: một số Arduino sketch gửi tín hiệu ngay sau DETECTED
                self.serial.send_signal(signal)

            elif message in {"READY", "REQUEST", "IR2", "IR3"}:
                self.process_ready_request()

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
                }
                self._last_image_rel = f"captures/{filename}"
            return self.get_result_payload()

        label, confidence = self.classifier.predict(frame)
        signal = self._label_to_signal.get(label, "0")
        self.queue.enqueue(signal)

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
            }
            self._last_image_rel = f"captures/{filename}"

        return self.get_result_payload()

    def process_ready_request(self) -> str:
        signal = self.queue.dequeue(default="0") or "0"
        self.serial.send_signal(signal)
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
