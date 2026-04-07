Tổng quan kiến trúc
src/ → xử lý logic hệ thống (AI + Arduino)
Web/ → giao diện + Flask
Models/ → model AI
run.py → chạy toàn hệ thống

🧠 1. Models/
📄 my_model.tflite

👉 Chức năng:

Model AI đã convert (TensorFlow Lite)
Dùng để phân loại linh kiện

👉 Được load trong:

model_loader.py
📄 labels.txt

👉 Chức năng:

Mapping index → tên linh kiện

⚙️ 2. src/ (PHẦN QUAN TRỌNG NHẤT)
📄 model_loader.py

👉 Chức năng:

Load model .tflite 1 lần duy nhất
Chuẩn bị interpreter

👉 Nhiệm vụ:

Load model
Allocate tensor
Lấy input/output details

📄 image_processing.py

👉 Chức năng:

Xử lý ảnh từ camera
Resize, normalize
Gọi model để predict

👉 Nhiệm vụ:

Nhận frame từ camera
Tiền xử lý ảnh
Trả về:
label
confidence

👉 Output:

return label, confidence
📄 serial_comm.py

👉 Chức năng:

Giao tiếp giữa Pi ↔ Arduino (qua USB)

👉 Nhiệm vụ:

Mở cổng serial (/dev/ttyUSB0)
Gửi tín hiệu:
'1', '2', '3'
Nhận tín hiệu:
"DETECTED"
"READY"

📄 queue_manager.py

👉 Chức năng:
🔥 Cực kỳ quan trọng

Quản lý hàng đợi kết quả phân loại

👉 Vì:

Vật di chuyển → cần đồng bộ thời gian

👉 Nhiệm vụ:

Thêm kết quả:
enqueue(result)
Lấy kết quả:
dequeue()

👉 Dữ liệu:

Queue = [1, 2, 3]
📄 controller.py

👉 Chức năng:
🔥 TRUNG TÂM HỆ THỐNG

👉 Đây là file quan trọng nhất

Nhiệm vụ của controller.py
1. Nhận tín hiệu từ Arduino
"DETECTED" từ IR1
2. Khi detect:
Chụp ảnh
Gọi AI (image_processing)
Lưu kết quả vào queue
3. Khi Arduino yêu cầu (IR2, IR3)
Lấy kết quả từ queue
Gửi lại Arduino
4. Cập nhật dữ liệu cho Web
Ảnh vừa chụp
Kết quả phân loại

🌐 3. Web/
📄 app.py

👉 Chức năng:

Server Flask

👉 Nhiệm vụ:

Route web:
/ → trang chính
/video_feed → stream camera
/result → trả kết quả AI
📁 templates/index.html

👉 Chức năng:

Giao diện web

👉 Hiển thị:

Camera stream
Ảnh vừa chụp
Tên linh kiện
Nút start/stop
📁 static/script.js

👉 Chức năng:

Gọi API Flask (AJAX)

👉 Nhiệm vụ:

Fetch kết quả AI liên tục
Update UI
📁 static/style.css

👉 Chức năng:

CSS giao diện
📁 static/captures/

👉 Chức năng:

Lưu ảnh đã chụp
🚀 4. File ngoài
📄 requirements.txt

👉 Chức năng:

Danh sách thư viện cần cài

📄 run.py

👉 Chức năng:
🔥 Điểm chạy chính của toàn hệ thống

