import sys
import numpy as np
import cv2
import base64
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from camera import WebcamThread


class AttendanceWidget(QWidget):
    def __init__(self, controller_window=None, db=None, face_recognizer=None):
        super().__init__()
        self.controller_window = controller_window
        self.face_recog = face_recognizer
        self.db = db
        self.webcam_thread = None

        self.setWindowTitle("🏢 Hệ thống chấm công")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        self.setup_styles()
        self.setup_ui()
        self.setup_connections()
        self.log_message("🚀 Hệ thống đã sẵn sàng", "info")

    def setup_styles(self):
        try:
            with open("assets/style.qss", "r", encoding="utf-8") as file:
                self.setStyleSheet(file.read())
        except Exception as e:
            print("Không thể load style.qss:", e)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header
        header = QLabel("🏢 HỆ THỐNG CHẤM CÔNG")
        header.setObjectName("header")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        # Back button
        self.btn_back = QPushButton("← Quay lại")
        self.btn_back.setFixedSize(100, 30)
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.setStyleSheet(""" 
            QPushButton { background: #f5f5f5; color: black; border: none; border-radius: 4px; 
                         font-weight: 950; font-size: 14px; padding: 0px; } 
            QPushButton:hover { background: #e0e0e0; } 
        """)

        # Main content
        content = QHBoxLayout()
        content.setSpacing(10)
        content.addWidget(self.create_left_panel(), 3)
        content.addWidget(self.create_right_panel(), 1)

        layout.addWidget(self.btn_back)
        layout.addLayout(content)

    def create_left_panel(self):
        panel = QFrame()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        # Controls
        control_card = QFrame()
        control_card.setProperty("class", "card")
        control_layout = QHBoxLayout(control_card)

        control_layout.addWidget(QLabel("Loại:"))

        self.check_type_combo = QComboBox()
        self.check_type_combo.addItems(["📥 Check In", "📤 Check Out"])
        control_layout.addWidget(self.check_type_combo)

        self.start_button = QPushButton("▶️ Bắt đầu")
        self.start_button.setCheckable(True)
        control_layout.addWidget(self.start_button)

        layout.addWidget(control_card)

        # Video
        video_card = QFrame()
        video_card.setProperty("class", "card")
        video_layout = QVBoxLayout(video_card)
        video_layout.addWidget(QLabel("📹 Camera:"))

        self.image_label = QLabel()
        self.image_label.setObjectName("video_display")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(640, 480)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setText("📷\nCamera chưa khởi động\n\nNhấn 'Bắt đầu' để kích hoạt")

        video_layout.addWidget(self.image_label)
        layout.addWidget(video_card, 2)

        # Logs
        log_card = QFrame()
        log_card.setProperty("class", "card")
        log_layout = QVBoxLayout(log_card)
        log_layout.addWidget(QLabel("📋 Nhật ký:"))

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(150)
        log_layout.addWidget(self.log_box)

        layout.addWidget(log_card, 0)
        return panel

    def create_right_panel(self):
        panel = QFrame()
        panel.setMinimumWidth(300)
        panel.setMaximumWidth(350)
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        # Employee info
        info_card = QFrame()
        info_card.setProperty("class", "card")
        info_layout = QVBoxLayout(info_card)
        info_layout.addWidget(QLabel("👤 Thông tin nhân viên:"))

        # Photo
        self.info_face = QLabel()
        self.info_face.setObjectName("employee_photo")
        self.info_face.setFixedSize(200, 150)
        self.info_face.setAlignment(Qt.AlignCenter)
        self.info_face.setText("📷\nChưa có ảnh")
        info_layout.addWidget(self.info_face, 0, Qt.AlignCenter)

        # Info labels
        self.info_name = QLabel("👤 Họ tên: ---")
        self.info_id = QLabel("🆔 Mã NV: ---")
        self.info_dept = QLabel("🏢 Phòng ban: ---")
        self.info_time = QLabel("⏰ Thời gian: ---")

        for label in [self.info_name, self.info_id, self.info_dept, self.info_time]:
            label.setProperty("class", "info")
            info_layout.addWidget(label)

        # Status
        self.status_label = QLabel("⚪ Trạng thái: Chờ")
        self.status_label.setProperty("class", "status")
        self.status_label.setStyleSheet("background: #6b7280; color: white;")
        info_layout.addWidget(self.status_label)

        layout.addWidget(info_card, 1)

        # Stats
        stats_card = QFrame()
        stats_card.setProperty("class", "card")
        stats_layout = QVBoxLayout(stats_card)
        stats_layout.addWidget(QLabel("📊 Thống kê hôm nay:"))

        self.stats_checkin = QLabel("📥 Check In: 0")
        self.stats_checkout = QLabel("📤 Check Out: 0")
        stats_layout.addWidget(self.stats_checkin)
        stats_layout.addWidget(self.stats_checkout)

        layout.addWidget(stats_card)
        return panel

    def setup_connections(self):
        self.start_button.toggled.connect(self.toggle_webcam)
        self.btn_back.clicked.connect(self.go_back)

    def toggle_webcam(self, checked):
        if checked:
            check_type = self.check_type_combo.currentText().replace("📥 ", "").replace("📤 ", "")
            self.log_message(f"▶️ Bắt đầu chấm công - {check_type}", "info")
            self.update_status("🟢 Đang hoạt động", "success")
            self.check_type = check_type

            self.webcam_thread = WebcamThread(self.face_recog, self.db, self.check_type)
            self.webcam_thread.frame_processed.connect(self.show_image)
            self.webcam_thread.attendance_logged.connect(self.handle_attendance_logged)
            self.webcam_thread.start()

            self.start_mock_camera()
            self.start_button.setText("⏹️ Dừng")
        else:
            self.log_message("⏹️ Dừng chấm công", "warning")
            self.update_status("🟡 Đã dừng", "warning")
            self.start_button.setText("▶️ Bắt đầu")
            self.image_label.setText("📷\nCamera đã tắt")

            if hasattr(self, 'webcam_thread') and self.webcam_thread.isRunning():
                self.webcam_thread.stop()

    def start_mock_camera(self):
        self.image_label.setText("📹\nCamera đang hoạt động...\n\n✨ Đưa mặt vào để chấm công")
        self.image_label.setStyleSheet(self.image_label.styleSheet() + "background: #e8f5e8;")

    def show_image(self, frame):
        if frame is None:
            return

        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)

        pixmap = QPixmap.fromImage(qt_image)
        scaled_pixmap = pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled_pixmap)

    def reset_employee_info(self):
        """Reset thông tin nhân viên về trạng thái mặc định"""
        info_labels = [
            (self.info_name, "👤 Họ tên: ---"),
            (self.info_id, "🆔 Mã NV: ---"),
            (self.info_dept, "🏢 Phòng ban: ---"),
            (self.info_time, "⏰ Thời gian: ---")
        ]

        for label, text in info_labels:
            label.setText(text)

        self.info_face.clear()
        self.info_face.setText("📷\nChưa có ảnh")
        self.update_status("⚪ Trạng thái: Chờ", "info")

    def handle_attendance_logged(self, msg, emp_info=None, face_img=None):
        self.log_message(msg, "success" if emp_info else "warning")

        if emp_info:
            emp_dict = {
                'EmployeeID': emp_info[0],
                'FullName': emp_info[1],
                'Department': emp_info[2] if len(emp_info) > 2 else '---',
                'Gender': emp_info[3] if len(emp_info) > 3 else '---',
                'Position': emp_info[4] if len(emp_info) > 4 else '---',
                'Face_img': emp_info[8] if len(emp_info) > 8 else None,
            }
            self.update_employee_info(emp_dict)
            self.update_status("✅ Chấm công thành công", "success")
        else:
            self.reset_employee_info()

    def update_employee_info(self, emp_info):
        self.info_name.setText(f"👤 Họ tên: {emp_info.get('FullName', '---')}")
        self.info_id.setText(f"🆔 Mã Nhân Viên: {emp_info.get('EmployeeID', '---')}")
        self.info_dept.setText(f"🏢 Phòng ban: {emp_info.get('Department', '---')}")

        now = QDateTime.currentDateTime().toString("HH:mm:ss dd/MM/yyyy")
        self.info_time.setText(f"⏰ Thời gian: {now}")

        # Xử lý hiển thị ảnh
        face_img_data = emp_info.get('Face_img')
        if face_img_data:
            self.display_face_image(face_img_data)
        else:
            self.info_face.setText("📷\nKhông có ảnh")

    def display_face_image(self, face_img_data):
        """Xử lý và hiển thị ảnh khuôn mặt"""
        try:
            face_img_bytes = self.convert_to_bytes(face_img_data)
            if not face_img_bytes:
                self.info_face.setText("📷\nLỗi chuyển đổi dữ liệu")
                return

            # Decode binary data thành OpenCV image
            nparr = np.frombuffer(face_img_bytes, np.uint8)
            face_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if face_img is not None and face_img.size > 0:
                # Resize nếu cần
                min_size = 80
                if face_img.shape[0] < min_size or face_img.shape[1] < min_size:
                    scale_factor = max(min_size / face_img.shape[0], min_size / face_img.shape[1])
                    new_width = int(face_img.shape[1] * scale_factor)
                    new_height = int(face_img.shape[0] * scale_factor)
                    face_img = cv2.resize(face_img, (new_width, new_height), interpolation=cv2.INTER_CUBIC)

                # Chuyển BGR sang RGB và hiển thị
                face_rgb = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
                h, w, ch = face_rgb.shape
                qt_face = QImage(face_rgb.data, w, h, ch * w, QImage.Format_RGB888)

                scaled_face = QPixmap.fromImage(qt_face).scaled(
                    self.info_face.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.info_face.setPixmap(scaled_face)
            else:
                self.info_face.setText("📷\nLỗi decode ảnh")

        except Exception as e:
            print(f"Error displaying face image: {e}")
            self.info_face.setText("📷\nLỗi hiển thị ảnh")

    def convert_to_bytes(self, face_img_data):
        """Chuyển đổi dữ liệu ảnh sang bytes"""
        if isinstance(face_img_data, (bytes, bytearray)):
            return bytes(face_img_data)

        if isinstance(face_img_data, str):
            # Thử hex string
            if face_img_data.startswith('0x') or all(
                    c in '0123456789ABCDEFabcdef' for c in face_img_data.replace('0x', '')[:20]):
                try:
                    hex_data = face_img_data.replace('0x', '')
                    if len(hex_data) % 2 != 0:
                        hex_data = '0' + hex_data
                    return bytes.fromhex(hex_data)
                except ValueError:
                    pass

            # Thử base64
            if len(face_img_data) > 20:
                try:
                    return base64.b64decode(face_img_data)
                except Exception:
                    try:
                        return face_img_data.encode('latin-1')
                    except:
                        pass
        return None

    def update_status(self, text, status_type):
        self.status_label.setText(text)
        colors = {"success": "#059669", "warning": "#d97706", "danger": "#dc2626"}
        color = colors.get(status_type, "#6b7280")
        self.status_label.setStyleSheet(
            f"background: {color}; color: white; padding: 8px; border-radius: 6px; font-weight: bold;")

    def log_message(self, message, msg_type="info"):
        timestamp = QDateTime.currentDateTime().toString("HH:mm:ss")
        icons = {"success": "✅", "warning": "⚠️", "error": "❌", "info": "ℹ️"}
        colors = {"success": "#059669", "warning": "#d97706", "error": "#dc2626", "info": "#2563eb"}

        icon = icons.get(msg_type, "ℹ️")
        color = colors.get(msg_type, "#2563eb")

        formatted_msg = f'<span style="color: {color}; font-weight: bold;">[{timestamp}] {icon}</span> {message}'
        self.log_box.append(formatted_msg)

        cursor = self.log_box.textCursor()
        cursor.movePosition(cursor.End)
        self.log_box.setTextCursor(cursor)

    def go_back(self):
        """Xử lý khi nhấn nút back"""
        try:
            # Dừng webcam nếu đang chạy
            if hasattr(self, 'webcam_thread') and self.webcam_thread and self.webcam_thread.isRunning():
                self.webcam_thread.stop()
                self.webcam_thread.wait()

            # Hiển thị lại màn hình chính
            if self.controller_window:
                self.controller_window.show_main_window()

            self.hide()
        except Exception as e:
            print(f"Error in go_back: {e}")
            self.close()