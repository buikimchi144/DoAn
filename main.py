import sys
import numpy as np
import hashlib
import openpyxl
import os
from db.database import Database
from ui_components import CustomTableWidget, Sidebar
from face_recognition_util import FaceRecognitionUtil
import time
from camera import WebcamThread
from camera import Camera
import base64
import cv2
from PyQt5.QtWidgets import *

# Import necessary modules and widgets
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QDesktopWidget, QComboBox,
                             QLineEdit, QMessageBox)
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtCore import Qt

# Import other application windows/widgets that the controller manages
from employee_attendance import EmployeeAttendanceApp
from personal_stats import PersonalAttendanceStatsUI
from attendance_widget import AttendanceWidget

# --- Tối ưu 1: Quản lý tập trung các stylesheet (QSS) ---
# Đã gom các stylesheet vào một dictionary để dễ quản lý.
STYLES = {
    "main_window": """
        QWidget {
            background-color: #f8fafc;
            font-family: 'Segoe UI', 'Arial Unicode MS', sans-serif;
        }
    """,
    "main_title": """
        QLabel {
            color: #1e293b;
            padding: 60px;
            background: white;
            border: 2px solid #e2e8f0;
            border-radius: 12px;
            margin-bottom: 30px;
            font-family: 'Segoe UI', 'Arial Unicode MS', sans-serif;
            font-weight: bold;
        }
    """,
    "login_button": """
        QPushButton {
            background-color: #3b82f6;
            color: white;
            border: none;
            border-radius: 12px;
            padding: 15px;
            font-weight: bold;
            font-size: 14px;
            font-family: 'Segoe UI', 'Arial Unicode MS', sans-serif;
        }
        QPushButton:hover { background-color: #2563eb; }
        QPushButton:pressed { background-color: #1d4ed8; }
    """,
    "attendance_button": """
        QPushButton {
            background-color: #10b981;
            color: white;
            border: none;
            border-radius: 12px;
            padding: 15px;
            font-weight: bold;
            font-size: 14px;
            font-family: 'Segoe UI', 'Arial Unicode MS', sans-serif;
        }
        QPushButton:hover { background-color: #059669; }
        QPushButton:pressed { background-color: #047857; }
    """,
    "login_window": """
        QWidget {
            background-color: #f8f9fa;
            font-family: 'Segoe UI', Arial, sans-serif;
        }
    """,
    "header": """
        QWidget {
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #2196F3, stop: 1 #1976D2);
            border-radius: 0;
        }
    """,
    "back_button": """
        QPushButton {
            background-color: rgba(255, 255, 255, 0.2);
            color: white;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-radius: 20px;
            font-size: 18px;
            font-weight: bold;
        }
        QPushButton:hover { background-color: rgba(255, 255, 255, 0.3); }
        QPushButton:pressed { background-color: rgba(255, 255, 255, 0.1); }
    """,
    "title_label": """
        QLabel {
            color: white;
            font-size: 24px;
            font-weight: bold;
            background: transparent;
        }
    """,
    "form_container": """
        QWidget {
            background-color: white;
            border-radius: 0;
        }
    """,
    "input_icon": """
        QLabel {
            background-color: #e9ecef;
            border: 2px solid #dee2e6;
            border-right: none;
            border-radius: 8px 0 0 8px;
            font-size: 18px;
        }
    """,
    "line_edit": """
        QLineEdit {
            padding: 12px 15px;
            border: 2px solid #dee2e6;
            border-left: none;
            border-radius: 0 8px 8px 0;
            font-size: 14px;
            background-color: white;
        }
        QLineEdit:focus { border-color: #2196F3; }
    """,
    "combo_box": """
        QComboBox {
            padding: 12px 15px;
            border: 2px solid #dee2e6;
            border-radius: 8px;
            background-color: white;
            font-size: 14px;
        }
        QComboBox:focus { border-color: #2196F3; }
        QComboBox QAbstractItemView {
            border: 2px solid #dee2e6;
            background-color: white;
            selection-background-color: #2196F3;
        }
    """,
    "form_login_button": """
        QPushButton {
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #2196F3, stop: 1 #1976D2);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
        }
        QPushButton:hover { background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #1976D2, stop: 1 #1565C0); }
        QPushButton:pressed { background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #1565C0, stop: 1 #0D47A1); }
    """,
    "message_box": """
        QMessageBox { background-color: white; }
        QMessageBox QLabel { color: #333; font-size: 14px; }
        QMessageBox QPushButton {
            background-color: #2196F3;
            color: white;
            border-radius: 4px;
            padding: 8px 16px;
            min-width: 80px;
        }
        QMessageBox QPushButton:hover { background-color: #1976D2; }
    """
}

