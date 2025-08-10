from PyQt5.QtWidgets import (QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout,
                             QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
                             QAbstractItemView, QStyle, QLineEdit)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QFont

# --- STYLESHEET CONSTANTS ---
STYLES = {
    "sidebar": {
        "frame": "background: white; border-right: 2px solid #e5e7eb;",
        "header": """
            QLabel {
                color: white; font-size: 13px; font-weight: bold;
                padding: 20px 16px; background: #2196F3;
                border-radius: 12px; border: 1px solid #60a5fa;
            }
        """,
        "nav_button": """
            QPushButton {
                background: #e5e7eb; color: #374151; border: 1px solid #e5e7eb;
                border-radius: 10px; padding: 14px 16px; text-align: left;
                font-size: 14px; font-weight: 500;
            }
            QPushButton:hover {
                background: #e5e7eb; color: #1f2937; border: 1px solid #d1d5db;
            }
            QPushButton[active="true"] {
                background: #374151; color: white; border: 1px solid #4b5563;
                font-weight: bold;
            }
        """,
        "user_card": "background: #f8fafc; border-radius: 12px; border: 1px solid #e2e8f0;",
        "logout_button": """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #dc2626, stop:1 #b91c1c);
                color: white; border: 1px solid #ef4444; border-radius: 10px;
                padding: 12px 16px; font-size: 14px; font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #b91c1c, stop:1 #991b1b);
            }
        """
    },
    "table": {
        "widget": """
            QTableWidget {
                background: white; border: 1px solid #dee2e6; border-radius: 8px;
                font-size: 13px; gridline-color: #f1f3f4;
            }
            QHeaderView::section {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f8f9fa, stop:1 #e9ecef);
                padding: 12px 8px; border: none; border-bottom: 2px solid #dee2e6;
                border-right: 1px solid #dee2e6; font-weight: 600; color: #495057;
            }
            QTableWidget::item { padding: 12px 8px; border-bottom: 1px solid #f1f3f4; }
            QTableWidget::item:selected { background: #e3f2fd; color: #1565c0; }
        """,
        "add_button": """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4CAF50, stop:1 #45a049);
                color: white; border: none; padding: 0px 20px;
                border-radius: 21px; font-weight: 600; font-size: 13px;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #45a049, stop:1 #3d8b40); }
            QPushButton:pressed { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3d8b40, stop:1 #2e7d32); }
        """
    },
    "action_button": """
        QPushButton {{ background-color: {base}; border-radius: 4px; }}
        QPushButton:hover {{ background-color: {hover}; }}
        QPushButton:pressed {{ background-color: {pressed}; }}
    """
}


class CustomButton(QPushButton):
    def __init__(self, text, button_type="primary", callback=None, additional_buttons=None):
        super().__init__(text)
        self.setMinimumHeight(36)
        self.setCursor(Qt.PointingHandCursor)
        self.callback = callback
        self.additional_buttons = additional_buttons if additional_buttons else []

        base_style = """
            QPushButton {
                border: none; border-radius: 6px; padding: 8px 16px;
                font-weight: 500; font-size: 13px;
            }
            QPushButton:hover { opacity: 0.8; }
            QPushButton:pressed { opacity: 0.6; }
        """
        colors = {
            "primary": "background: #3b82f6; color: white;",
            "success": "background: #10b981; color: white;",
            "danger": "background: #ef4444; color: white;"
        }
        self.setStyleSheet(base_style + colors.get(button_type, colors["primary"]))

    def create_button_layout(self):
        """Tạo layout chứa chính nút này và các nút bổ sung nếu có"""
        layout = QHBoxLayout()
        layout.addWidget(self)

        for button in self.additional_buttons:
            layout.addWidget(button)

        layout.addStretch()
        return layout


class Sidebar(QFrame):
    def __init__(self, callbacks: dict):
        super().__init__()
        self.setFixedWidth(260)
        self.callbacks = callbacks
        self.active_button = None
        self.nav_buttons = []
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(STYLES["sidebar"]["frame"])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header = QLabel("QUẢN LÝ DOANH NGHIỆP")
        header.setStyleSheet(STYLES["sidebar"]["header"])
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        # Navigation
        nav_items = [
            ("✍️", "Đăng ký nhân viên", "show_register"),
            ("👥", "Quản lý nhân viên", "show_employee_list"),
            ("📊", "Thống kê báo cáo", "show_attendance_stats"),
        ]
        for icon, text, callback_key in nav_items:
            btn = self._create_nav_button(icon, text, callback_key)
            self.nav_buttons.append(btn)
            layout.addWidget(btn)

        if self.nav_buttons:
            self._set_active_button(self.nav_buttons[0])  # Set first button active by default

        layout.addStretch()

        # User Info Card
        user_card = QFrame()
        user_card.setStyleSheet(STYLES["sidebar"]["user_card"])
        user_layout = QVBoxLayout(user_card)
        user_name = QLabel("👤 Admin User")
        user_name.setStyleSheet("font-size: 14px; font-weight: bold; color: #1f2937;")
        user_status = QLabel("🟢 Trực tuyến")
        user_status.setStyleSheet("font-size: 12px; color: #10b981;")
        user_layout.addWidget(user_name)
        user_layout.addWidget(user_status)
        layout.addWidget(user_card)

        # Logout Button
        logout_btn = QPushButton("🚪  Đăng xuất")
        logout_btn.setStyleSheet(STYLES["sidebar"]["logout_button"])
        if "logout" in self.callbacks:
            logout_btn.clicked.connect(self.callbacks["logout"])
        layout.addWidget(logout_btn)

    def _create_nav_button(self, icon, text, callback_key):
        btn = QPushButton(f"{icon}  {text}")
        btn.setStyleSheet(STYLES["sidebar"]["nav_button"])
        btn.setProperty("active", False)  # Custom property for styling

        def on_click():
            self._set_active_button(btn)
            if self.callbacks.get(callback_key):
                self.callbacks[callback_key]()

        btn.clicked.connect(on_click)
        return btn

    def _set_active_button(self, new_active_button):
        if self.active_button:
            self.active_button.setProperty("active", False)
            self.active_button.style().unpolish(self.active_button)
            self.active_button.style().polish(self.active_button)

        new_active_button.setProperty("active", True)
        new_active_button.style().unpolish(new_active_button)
        new_active_button.style().polish(new_active_button)

        self.active_button = new_active_button


