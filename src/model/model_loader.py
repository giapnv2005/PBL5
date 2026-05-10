from __future__ import annotations

from pathlib import Path
from typing import List
import numpy as np
import cv2

try:
    import tflite_runtime.interpreter as tflite
except ImportError:
    import tensorflow.lite as tflite


class TFLiteModelLoader:
    """Load a TFLite model, labels, and preprocess input frames."""

    def __init__(self, model_path: str, labels_path: str) -> None:
        if not Path(model_path).exists():
            raise FileNotFoundError(f"Không tìm thấy model: {model_path}")
        if not Path(labels_path).exists():
            raise FileNotFoundError(f"Không tìm thấy labels: {labels_path}")

        self.model_path = str(Path(model_path))
        self.labels_path = str(Path(labels_path))

        self.interpreter = tflite.Interpreter(model_path=self.model_path)
        self.interpreter.allocate_tensors()

        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()

        self.input_shape = self.input_details[0]['shape']  # [1, h, w, c]
        self.input_dtype = self.input_details[0]['dtype']

        self.input_scale, self.input_zero_point = self.input_details[0]['quantization']
        self.output_scale, self.output_zero_point = self.output_details[0]['quantization']

        self.labels = self._load_labels(self.labels_path)

        num_classes = self.output_details[0]['shape'][-1]
        if len(self.labels) != num_classes:
            print(f"⚠ Warning: labels ({len(self.labels)}) != classes ({num_classes})")

        print("✅ Model loaded successfully")
        print(f"Input shape: {self.input_shape}")
        print(f"Input dtype: {self.input_dtype}")
        print(f"Quantization: scale={self.input_scale}, zero_point={self.input_zero_point}")

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

    def preprocess(self, frame: np.ndarray) -> np.ndarray:
        _, height, width, _ = self.input_shape

        img = cv2.resize(frame, (width, height))

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        if np.issubdtype(self.input_dtype, np.integer):
            img = img.astype(np.float32)
            img = img / 255.0
            img = img / self.input_scale + self.input_zero_point
            info = np.iinfo(self.input_dtype)
            img = np.clip(img, info.min, info.max).astype(self.input_dtype)
        else:
            img = img.astype(np.float32) / 255.0

        img = np.expand_dims(img, axis=0)

        return img