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
        labels = [label for _, label in label_entries]
        signals = [signal for signal, _ in label_entries]
        if self.classifier is not None and getattr(self.classifier, "labels", None):
            labels = self.classifier.labels

        self.queue = ResultQueue()
        self.serial = SerialComm(port=serial_port, baudrate=baudrate)

        self.capture_dir = Path(capture_dir)
        self.capture_dir.mkdir(parents=True, exist_ok=True)

        self._camera_index = camera_index
        self._camera_size = (640, 480)
        self._camera_format = "RGB888"
        self.camera = None
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
            label: signals[index] if index < len(signals) else str(index)
            for index, label in enumerate(labels)
        }



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



    def _init_camera(self) -> None:

        self._close_camera()



        # Try V4L2 first (better compatibility on Raspberry Pi USB cams)

        camera = cv2.VideoCapture(self._camera_index, cv2.CAP_V4L2)

        if not camera.isOpened():

            camera = cv2.VideoCapture(self._camera_index)



        if camera.isOpened():

            camera.set(cv2.CAP_PROP_FRAME_WIDTH, self._camera_size[0])

            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self._camera_size[1])

            camera.set(cv2.CAP_PROP_FPS, 15)

            camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)



            ok = False

            for _ in range(12):

                ret, frame = camera.read()

                if ret and frame is not None:

                    ok = True

                    break

                time.sleep(0.05)



            if ok:

                self.camera = camera

                self._camera_backend = "opencv"

                print(f"[OK] Camera ready with OpenCV backend (index={self._camera_index})")

                return



            camera.release()



        if Picamera2 is not None:

            picam2 = None

            try:

                picam2 = Picamera2()

                config = picam2.create_preview_configuration(

                    main={"size": self._camera_size, "format": self._camera_format}

                )

                picam2.configure(config)

                picam2.start()

                time.sleep(0.2)

                frame = picam2.capture_array()

                if frame is not None:

                    self.picam2 = picam2

                    self._camera_backend = "picamera2"

                    print("[OK] Camera ready with Picamera2 backend")

                    return

            except Exception as exc:

                print(f"[WARNING] Picamera2 init failed: {exc}")

            finally:

                if picam2 is not None and self.picam2 is None:

                    try:

                        picam2.stop()

                    except Exception:

                        pass

                    try:

                        picam2.close()

                    except Exception:

                        pass



        print("[ERROR] No working camera backend found")



    def _close_camera(self) -> None:

        if self.camera is not None:

            try:

                self.camera.release()

            except Exception:

                pass

        self.camera = None



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

        self._camera_backend = "none"

        time.sleep(0.1)



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
                # Compatibility path: some Arduino sketches expect result
                # immediately after DETECTED without sending REQUEST/READY.
                self.serial.send_signal(signal)

            elif message in {"READY", "REQUEST", "IR2", "IR3"}:

                self.process_ready_request()



    def _read_frame(self):

        with self._camera_lock:

            if self._camera_backend == "none":

                self._init_camera()



            if self._camera_backend == "opencv" and self.camera is not None:

                ok, frame = self.camera.read()

                if ok and frame is not None:

                    return frame



                # Reinitialize once when OpenCV camera drops frames repeatedly.

                self._init_camera()

                if self._camera_backend == "opencv" and self.camera is not None:

                    ok, frame = self.camera.read()

                    if ok and frame is not None:

                        return frame



            if self._camera_backend == "picamera2" and self.picam2 is not None:

                try:

                    frame_rgb = self.picam2.capture_array()

                    if frame_rgb is not None:

                        return cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

                except Exception as exc:

                    print(f"[WARNING] Picamera2 capture failed: {exc}")



            return None



    def get_preview_jpeg(self) -> Optional[bytes]:
        frame = self._read_frame()
        if frame is None:
            return None
        try:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            ok, encoded = cv2.imencode(".jpg", frame_rgb)
            if not ok:
                return None
            return encoded.tobytes()
        except Exception as e:
            print(f"[ERROR] Exception during JPEG encoding: {e}")
            return None



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

            with self._state_lock:

                self._last_result = {

                    "label": "AI_UNAVAILABLE",

                    "confidence": 0.0,

                    "signal": "0",

                    "timestamp": timestamp.isoformat(timespec="seconds"),

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



        with self._state_lock:

            self._counts[label] = self._counts.get(label, 0) + 1

            self._last_result = {

                "label": label,

                "confidence": round(float(confidence), 4),

                "signal": signal,

                "timestamp": timestamp.isoformat(timespec="seconds"),

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

                "counts": dict(self._counts),

                "last_result": dict(self._last_result),

                "last_image": self._last_image_rel,

                "queue_size": self.queue.size(),

                "running": self._running,

                "serial_connected": self.serial.is_connected,

            }