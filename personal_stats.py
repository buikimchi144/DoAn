import calendar
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QGridLayout, QScrollArea, QMessageBox, QSizePolicy, QDialog, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt, QDate, QSize
from PyQt5.QtGui import QFont, QColor
from datetime import datetime


class PersonalAttendanceStatsUI(QWidget):
    def __init__(self, user_info=None, db=None, controller_window=None):
        super().__init__()
        self.db = db
        self.controller_window = controller_window
        self.user_info = user_info if user_info else {}
        self.employee_id = self.user_info.get('employee_id')
        self.full_name = self.user_info.get('full_name', 'Unknown')

        self.main_layout = QVBoxLayout(self)
        self.calendar_widget = None
        self.attendance_data_by_date = {}
        self.current_date = QDate.currentDate()

        self.month_label = None
        self.present_value_label = None
        self.late_value_label = None
        self.early_leave_value_label = None
        self.late_and_early_value_label = None
        self.absent_value_label = None
        self.total_hours_value_label = None

        self.month_names = ["", "Tháng 1", "Tháng 2", "Tháng 3", "Tháng 4", "Tháng 5", "Tháng 6",
                            "Tháng 7", "Tháng 8", "Tháng 9", "Tháng 10", "Tháng 11", "Tháng 12"]

        self.init_ui()

    def init_ui(self):
        """Khởi tạo và xây dựng toàn bộ giao diện người dùng chính."""
        title = f"Thống kê chấm công cá nhân - {self.full_name}"
        if self.employee_id:
            title += f" (ID: {self.employee_id})"
        self.setWindowTitle(title)
        self.setGeometry(100, 100, 1400, 900)

        # -- Header --
        header_frame = QFrame()
        header_frame.setStyleSheet(
            "QFrame { background-color: #f8f9fa; border-bottom: 2px solid #dee2e6; padding: 5px; }")
        header_layout = QHBoxLayout(header_frame)
        user_info_label = QLabel(f"Xin chào, {self.full_name}")
        user_info_label.setFont(QFont("Arial", 14, QFont.Bold))
        user_info_label.setStyleSheet("color: #333;")
        buttons_container = QWidget()
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(10)
        info_btn = self._create_styled_button("👤 Thông tin", QSize(130, 40), "#17a2b8", "#138496",
                                              self.show_employee_info)
        logout_btn = self._create_styled_button("🚪 Đăng xuất", QSize(130, 40), "#dc3545", "#c82333", self.logout)
        buttons_layout.addWidget(info_btn)
        buttons_layout.addWidget(logout_btn)
        header_layout.addWidget(user_info_label)
        header_layout.addStretch()
        header_layout.addWidget(buttons_container)
        self.main_layout.addWidget(header_frame)

        # -- Thanh điều hướng tháng --
        nav_frame = QFrame()
        nav_frame.setStyleSheet("QFrame { background-color: white; border-bottom: 1px solid #dee2e6; padding: 15px; }")
        nav_layout = QHBoxLayout(nav_frame)
        prev_btn = self._create_styled_button("◀ Tháng trước", QSize(150, 40), "#6c757d", "#5a6268",
                                              self.previous_month)
        next_btn = self._create_styled_button("Tháng sau ▶", QSize(150, 40), "#6c757d", "#5a6268", self.next_month)
        today_btn = self._create_styled_button("Hôm nay", QSize(120, 40), "#28a745", "#218838", self.go_to_today)
        self.month_label = QLabel()
        self.month_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.month_label.setAlignment(Qt.AlignCenter)
        self.month_label.setStyleSheet("color: #333;")
        self.month_label.setText(f"{self.month_names[self.current_date.month()]} {self.current_date.year()}")
        nav_layout.addWidget(prev_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(self.month_label)
        nav_layout.addStretch()
        nav_layout.addWidget(today_btn)
        nav_layout.addWidget(next_btn)
        self.main_layout.addWidget(nav_frame)

        # -- Khu vực tổng quan thống kê --
        stats_frame = QFrame()
        stats_frame.setStyleSheet(
            "QFrame { background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px; margin: 10px; padding: 15px; }")
        stats_layout = QHBoxLayout(stats_frame)
        present_card, self.present_value_label = self._create_stat_card("Có mặt", "0", "#28a745")
        late_card, self.late_value_label = self._create_stat_card("Đi trễ", "0", "#ffc107")
        early_leave_card, self.early_leave_value_label = self._create_stat_card("Về sớm", "0", "#fd7e14")
        late_and_early_card, self.late_and_early_value_label = self._create_stat_card("Đi trễ-Về sớm", "0", "#e83e8c")
        absent_card, self.absent_value_label = self._create_stat_card("Vắng mặt", "0", "#dc3545")
        total_hours_card, self.total_hours_value_label = self._create_stat_card("Tổng giờ", "0h", "#007bff")
        stats_layout.addWidget(present_card)
        stats_layout.addWidget(late_card)
        stats_layout.addWidget(early_leave_card)
        stats_layout.addWidget(late_and_early_card)
        stats_layout.addWidget(absent_card)
        stats_layout.addWidget(total_hours_card)
        stats_layout.addStretch()
        self.main_layout.addWidget(stats_frame)

        self._build_calendar_view()

    def _create_styled_button(self, text, fixed_size, bg_color, hover_color, clicked_slot):
        """Hàm trợ giúp tạo button với style nhất quán."""
        btn = QPushButton(text)
        btn.setFixedSize(fixed_size)
        btn.setStyleSheet(f"""
            QPushButton {{ background-color: {bg_color}; color: white; border: none; border-radius: 6px; font-weight: bold; font-size: 12px; }}
            QPushButton:hover {{ background-color: {hover_color}; }}
        """)
        btn.clicked.connect(clicked_slot)
        return btn

    def show_employee_info(self):
        """Hiển thị thông tin chi tiết của nhân viên."""
        dialog = QDialog(self)
        dialog.setModal(True)
        dialog.setWindowTitle("Thông tin nhân viên")
        dialog.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        dialog.setMinimumSize(650, 500)
        dialog.resize(700, 550)
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        header_label = QLabel("THÔNG TIN NHÂN VIÊN")
        header_label.setFont(QFont("Arial", 16, QFont.Bold))
        header_label.setAlignment(Qt.AlignCenter)
        header_label.setStyleSheet(
            "QLabel { color: #2c3e50; padding: 15px; background-color: #ecf0f1; border-radius: 8px; border: 1px solid #bdc3c7; }")
        main_layout.addWidget(header_label)

        info_frame = QFrame()
        info_frame.setStyleSheet(
            "QFrame { background-color: #ffffff; border: 1px solid #dee2e6; border-radius: 8px; padding: 10px; }")
        info_layout = QVBoxLayout(info_frame)
        info_layout.setSpacing(10)

        join_date_formatted = 'Không có thông tin'
        raw_join_date = self.user_info.get('join_date')
        if raw_join_date:
            if isinstance(raw_join_date, str):
                for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']:
                    try:
                        join_date_formatted = datetime.strptime(raw_join_date, fmt).strftime('%d/%m/%Y')
                        break
                    except ValueError:
                        pass
            elif isinstance(raw_join_date, datetime):
                join_date_formatted = raw_join_date.strftime('%d/%m/%Y')

        info_data = {
            "👤 Họ và tên:": self.full_name,
            "🆔 Mã nhân viên:": str(self.employee_id if self.employee_id else 'Không có thông tin'),
            "👤 Tên đăng nhập:": self.user_info.get('username', 'Không có thông tin'),
            "🏢 Phòng ban:": self.user_info.get('department', 'Không có thông tin'),
            "🔑 Vai trò:": self.user_info.get('role', 'Không có thông tin'),
            "📅 Ngày vào làm:": join_date_formatted,
        }

        for label_text, value_text in info_data.items():
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(10, 8, 10, 8)
            label = QLabel(label_text)
            label.setFont(QFont("Arial", 10, QFont.Bold))
            label.setStyleSheet("color: #495057;")
            label.setFixedWidth(180)
            value = QLabel(str(value_text))
            value.setFont(QFont("Arial", 10))
            value.setStyleSheet(
                "color: #212529; background-color: #f8f9fa; padding: 8px; border-radius: 4px; border: 1px solid #ced4da;")
            value.setWordWrap(True)
            row_layout.addWidget(label)
            row_layout.addWidget(value, 1)
            info_layout.addWidget(row_widget)

        main_layout.addWidget(info_frame)
        main_layout.addStretch()

        close_btn = QPushButton("Đóng")
        close_btn.setFixedSize(100, 35)
        close_btn.setFont(QFont("Arial", 10, QFont.Bold))
        close_btn.setStyleSheet(
            "QPushButton { background-color: #6c757d; color: white; border: none; border-radius: 5px; } QPushButton:hover { background-color: #5a6268; }")
        close_btn.clicked.connect(dialog.accept)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)
        dialog.exec_()

    def _build_calendar_view(self):
        """Tạo hoặc cập nhật chế độ xem lịch chấm công."""
        if self.calendar_widget: self.calendar_widget.deleteLater()
        self._load_attendance_data()

        calendar_container = QFrame()
        calendar_container.setStyleSheet(
            "QFrame { background-color: white; border: 1px solid #dee2e6; border-radius: 8px; margin: 10px; }")
        calendar_layout = QVBoxLayout(calendar_container)

        weekdays_frame = QFrame()
        weekdays_layout = QHBoxLayout(weekdays_frame)
        weekdays_layout.setSpacing(0)
        weekdays_layout.setContentsMargins(0, 0, 0, 0)
        for day_name in ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]:
            day_label = QLabel(day_name)
            day_label.setAlignment(Qt.AlignCenter)
            day_label.setStyleSheet(
                "QLabel { background-color: #6c757d; color: white; padding: 15px; font-weight: bold; border-right: 1px solid #495057; }")
            weekdays_layout.addWidget(day_label)
        calendar_layout.addWidget(weekdays_frame)

        calendar_grid_widget = QWidget()
        self.calendar_grid = QGridLayout()
        self.calendar_grid.setSpacing(2)
        self.calendar_grid.setContentsMargins(5, 5, 5, 5)
        calendar_grid_widget.setLayout(self.calendar_grid)

        scroll_area = QScrollArea()
        scroll_area.setWidget(calendar_grid_widget)
        scroll_area.setWidgetResizable(True)
        calendar_layout.addWidget(scroll_area)

        self._populate_calendar()
        self.calendar_widget = calendar_container
        self.main_layout.addWidget(self.calendar_widget)

    def _populate_calendar(self):
        """Điền dữ liệu vào các ô ngày trong lưới lịch."""
        for i in reversed(range(self.calendar_grid.count())):
            widget = self.calendar_grid.itemAt(i).widget()
            if widget: widget.deleteLater()

        year, month = self.current_date.year(), self.current_date.month()
        cal = calendar.monthcalendar(year, month)
        for row, week in enumerate(cal):
            for col, day in enumerate(week):
                if day == 0:
                    empty_cell = QFrame()
                    empty_cell.setStyleSheet("QFrame { background-color: #f8f9fa; }")
                    empty_cell.setFixedSize(200, 120)
                    self.calendar_grid.addWidget(empty_cell, row, col)
                else:
                    self.calendar_grid.addWidget(self._create_day_cell(year, month, day), row, col)

    def _create_day_cell(self, year, month, day):
        """Tạo một ô ngày cho lịch với trạng thái chấm công."""
        date_str = f"{year}-{month:02d}-{day:02d}"
        cell = QFrame()
        cell.setFixedSize(200, 130)
        cell.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        is_today = (date_str == QDate.currentDate().toString("yyyy-MM-dd"))
        attendance_info = self.attendance_data_by_date.get(date_str)
        bg_color, border_color, status_color, status_text = "#ffffff", "#dee2e6", "#6c757d", "Không có dữ liệu"

        if attendance_info:
            status_db = attendance_info.get('status', '')
            status_text = status_db
            if status_db in ["Đúng giờ", "Có mặt"]:
                bg_color, border_color, status_color = "#d4edda", "#28a745", "#155724"
            elif status_db in ["Đi trễ", "Về sớm", "Đi trễ về sớm"]:
                bg_color, border_color, status_color = "#fff3cd", "#ffc107", "#856404"
            elif status_db == "Vắng":
                bg_color, border_color, status_color = "#f8d7da", "#dc3545", "#721c24"
            else:
                bg_color, border_color, status_color = "#e2e3e5", "#6c757d", "#383d41"

        cell.setStyleSheet(
            f"QFrame {{ background-color: {bg_color}; border: {'3px' if is_today else '2px'} solid {'#007bff' if is_today else border_color}; border-radius: 8px; margin: 1px; }}")

        # Layout chính của ô, theo chiều dọc
        layout = QVBoxLayout(cell)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)  # Giảm khoảng cách giữa các hàng

        day_label = QLabel(str(day))
        day_label.setFont(QFont("Arial", 10, QFont.Bold))
        day_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        if is_today: day_label.setStyleSheet("color: #007bff;")
        layout.addWidget(day_label)

        if attendance_info:
            # ** THAY ĐỔI: Thêm thẳng các label vào layout dọc **

            # Hàng 1: Giờ vào
            if attendance_info.get('time_in'):
                time_in_label = QLabel(f"Vào: {attendance_info['time_in']}")
                time_in_label.setFont(QFont("Arial", 8))
                time_in_label.setStyleSheet("color: #28a745; font-weight: bold; background-color: transparent;")
                layout.addWidget(time_in_label)

            # Hàng 2: Giờ ra
            if attendance_info.get('time_out'):
                time_out_label = QLabel(f"Ra: {attendance_info['time_out']}")
                time_out_label.setFont(QFont("Arial", 8))
                time_out_label.setStyleSheet("color: #dc3545; font-weight: bold; background-color: transparent;")
                layout.addWidget(time_out_label)

            # Thêm một khoảng trống co giãn để đẩy trạng thái xuống dưới cùng
            layout.addStretch(1)

            # Hàng cuối: Trạng thái
            status_label = QLabel(status_text)
            status_label.setFont(QFont("Arial", 9, QFont.Bold))
            status_label.setStyleSheet(f"color: {status_color}; background-color: transparent;")
            status_label.setAlignment(Qt.AlignCenter)
            status_label.setWordWrap(True)
            layout.addWidget(status_label)
        else:
            # Nếu không có thông tin, thêm một stretch để giữ layout nhất quán
            layout.addStretch(1)

        return cell

    def _load_attendance_data(self):
        """Tải dữ liệu chấm công và cập nhật thống kê."""
        if not self.employee_id: return
        try:
            year, month = self.current_date.year(), self.current_date.month()
            first_day = f"{year}-{month:02d}-01"
            last_day_of_month = calendar.monthrange(year, month)[1]
            last_day = f"{year}-{month:02d}-{last_day_of_month:02d}"
            attendance_data = self.db.attendance.get_attendance_logs_by_employee(self.employee_id, first_day, last_day)

            self.attendance_data_by_date = {}
            stats = {'present': 0, 'late': 0, 'early_leave': 0, 'late_and_early': 0, 'absent': 0, 'total_hours': 0.0}

            for record in attendance_data:
                date_key, time_in, time_out, working_hours, status = record[3], record[4], record[5], record[6], record[
                    7]
                self.attendance_data_by_date[date_key] = {
                    'time_in': time_in.split('.')[0] if time_in else "",
                    'time_out': time_out.split('.')[0] if time_out else "",
                    'status': status, 'total_hours': working_hours, 'session_id': record[0]
                }

                if status in ["Đúng giờ", "Có mặt"]:
                    stats['present'] += 1
                elif status == "Đi trễ":
                    stats['late'] += 1
                elif status == "Về sớm":
                    stats['early_leave'] += 1
                elif status == "Đi trễ về sớm":
                    stats['late_and_early'] += 1
                elif status == "Vắng":
                    stats['absent'] += 1

                if working_hours:
                    try:
                        stats['total_hours'] += float(str(working_hours).replace('h', '').strip())
                    except (ValueError, TypeError):
                        pass

            self.present_value_label.setText(str(stats['present']))
            self.late_value_label.setText(str(stats['late']))
            self.early_leave_value_label.setText(str(stats['early_leave']))
            self.late_and_early_value_label.setText(str(stats['late_and_early']))
            self.absent_value_label.setText(str(stats['absent']))
            self.total_hours_value_label.setText(f"{stats['total_hours']:.1f}h")

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi tải dữ liệu: {str(e)}")

    def _create_stat_card(self, title, value, color):
        """Tạo một thẻ thống kê trực quan."""
        card = QFrame()
        card.setFrameStyle(QFrame.NoFrame)
        card.setMinimumWidth(185)
        card.setMaximumHeight(125)
        card.setStyleSheet(
            "QFrame { border: none; border-radius: 16px; background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f8f9fa); margin: 4px; padding: 0px; } QFrame:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #f1f3f4); }")
        shadow = QGraphicsDropShadowEffect(blurRadius=15, xOffset=0, yOffset=4, color=QColor(0, 0, 0, 40))
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 18, 16, 14)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Segoe UI", 9, QFont.Medium))
        title_label.setStyleSheet(
            "color: #495057; border: none; padding: 0px; margin: 0px; font-weight: 500; letter-spacing: 0.5px; text-transform: uppercase;")
        title_label.setWordWrap(True)

        value_label = QLabel(str(value))
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setFont(QFont("Segoe UI", 26, QFont.Bold))
        value_label.setStyleSheet(
            f"color: {color}; border: none; padding: 0px; margin: 0px; font-weight: 700; letter-spacing: -1px;")

        layout.addWidget(title_label)
        layout.addStretch(1)
        layout.addWidget(value_label)
        layout.addStretch(1)
        return card, value_label

    def previous_month(self):
        """Điều hướng đến tháng trước."""
        self.current_date = self.current_date.addMonths(-1)
        self.month_label.setText(f"{self.month_names[self.current_date.month()]} {self.current_date.year()}")
        self._build_calendar_view()

    def next_month(self):
        """Điều hướng đến tháng sau."""
        self.current_date = self.current_date.addMonths(1)
        self.month_label.setText(f"{self.month_names[self.current_date.month()]} {self.current_date.year()}")
        self._build_calendar_view()

    def go_to_today(self):
        """Điều hướng đến tháng hiện tại."""
        self.current_date = QDate.currentDate()
        self.month_label.setText(f"{self.month_names[self.current_date.month()]} {self.current_date.year()}")
        self._build_calendar_view()

    def logout(self):
        """Xử lý hành động đăng xuất."""
        self.hide()
        if self.controller_window:
            self.controller_window.show_main_window()
        else:
            print("Controller window not available for logout action.")