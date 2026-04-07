from __future__ import annotations

from pathlib import Path
from typing import List, Tuple
import numpy as np
import cv2

try:
    import tflite_runtime.interpreter as tflite
except ImportError:
    import tensorflow.lite as tflite


class TFLiteModelLoader:
    """Load TFLite model (int8/float32) + labels + inference pipeline"""

    def __init__(self, model_path: str, labels_path: str) -> None:
        # ===== Check file tồn tại =====
        if not Path(model_path).exists():
            raise FileNotFoundError(f"Không tìm thấy model: {model_path}")
        if not Path(labels_path).exists():
            raise FileNotFoundError(f"Không tìm thấy labels: {labels_path}")

        self.model_path = str(Path(model_path))
        self.labels_path = str(Path(labels_path))

        # ===== Load model =====
        self.interpreter = tflite.Interpreter(model_path=self.model_path)
        self.interpreter.allocate_tensors()

        # ===== Tensor info =====
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()

        # Input info
        self.input_shape = self.input_details[0]['shape']  # [1, h, w, c]
        self.input_dtype = self.input_details[0]['dtype']

        # Quantization info
        self.input_scale, self.input_zero_point = self.input_details[0]['quantization']
        self.output_scale, self.output_zero_point = self.output_details[0]['quantization']

        # Load labels
        self.labels = self._load_labels(self.labels_path)

        # Check label vs output
        num_classes = self.output_details[0]['shape'][-1]
        if len(self.labels) != num_classes:
            print(f"⚠ Warning: labels ({len(self.labels)}) != classes ({num_classes})")

        print("✅ Model loaded successfully")
        print(f"Input shape: {self.input_shape}")
        print(f"Input dtype: {self.input_dtype}")
        print(f"Quantization: scale={self.input_scale}, zero_point={self.input_zero_point}")

    # =========================
    # Load label
    # =========================
    @staticmethod
    def _load_labels(labels_path: str) -> List[str]:
        labels: List[str] = []
        with open(labels_path, "r", encoding="utf-8") as f:
            for line in f:
                raw = line.strip()
                if not raw:
                    continue
                parts = raw.split(maxsplit=1)
                labels.append(parts[1] if len(parts) > 1 else parts[0])
        return labels

    # =========================
    # Preprocess image
    # =========================
    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        _, height, width, _ = self.input_shape

    # Resize
        img = cv2.resize(frame, (width, height))

    # BGR -> RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # ===== FIX CHÍNH Ở ĐÂY =====
        if np.issubdtype(self.input_dtype, np.integer):
        # 1. đưa về float
            img = img.astype(np.float32)

        # 2. normalize (rất quan trọng)
            img = img / 255.0

        # 3. quantize theo model
            img = img / self.input_scale + self.input_zero_point

        # 4. clamp đúng range int8
            info = np.iinfo(self.input_dtype)
            img = np.clip(img, info.min, info.max).astype(self.input_dtype)

        else:
        # float32 model
            img = img.astype(np.float32) / 255.0

    # Add batch
        img = np.expand_dims(img, axis=0)

        return img

    # =========================
    # Predict
    # =========================
    def predict(self, frame: np.ndarray) -> Tuple[str, float]:
        input_data = self.preprocess(frame)

        # Set input
        self.interpreter.set_tensor(self.input_details[0]['index'], input_data)

        # Run inference
        self.interpreter.invoke()

        # Get output
        output = self.interpreter.get_tensor(self.output_details[0]['index'])[0]

        # Dequantize nếu cần
        if self.output_scale > 0:
            output = self.output_scale * (output - self.output_zero_point)

        # Lấy class
        class_id = int(np.argmax(output))
        confidence = float(output[class_id])

        label = self.labels[class_id] if class_id < len(self.labels) else str(class_id)

        return label, confidence