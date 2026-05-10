#include <Servo.h>

const int IR_1_PI_SNAP  = 2;  

Servo servo1; // Gạt Capacitor (Loại 0)
Servo servo2; // Gạt IC (Loại 1)
Servo servo3; // Gạt Transistor (Loại 2)

// Cấu hình góc Servo
const int SERVO_HOME = 0;   
const int SERVO_KICK = 130;    
const int KICK_HOLD_TIME = 2500; 

void setup() {
  Serial.begin(9600);
  
  pinMode(IR_1_PI_SNAP, INPUT);

  servo1.attach(8);
  servo2.attach(9);
  servo3.attach(10);

  servo1.write(SERVO_HOME);
  servo2.write(SERVO_HOME);
  servo3.write(SERVO_HOME);
  
  Serial.println("SYSTEM_READY");
}

void loop() {
  // 1. Xử lý cảm biến 1: Báo Pi chụp ảnh
  if (digitalRead(IR_1_PI_SNAP) == LOW) {
    Serial.println("DETECTED");
    while(digitalRead(IR_1_PI_SNAP) == LOW); 
  }

  // 2. Đọc kết quả phân loại từ Raspberry Pi
  if (Serial.available() > 0) {
    String msg = Serial.readStringUntil('\n');
    msg.trim();

    if (msg == "0") {
      executeKick(servo1, 4000);
    } 
    else if (msg == "1") {
      executeKick(servo2, 5000);
    }
    else if (msg == "2") {
      executeKick(servo3, 6000);
    }
  }
}

void executeKick(Servo &s, int waitTime) {
  delay(waitTime);           // Đợi vật thể di chuyển đến vị trí gạt
  s.write(SERVO_KICK);       // Thực hiện gạt
  delay(KICK_HOLD_TIME);     // Giữ cánh tay gạt trong 2 giây
  s.write(SERVO_HOME);       // Quay về vị trí nghỉ
}