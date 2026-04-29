# test_classifier.py
import cv2
import numpy as np
from src.model_loader import TFLiteModelLoader
from src.image_processing import ComponentClassifier

# 1. Load model và in thông tin quantization
loader = TFLiteModelLoader(
    model_path="./Models/my_model.tflite",  # sửa đường dẫn
    labels_path="./Models/labels.txt"
)

print(f"input_scale={loader.input_scale}, input_zero_point={loader.input_zero_point}")
print(f"output_scale={loader.output_scale}, output_zero_point={loader.output_zero_point}")
print(f"labels={loader.labels}")

# 2. Test với ảnh thật (chụp sẵn hoặc dùng ảnh capture có sẵn)
classifier = ComponentClassifier(
    model_path="./Models/my_model.tflite",
    label_path="./Models/labels.txt"
)

# Dùng ảnh capture sẵn trong thư mục captures/
import glob
images = glob.glob("captures/*.jpg")[:5]  # lấy 5 ảnh đầu

for img_path in images:
    img_bgr = cv2.imread(img_path)
    label, confidence = classifier.predict(img_bgr)
    print(f"{img_path} → {label} ({confidence:.2%})")
    
import glob
images = glob.glob("/home/pi/a/PBL5/Web/static/captures/capture_20260421_222357_628082.jpg")[:5]

for img_path in images:
    img_bgr = cv2.imread(img_path)
    label, confidence = classifier.predict(img_bgr)
    print(f"{img_path} → {label} ({confidence:.2%})")