class CustomTableWidget(QWidget):
    add_clicked = pyqtSignal()
    edit_clicked = pyqtSignal(int)
    delete_clicked = pyqtSignal(int)
    status_clicked = pyqtSignal(int)
    detail_clicked = pyqtSignal(int)

    def __init__(self, headers, data, add_button_text=None, show_status_btn=False, show_detail_btn=False):
        super().__init__()
        self.headers = headers + ["Thao tác"]
        self.data = data
        self.show_status_btn = show_status_btn
        self.show_detail_btn = show_detail_btn
        self._setup_ui(add_button_text)

    def _setup_ui(self, add_button_text):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        if add_button_text:
            header_layout = QHBoxLayout()
            header_layout.addStretch()
            add_btn = QPushButton(f"+ {add_button_text}")
            add_btn.setFixedHeight(42)
            add_btn.setMinimumWidth(120)
            add_btn.setStyleSheet(STYLES["table"]["add_button"])
            add_btn.clicked.connect(self.add_clicked.emit)
            header_layout.addWidget(add_btn)
            layout.addLayout(header_layout)

        # Table setup
        self.table = QTableWidget()
        self.table.setStyleSheet(STYLES["table"]["widget"])
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(55)

        header = self.table.horizontalHeader()
        for col in range(len(self.headers) - 1):
            header.setSectionResizeMode(col, QHeaderView.Stretch)

        action_col_idx = len(self.headers) - 1
        action_width = self._calculate_action_column_width()
        header.setSectionResizeMode(action_col_idx, QHeaderView.Fixed)
        self.table.setColumnWidth(action_col_idx, action_width)

        layout.addWidget(self.table)
        self.refresh_data(self.data)

    def _calculate_action_column_width(self):
        button_count = 2  # Edit, Delete
        if self.show_detail_btn: button_count += 1
        if self.show_status_btn: button_count += 1
        return (button_count * 30) + ((button_count + 1) * 5) + 20  # width * count + spacing + margins

    def _create_action_button(self, icon, tooltip, colors, on_click):
        btn = QPushButton()
        btn.setIcon(self.style().standardIcon(icon))
        btn.setIconSize(QSize(12, 12))
        btn.setFixedSize(30, 30)
        btn.setToolTip(tooltip)
        btn.setStyleSheet(STYLES["action_button"].format(**colors))
        btn.clicked.connect(on_click)
        return btn

    def _populate_action_buttons(self, row_idx):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignCenter)

        buttons_to_add = []
        if self.show_detail_btn:
            buttons_to_add.append(self._create_action_button(
                QStyle.SP_FileDialogDetailedView, "Xem chi tiết",
                {"base": "#007bff", "hover": "#0056b3", "pressed": "#004085"},
                lambda: self.detail_clicked.emit(row_idx)))

        buttons_to_add.append(self._create_action_button(
            QStyle.SP_FileDialogContentsView, "Sửa",
            {"base": "#FF9800", "hover": "#F57C00", "pressed": "#E65100"},
            lambda: self.edit_clicked.emit(row_idx)))

        if self.show_status_btn:
            buttons_to_add.append(self._create_action_button(
                QStyle.SP_BrowserReload, "Chuyển trạng thái",
                {"base": "#2196F3", "hover": "#1976D2", "pressed": "#0D47A1"},
                lambda: self.status_clicked.emit(row_idx)))

        buttons_to_add.append(self._create_action_button(
            QStyle.SP_TrashIcon, "Xóa",
            {"base": "#F44336", "hover": "#D32F2F", "pressed": "#B71C1C"},
            lambda: self.delete_clicked.emit(row_idx)))

        for btn in buttons_to_add:
            layout.addWidget(btn)

        self.table.setCellWidget(row_idx, len(self.headers) - 1, widget)
        self.table.setRowHeight(row_idx, 60)

    def refresh_data(self, new_data):
        self.data = new_data
        self.table.setRowCount(0)  # Clear table including widgets
        self.table.setRowCount(len(self.data))

        for row_idx, row_data in enumerate(self.data):
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row_idx, col_idx, item)
            self._populate_action_buttons(row_idx)


