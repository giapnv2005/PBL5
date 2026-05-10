from __future__ import annotations

from typing import Tuple, Dict
import numpy as np

from src.model.model_loader import TFLiteModelLoader


class ComponentClassifier:
    """Run classification using TFLiteModelLoader (optimized version)"""

    def __init__(self, model_path: str, label_path: str) -> None:
        self.loader = TFLiteModelLoader(
            model_path=model_path,
            labels_path=label_path
        )

        self.interpreter = self.loader.interpreter
        self.input_details = self.loader.input_details
        self.output_details = self.loader.output_details
        self.labels = self.loader.labels

    @staticmethod
    def _to_probabilities(scores: np.ndarray) -> np.ndarray:
        if np.all(scores >= 0) and np.all(scores <= 1):
            return scores

        shifted = scores - np.max(scores)
        exp_scores = np.exp(shifted)
        return exp_scores / np.sum(exp_scores)

    def predict(self, frame: np.ndarray, confidence_threshold: float = 0.7) -> Tuple[str, float, dict]:
        """
        Predict class and return label, confidence, and probability distribution.
        If confidence < threshold, return 'unknown'.
        
        Args:
            frame: Input frame (BGR image)
            confidence_threshold: Minimum confidence to accept prediction (default 0.7)
            
        Returns:
            tuple: (label, confidence, probabilities_dict)
        """
        input_data = self.loader.preprocess(frame)

        self.interpreter.set_tensor(self.input_details[0]["index"], input_data)
        self.interpreter.invoke()

        raw_output = self.interpreter.get_tensor(
            self.output_details[0]["index"]
        )[0]

        if self.loader.output_scale > 0:
            raw_output = self.loader.output_scale * (
                raw_output.astype(np.float32) - self.loader.output_zero_point
            )
        else:
            raw_output = raw_output.astype(np.float32)

        probs = self._to_probabilities(raw_output)

        class_index = int(np.argmax(probs))
        confidence = float(probs[class_index])
        
        # Build probability distribution dictionary
        probs_dict = {}
        for idx, prob in enumerate(probs):
            class_name = self.labels[idx] if idx < len(self.labels) else f"class_{idx}"
            probs_dict[class_name] = float(prob)

        # Check confidence threshold
        if confidence < confidence_threshold:
            label = "unknown"
        else:
            if not self.labels:
                label = str(class_index)
            elif class_index < len(self.labels):
                label = self.labels[class_index]
            else:
                label = f"class_{class_index}"

        return label, confidence, probs_dict