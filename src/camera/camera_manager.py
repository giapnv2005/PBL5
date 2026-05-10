"""Camera Manager - Camera initialization and frame capture operations."""

from __future__ import annotations

import sys
import time
from typing import Optional

import cv2

try:
    from picamera2 import Picamera2  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    dist_packages = "/usr/lib/python3/dist-packages"
    if dist_packages not in sys.path:
        sys.path.append(dist_packages)
    try:
        from picamera2 import Picamera2  # type: ignore[import-not-found]
    except ImportError:
        Picamera2 = None


class CameraManager:
    """Manages Raspberry Pi camera operations."""

    def __init__(self, camera_width: int = 640, camera_height: int = 480) -> None:
        """
        Initialize camera manager.

        Args:
            camera_width: Camera frame width
            camera_height: Camera frame height
        """
        self.picam2: Optional[object] = None
        self._camera_size = (camera_width, camera_height)
        self._camera_format = "RGB888"
        self._camera_backend = "none"

    def initialize(self) -> bool:
        """
        Initialize Picamera2 (Raspberry Pi CSI camera).

        Returns:
            True if camera initialized successfully, False otherwise
        """
        self.close()

        if Picamera2 is None:
            print("[ERROR] Picamera2 không khả dụng — kiểm tra cài đặt libcamera")
            return False

        picam2 = None
        try:
            picam2 = Picamera2()
            config = picam2.create_preview_configuration(
                main={"size": self._camera_size, "format": self._camera_format}
            )
            picam2.configure(config)
            picam2.start()

            # Chờ ISP hội tụ Auto Exposure và Auto White Balance
            time.sleep(2.0)

            frame = picam2.capture_array()
            if frame is not None:
                self.picam2 = picam2
                self._camera_backend = "picamera2"
                print("[OK] Camera ready với Picamera2 (ISP đã hội tụ)")
                return True

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

        return False

    def read_frame(self) -> Optional[bytes]:
        """
        Read frame from camera.

        Returns:
            Frame as numpy array (BGR), or None if failed
        """
        if self._camera_backend == "none":
            if not self.initialize():
                return None

        if self._camera_backend == "picamera2" and self.picam2 is not None:
            try:
                frame_rgb = self.picam2.capture_array()
                if frame_rgb is not None:
                    # Picamera2 trả về RGB, chuyển sang BGR cho OpenCV
                    return cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
            except Exception as exc:
                print(f"[WARNING] Picamera2 capture thất bại: {exc}")
                self.close()

        return None

    def close(self) -> None:
        """Close camera connection."""
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

    @property
    def is_ready(self) -> bool:
        """Check if camera is ready."""
        return self._camera_backend == "picamera2" and self.picam2 is not None
