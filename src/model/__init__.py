"""AI Model Layer - Model loading and inference."""

try:
    from src.model.model_loader import TFLiteModelLoader
    from src.model.classifier import ComponentClassifier
    __all__ = ["TFLiteModelLoader", "ComponentClassifier"]
except ImportError as e:
    # TensorFlow/tflite-runtime not installed
    import warnings
    warnings.warn(f"AI model layer unavailable: {e}", RuntimeWarning)
    TFLiteModelLoader = None
    ComponentClassifier = None
    __all__ = []