# --- Tối ưu 2: Tạo Widget có thể tái sử dụng cho các trường nhập liệu ---
# Tạo một widget tùy chỉnh để kết hợp icon và QLineEdit, giúp mã gọn gàng hơn.
class IconLineEdit(QWidget):
    """Một widget kết hợp QLabel (icon) và QLineEdit."""

    def __init__(self, icon_text, placeholder_text, is_password=False, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        icon_label = QLabel(icon_text)
        icon_label.setFixedSize(45, 45)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(STYLES["input_icon"])

        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText(placeholder_text)
        self.line_edit.setFixedHeight(45)
        self.line_edit.setStyleSheet(STYLES["line_edit"])
        if is_password:
            self.line_edit.setEchoMode(QLineEdit.Password)

        layout.addWidget(icon_label)
        layout.addWidget(self.line_edit)

    def text(self):
        return self.line_edit.text().strip()

    def set_return_pressed_action(self, action):
        self.line_edit.returnPressed.connect(action)


class Controller:
    def __init__(self, db, face_recognizer):
        self.db = db
        self.face_recognizer = face_recognizer
        self.main_window = MainWindow()
        self.login_window = None
        self.attendance_window = None
        self.employee_app = None
        self.personal_stats_ui = None

        # Thêm biến để track current user
        self.current_user = None

        # Connect signals
        self.main_window.login_button.clicked.connect(lambda: self.show_window('login'))
        self.main_window.attendance_button.clicked.connect(lambda: self.show_window('attendance'))

        self.main_window.show()

    def show_window(self, window_type, user_info=None, selected_role=None):
        """Unified method to switch and manage windows."""
        self._hide_all_windows()

        if window_type == 'login':
            if not self.login_window:
                self.login_window = LoginWindow(
                    controller=self,
                    db=self.db,
                    face_recognizer=self.face_recognizer
                )
            self.login_window.show()

        elif window_type == 'employee_app':
            # Luôn tạo mới window khi đổi user
            if self.employee_app:
                self.employee_app.close()
                self.employee_app = None

            self.employee_app = EmployeeAttendanceApp(
                user_info=user_info,
                db=self.db,
                face_recognizer=self.face_recognizer,
                controller_window=self
            )
            self.current_user = user_info
            self.employee_app.show()

        elif window_type == 'personal_stats_ui':
            # Luôn tạo mới window khi đổi user
            if self.personal_stats_ui:
                self.personal_stats_ui.close()
                self.personal_stats_ui = None

            self.personal_stats_ui = PersonalAttendanceStatsUI(
                user_info=user_info,
                db=self.db,
                controller_window=self
            )
            self.current_user = user_info
            self.personal_stats_ui.show()

        elif window_type == 'attendance':
            if not self.attendance_window:
                self.attendance_window = AttendanceWidget(
                    controller_window=self,
                    db=self.db,
                    face_recognizer=self.face_recognizer
                )
            self.attendance_window.show()

        else:
            print(f"Warning: Unknown window type '{window_type}' requested.")

    def _hide_all_windows(self):
        """Helper to hide all windows managed by the controller."""
        if self.main_window:
            self.main_window.hide()
        if self.login_window:
            self.login_window.hide()
        if self.attendance_window:
            self.attendance_window.hide()
        if self.employee_app:
            self.employee_app.hide()
        if self.personal_stats_ui:
            self.personal_stats_ui.hide()

    def logout_user(self):
        """Đăng xuất và reset tất cả dữ liệu user"""
        # Reset current user
        self.current_user = None

        # Reset database current user
        if self.db:
            self.db.current_user = None

        # Reset login window
        if self.login_window:
            self.login_window.current_user = None

        # Đóng và reset các window chứa dữ liệu user
        if self.employee_app:
            self.employee_app.close()
            self.employee_app = None

        if self.personal_stats_ui:
            self.personal_stats_ui.close()
            self.personal_stats_ui = None

        # Hiển thị main window
        self.show_main_window()

    def show_main_window(self):
        """Explicit method to show the main window."""
        self._hide_all_windows()
        self.main_window.show()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hệ thống Quản lý Doanh nghiệp")
        self.setFixedSize(550, 600)
        self.setStyleSheet(STYLES["main_window"])
        self.center_window()
        self.init_ui()

    def center_window(self):
        """Center the window on the screen"""
        screen = QApplication.primaryScreen().availableGeometry()
        window = self.geometry()
        x = (screen.width() - window.width()) // 2
        y = (screen.height() - window.height()) // 2
        self.move(x, y)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(25)

        title = QLabel("HỆ THỐNG QUẢN LÝ DOANH NGHIỆP")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont('Segoe UI', 11, QFont.Bold))
        title.setStyleSheet(STYLES["main_title"])

        login_btn = QPushButton("🔐 Đăng nhập")
        login_btn.setFont(QFont('Segoe UI', 12))
        login_btn.setFixedHeight(60)
        login_btn.setCursor(Qt.PointingHandCursor)
        login_btn.setStyleSheet(STYLES["login_button"])

        attendance_btn = QPushButton("⏰ Chấm công")
        attendance_btn.setFont(QFont('Segoe UI', 12))
        attendance_btn.setFixedHeight(60)
        attendance_btn.setCursor(Qt.PointingHandCursor)
        attendance_btn.setStyleSheet(STYLES["attendance_button"])

        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(login_btn)
        layout.addWidget(attendance_btn)
        layout.addStretch(2)

        self.login_button = login_btn
        self.attendance_button = attendance_btn


class LoginWindow(QWidget):
    # --- Tối ưu 3: Sử dụng hằng số cho các chuỗi văn bản và cấu hình ---
    WINDOW_TITLE = "Đăng nhập"
    HEADER_TITLE = "Đăng nhập hệ thống"
    ICON_PATH = "./assets/img/login.png"
    WELCOME_TEXT = "Chào mừng bạn trở lại!"
    USERNAME_PLACEHOLDER = "Tên đăng nhập"
    PASSWORD_PLACEHOLDER = "Mật khẩu"
    ROLE_ADMIN = "Admin"
    ROLE_EMPLOYEE = "Nhân viên"
    ROLE_LABEL = "Quyền hạn:"

    def __init__(self, controller=None, db=None, face_recognizer=None):
        super().__init__()
        self.controller = controller
        self.current_user = None
        self.db = db
        self.face_recognizer = face_recognizer

        self._setup_window()
        self._create_ui()
        self._center_window()

    def _setup_window(self):
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setFixedSize(550, 600)
        self.setWindowIcon(QIcon(self.ICON_PATH))
        self.setStyleSheet(STYLES["login_window"])

    def _center_window(self):
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        window_geometry = self.frameGeometry()
        window_geometry.moveCenter(screen_geometry.center())
        self.move(window_geometry.topLeft())

    def _create_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header_widget = self._create_header()
        form_container = self._create_form_layout()

        main_layout.addWidget(header_widget)
        main_layout.addWidget(form_container)

        self.login_button.clicked.connect(self._handle_login)
        self.username_input.set_return_pressed_action(self._handle_login)
        self.password_input.set_return_pressed_action(self._handle_login)
        self.back_button.clicked.connect(self._go_back)

    # --- Tối ưu 4: Chia nhỏ hàm create_ui ---
    def _create_header(self):
        header_widget = QWidget()
        header_widget.setFixedHeight(80)
        header_widget.setStyleSheet(STYLES["header"])
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 15, 20, 15)

        self.back_button = QPushButton("←")
        self.back_button.setFixedSize(40, 40)
        self.back_button.setCursor(Qt.PointingHandCursor)
        self.back_button.setStyleSheet(STYLES["back_button"])

        title_label = QLabel(self.HEADER_TITLE)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(STYLES["title_label"])

        header_layout.addWidget(self.back_button)
        header_layout.addStretch()
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(QWidget())  # Spacer
        return header_widget

    def _create_form_layout(self):
        form_container = QWidget()
        form_container.setStyleSheet(STYLES["form_container"])
        layout = QVBoxLayout(form_container)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(25)

        # Sử dụng widget tùy chỉnh IconLineEdit
        self.username_input = IconLineEdit("👤", self.USERNAME_PLACEHOLDER)
        self.password_input = IconLineEdit("🔒", self.PASSWORD_PLACEHOLDER, is_password=True)

        self.role_combo = QComboBox()
        self.role_combo.addItems([self.ROLE_EMPLOYEE, self.ROLE_ADMIN])
        self.role_combo.setFixedHeight(45)
        self.role_combo.setStyleSheet(STYLES["combo_box"])

        self.login_button = QPushButton(self.WINDOW_TITLE)
        self.login_button.setFixedHeight(50)
        self.login_button.setCursor(Qt.PointingHandCursor)
        self.login_button.setStyleSheet(STYLES["form_login_button"])

        layout.addStretch()
        welcome_label = QLabel(self.WELCOME_TEXT)
        welcome_label.setAlignment(Qt.AlignCenter)
        welcome_label.setFont(QFont('Segoe UI', 16, QFont.Bold))
        layout.addWidget(welcome_label)
        layout.addStretch()

        layout.addWidget(self.username_input)
        layout.addWidget(self.password_input)
        layout.addWidget(QLabel(self.ROLE_LABEL))
        layout.addWidget(self.role_combo)
        layout.addWidget(self.login_button)
        layout.addStretch()

        return form_container

    def _handle_login(self):
        username = self.username_input.text()
        password = self.password_input.text()

        if not username or not password:
            self._show_message("Lỗi", "Vui lòng nhập đầy đủ thông tin!", QMessageBox.Warning)
            return

        selected_role = self.role_combo.currentText()
        db_role = "admin" if selected_role == self.ROLE_ADMIN else "user"

        if username == "admin" and password == "123":
            if selected_role != self.ROLE_ADMIN:
                self._show_message("Lỗi", "Tài khoản admin chỉ được sử dụng với quyền Admin!", QMessageBox.Warning)
                return
            self.current_user = {'username': 'admin', 'role': 'admin', 'full_name': 'System Administrator'}
            self._login_success(self.current_user, db_role)
            return

        if self.db is None:
            self._show_message("Lỗi", "Không thể kết nối cơ sở dữ liệu!", QMessageBox.Critical)
            return

        try:
            if not self.db.authenticate_user(username, password):
                self._show_message("Lỗi", "Sai tên đăng nhập hoặc mật khẩu!", QMessageBox.Warning)
                return

            self.current_user = self.db.current_user
            actual_role = self.current_user.get('role', 'user').lower()

            if db_role == "admin" and actual_role != "admin":
                self._show_message("Lỗi", "Bạn không có quyền Admin!", QMessageBox.Warning)
                return

            self._login_success(self.current_user, db_role)
        except Exception as e:
            self._show_message("Lỗi", f"Lỗi xác thực: {e}", QMessageBox.Critical)

    def _login_success(self, user_info, role):
        try:
            if role == "admin":
                self.controller.show_window('employee_app', user_info=user_info)
            else:
                self.controller.show_window('personal_stats_ui', user_info=user_info)

            role_name = self.ROLE_ADMIN if role == "admin" else self.ROLE_EMPLOYEE
            user_name = user_info.get('full_name', user_info['username'])
            self._show_message(
                "Đăng nhập thành công",
                f"Chào mừng {user_name}!\nQuyền hạn: {role_name}",
                QMessageBox.Information
            )
            self.close()
        except Exception as e:
            self._show_message("Lỗi", f"Lỗi khởi tạo ứng dụng: {e}", QMessageBox.Critical)

    def _show_message(self, title, message, icon):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setIcon(icon)
        msg_box.setStyleSheet(STYLES["message_box"])
        msg_box.exec_()

    def _go_back(self):
        """Override để logout đúng cách"""
        if self.controller:
            self.controller.logout_user()  # Sử dụng method logout thay vì show_main_window
        self.close()

    def closeEvent(self, event):
        """Override closeEvent để reset user khi đóng window"""
        self.current_user = None
        if self.db:
            self.db.current_user = None
        event.accept()
# Main application entry point
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Tạo đối tượng cơ sở dữ liệu và nhận diện khuôn mặt
    db = Database()
    face_recognizer = FaceRecognitionUtil()

    # Truyền vào Controller
    controller = Controller(db, face_recognizer)

    sys.exit(app.exec_())

