import pyodbc
import logging
from datetime import datetime, time, timedelta
import cv2
import os
import traceback

class AttendanceOperations:
    def __init__(self, conn, cursor):
        self.conn = conn
        self.cursor = cursor

    def get_attendance_logs_detail(self, employee_id, work_date):
        """
        Lấy chi tiết các log chấm công của nhân viên trong ngày làm việc.
        """
        try:
            # Chuyển work_date thành datetime.date
            if isinstance(work_date, str):
                if '/' in work_date:
                    work_date = datetime.strptime(work_date, "%d/%m/%Y").date()
                else:
                    work_date = datetime.strptime(work_date, "%Y-%m-%d").date()
            elif isinstance(work_date, datetime):
                work_date = work_date.date()

            query = """
                    SELECT al.LogID,
                           al.EmployeeID,
                           e.FullName,
                           al.AttendanceTime,
                           CAST(al.AttendanceTime AS DATE) AS AttendanceDate,
                           al.Status,
                           al.FaceImagePath,
                           al.Confidence
                    FROM AttendanceLogs al
                             JOIN Employees e ON al.EmployeeID = e.EmployeeID
                    WHERE al.EmployeeID = ?
                      AND CAST(al.AttendanceTime AS DATE) = ?
                    ORDER BY al.AttendanceTime ASC
                    """

            cursor = self.conn.cursor()
            # 👉 Chuyển work_date về chuỗi 'YYYY-MM-DD' để tránh lỗi SQLBindParameter
            cursor.execute(query, (employee_id, work_date.strftime("%Y-%m-%d")))
            result = cursor.fetchall()

            print(f"\n📋 Attendance Logs for Employee {employee_id} on {work_date.strftime('%d/%m/%Y')}:")
            for row in result:
                # In ra thông tin, có thể bỏ qua phần dữ liệu ảnh để dễ đọc
                print(row[:-2], type(row[6]), row[-1])

            return result

        except Exception as e:
            print(f"❌ Error getting attendance logs detail: {e}")
            return []

    def determine_status(self, checkin_time_str, checkout_time_str):
        """
        Xác định trạng thái làm việc dựa trên thời gian check in và check out
        """
        try:
            # Helper function to parse time from SQL Server format
            def parse_sql_time(time_str):
                if isinstance(time_str, str):
                    # Remove microseconds part (.0000000) from SQL Server TIME format
                    clean_time = time_str.split('.')[0]
                    return datetime.strptime(clean_time, '%H:%M:%S').time()
                else:
                    return time_str

            # Parse times
            checkin_time = parse_sql_time(checkin_time_str)
            checkout_time = datetime.strptime(checkout_time_str, '%H:%M:%S').time()

            # Định nghĩa giờ chuẩn
            standard_checkin = time(7, 30)  # 7:30 AM
            standard_checkout = time(16, 30)  # 5:00 PM

            # Xác định trạng thái
            is_late = checkin_time > standard_checkin
            is_early_leave = checkout_time < standard_checkout

            if is_late and is_early_leave:
                return "Đi trễ về sớm"
            elif is_late:
                return "Đi trễ"
            elif is_early_leave:
                return "Về sớm"
            else:
                return "Đúng giờ"

        except Exception as e:
            print(f"Error in determine_status: {e}")
            return "Không xác định"

    def calculate_work_hours(self, check_in, check_out, attendance_date):
        if not check_in:
            return '---'

        now = datetime.now()

        # Nếu chưa check_out và không phải hôm nay thì không tính
        if check_out is None and attendance_date.date() != now.date():
            return '---'

        # Thời gian bắt đầu tính từ 7h30 nếu đến sớm hơn
        start_time = max(check_in, check_in.replace(hour=7, minute=30, second=0, microsecond=0))

        # Nếu chưa check out, dùng giờ hiện tại hoặc 16:30, tùy cái nào nhỏ hơn
        if check_out is None and attendance_date.date() == now.date():
            current_time = min(now.time(), time(16, 30))
            end_time = datetime.combine(attendance_date.date(), current_time)
        elif check_out and check_out.time() > time(16, 30):
            end_time = check_out.replace(hour=16, minute=30, second=0, microsecond=0)
        else:
            end_time = check_out

        # Tính phút làm việc
        work_duration = (end_time - start_time).total_seconds() / 60.0

        # Trừ giờ nghỉ trưa nếu có
        lunch_start = time(11, 40)
        lunch_end = time(12, 40)
        if start_time.time() < lunch_end and (
                (check_out and check_out.time() > lunch_start) or
                (check_out is None and now.time() > lunch_start)
        ):
            work_duration -= 60

        hours = round(work_duration / 60.0, 2)
        return f"{hours} giờ" if hours > 0 else '---'

    def log_attendance(self, employee_id, check_type='Check In', face_img=None, confidence=None):
        try:
            now = datetime.now()
            today_str = now.strftime('%Y-%m-%d')
            current_time_str = now.strftime('%H:%M:%S')
            now_str = now.strftime('%Y-%m-%d %H:%M:%S')

            # --- Logic lưu ảnh ---
            face_img_path = None
            if face_img is not None:
                image_storage_dir = os.path.join("attendance_images", today_str)
                os.makedirs(image_storage_dir, exist_ok=True)
                filename = f"{employee_id}_{now.strftime('%Y%m%d%H%M%S%f')}.png"
                face_img_path = os.path.join(image_storage_dir, filename)
                is_success = cv2.imwrite(face_img_path, face_img)
                if not is_success:
                    print(f"Lỗi: Không thể lưu ảnh khuôn mặt cho nhân viên {employee_id} vào {face_img_path}")
                    face_img_path = None

            # 1. Lưu vào AttendanceLogs
            attendance_sql = """
                             INSERT INTO AttendanceLogs(EmployeeID, AttendanceTime, Status, CreatedAt, FaceImagePath,
                                                        Confidence)
                             VALUES (?, ?, ?, ?, ?, ?)
                             """
            confidence_value = float(f"{confidence * 100:.2f}") if confidence is not None else None
            attendance_params = (employee_id, now_str, check_type, now_str, face_img_path, confidence_value)
            self.cursor.execute(attendance_sql, attendance_params)

            # 2. Kiểm tra WorkSessions hiện tại
            session_check_sql = """
                                SELECT SessionID, CheckIn, CheckOut, WorkingHours
                                FROM WorkSessions
                                WHERE EmployeeID = ?
                                  AND WorkDate = ?
                                """
            self.cursor.execute(session_check_sql, (employee_id, today_str))
            existing_session = self.cursor.fetchone()

            if check_type == 'Check In':
                if existing_session:
                    print(f"Phiên đã tồn tại cho nhân viên {employee_id} hôm nay - Check In sẽ không được cập nhật")
                    self.conn.commit()
                    return True
                else:
                    temp_status = 'Đi trễ' if datetime.strptime(current_time_str, '%H:%M:%S').time() > time(7,
                                                                                                            30) else 'Đúng giờ'
                    insert_sql = """
                                 INSERT INTO WorkSessions(EmployeeID, WorkDate, CheckIn, Status, CreatedAt)
                                 VALUES (?, ?, ?, ?, ?)
                                 """
                    self.cursor.execute(insert_sql, (employee_id, today_str, current_time_str, temp_status, now_str))
                    print(f"Đã tạo phiên mới với CheckIn cho nhân viên {employee_id}")

            else:  # Check Out
                if existing_session:
                    if existing_session[1] is None:
                        print(f"❌ LỖI: Không thể Check Out khi chưa Check In cho nhân viên {employee_id}")
                        self.conn.rollback()
                        return False
                    if existing_session[2] is not None:
                        print(f"CheckOut đã tồn tại cho nhân viên {employee_id} hôm nay - bỏ qua")
                        self.conn.commit()
                        return True

                    working_hours = existing_session[3]
                    try:
                        def parse_sql_time(time_str):
                            if isinstance(time_str, str):
                                clean_time = time_str.split('.')[0]
                                return datetime.strptime(clean_time, '%H:%M:%S').time()
                            else:
                                return time_str

                        checkin_time = parse_sql_time(existing_session[1])
                        checkout_time = datetime.strptime(current_time_str, '%H:%M:%S').time()

                        today_date = datetime.strptime(today_str, '%Y-%m-%d').date()
                        checkin_datetime = datetime.combine(today_date, checkin_time)
                        checkout_datetime = datetime.combine(today_date, checkout_time)

                        if checkout_datetime < checkin_datetime:
                            checkout_datetime += timedelta(days=1)

                        working_hours = (checkout_datetime - checkin_datetime).total_seconds() / 3600
                        print(f"Giờ làm việc đã tính: {working_hours:.2f} giờ")

                    except Exception as time_calc_error:
                        print(f"Lỗi khi tính giờ làm việc: {time_calc_error}")
                        working_hours = None

                    # Đảm bảo self.determine_status tồn tại và hoạt động đúng cách
                    # Hoặc thay thế bằng logic trực tiếp ở đây
                    final_status = self.determine_status(existing_session[1], current_time_str)

                    update_sql = """
                                 UPDATE WorkSessions
                                 SET CheckOut     = ?,
                                     WorkingHours = ?,
                                     Status       = ?
                                 WHERE SessionID = ?
                                 """
                    self.cursor.execute(update_sql,
                                        (current_time_str, working_hours, final_status, existing_session[0]))
                    print(f"Đã cập nhật CheckOut, WorkingHours và Status cho nhân viên {employee_id}")

                else:
                    print(f"❌ LỖI: Không thể Check Out khi chưa Check In cho nhân viên {employee_id}")
                    self.conn.rollback()
                    return False

            self.conn.commit()

            if self.cursor.rowcount > 0:
                print(f"Chấm công thành công cho {employee_id}")
                return True
            else:
                print(f"Không có hàng nào bị ảnh hưởng khi chấm công cho {employee_id}")
                return False

        except Exception as e:
            print(f"Lỗi cơ sở dữ liệu khi chấm công cho {employee_id}: {e}")
            # THAY ĐỔI TẠI ĐÂY: In ra toàn bộ traceback
            traceback.print_exc()  # Dòng này sẽ in ra chi tiết lỗi

            try:
                self.conn.rollback()
            except Exception as rb_e:
                print(f"Lỗi trong quá trình rollback: {rb_e}")
                traceback.print_exc()  # In traceback cho lỗi rollback nếu có

            return False

    def get_attendance_logs(self):
        try:
            sql = """
                  SELECT ws.SessionID                                                                         as LogID,
                         ws.EmployeeID,
                         e.FullName,
                         ws.WorkDate,
                         ws.CheckIn,
                         ws.CheckOut,

                         CASE
                             WHEN ws.WorkingHours > 0 THEN CAST(ws.WorkingHours AS DECIMAL(5, 2))
                             ELSE 0 END                                                                       as TotalHours,
                         ws.Status,
                         ws.Note
                  FROM WorkSessions ws
                           LEFT JOIN Employees e ON ws.EmployeeID = e.EmployeeID
                  ORDER BY ws.WorkDate DESC, ws.CheckIn DESC
                  """

            self.cursor.execute(sql)
            results = self.cursor.fetchall()

            formatted_results = []
            for row in results:
                log_id, emp_id, full_name, work_date, check_in, check_out, total_hours, status , note = row

                if isinstance(work_date, str):
                    try:
                        date_obj = datetime.strptime(work_date, '%Y-%m-%d')
                        formatted_date = date_obj.strftime('%d/%m/%Y')
                    except:
                        formatted_date = work_date
                else:
                    formatted_date = work_date.strftime('%d/%m/%Y') if work_date else 'N/A'

                check_in_display = check_in if check_in else 'Chưa check in'
                check_out_display = check_out if check_out else 'Chưa check out'
                hours_display = f"{total_hours:.2f}h" if total_hours and total_hours > 0 else "0h"

                formatted_results.append((
                    log_id,
                    emp_id,
                    full_name or 'Unknown',
                    formatted_date,
                    check_in_display,
                    check_out_display,
                    hours_display,
                    status,
                    note
                ))

            return formatted_results

        except Exception as e:
            print(f"Error getting attendance logs: {e}")
            return []

    def delete_attendance_log(self, log_id):
        """
        Delete attendance record from WorkSessions table
        """
        try:
            sql = "DELETE FROM WorkSessions WHERE SessionID = ?"
            self.cursor.execute(sql, (log_id,))
            self.conn.commit()

            if self.cursor.rowcount > 0:
                print(f"Attendance record deleted successfully: SessionID {log_id}")
                return True
            else:
                print(f"No record found with SessionID: {log_id}")
                return False

        except Exception as e:
            print(f"Error deleting attendance log {log_id}: {e}")
            try:
                self.conn.rollback()
            except:
                pass
            return False

    def update_attendance_log(self, session_id, work_date, check_in, check_out=None, working_hours=0, note=None):
        """Update attendance log in database"""
        try:
            cursor = self.conn.cursor()

            # Tính toán Status dựa trên thời gian check-in và check-out
            if check_out:
                # Tính toán working hours nếu có check_out
                try:
                    def parse_sql_time(time_str):
                        if isinstance(time_str, str):
                            clean_time = time_str.split('.')[0]
                            return datetime.strptime(clean_time, '%H:%M:%S').time()
                        else:
                            return time_str

                    checkin_time = parse_sql_time(check_in)
                    checkout_time = parse_sql_time(check_out)

                    today_date = datetime.strptime(work_date, '%Y-%m-%d').date()
                    checkin_datetime = datetime.combine(today_date, checkin_time)
                    checkout_datetime = datetime.combine(today_date, checkout_time)

                    if checkout_datetime < checkin_datetime:
                        checkout_datetime += timedelta(days=1)

                    calculated_working_hours = (checkout_datetime - checkin_datetime).total_seconds() / 3600

                    # Sử dụng working_hours đã tính toán nếu không được truyền vào
                    if working_hours == 0:
                        working_hours = calculated_working_hours

                except Exception as time_calc_error:
                    print(f"Lỗi khi tính giờ làm việc: {time_calc_error}")

                # Tính Status dựa trên thời gian check-in và check-out
                final_status = self.determine_status(check_in, check_out)

                sql = """
                      UPDATE WorkSessions
                      SET WorkDate     = ?,
                          CheckIn      = ?,
                          CheckOut     = ?,
                          WorkingHours = ?,
                          Status       = ?,
                          Note         = ?
                      WHERE SessionID = ?
                      """
                cursor.execute(sql, (work_date, check_in, check_out, working_hours, final_status, note, session_id))
            else:
                # Chỉ có check-in, tính Status dựa trên thời gian check-in
                checkin_time = datetime.strptime(check_in, '%H:%M:%S').time()
                temp_status = 'Đi trễ' if checkin_time > time(7, 30) else 'Đúng giờ'

                sql = """
                      UPDATE WorkSessions
                      SET WorkDate     = ?,
                          CheckIn      = ?,
                          CheckOut     = NULL,
                          WorkingHours = 0,
                          Status       = ?,
                          Note         = ?
                      WHERE SessionID = ?
                      """
                cursor.execute(sql, (work_date, check_in, temp_status, note, session_id))

            self.conn.commit()
            print(f"✅ Updated attendance record for SessionID: {session_id}")
            return True

        except Exception as e:
            print(f"Lỗi khi cập nhật attendance log: {e}")
            try:
                self.conn.rollback()
            except Exception as rb_e:
                print(f"Lỗi trong quá trình rollback: {rb_e}")
            return False
    def get_attendance_logs_by_employee(self, employee_id, from_date, to_date):
        try:
            query = """
                    SELECT SessionID,
                           EmployeeID,
                           WorkDate,
                           CheckIn,
                           CheckOut,
                           WorkingHours,
                           CreatedAt,
                           Status
                    FROM WorkSessions
                    WHERE EmployeeID = ?
                      AND CONVERT(DATE, WorkDate) BETWEEN ? AND ?
                    ORDER BY WorkDate
                    """

            self.cursor.execute(query, (employee_id, from_date, to_date))
            rows = self.cursor.fetchall()

            # Xử lý dữ liệu để đảm bảo format đúng
            processed_rows = []
            for row in rows:
                session_id = row[0]
                employee_id = row[1]
                work_date = row[2]
                check_in = row[3]
                check_out = row[4]
                working_hours = row[5]
                created_at = row[6]
                status = row[7]

                # Chuyển đổi WorkDate thành string format YYYY-MM-DD nếu cần
                if hasattr(work_date, 'strftime'):
                    work_date_str = work_date.strftime('%Y-%m-%d')
                else:
                    work_date_str = str(work_date)

                # Chuyển đổi thời gian CheckIn và CheckOut thành string format HH:MM:SS
                check_in_str = ""
                check_out_str = ""

                if check_in:
                    if hasattr(check_in, 'strftime'):
                        check_in_str = check_in.strftime('%H:%M:%S')
                    else:
                        check_in_str = str(check_in)

                if check_out:
                    if hasattr(check_out, 'strftime'):
                        check_out_str = check_out.strftime('%H:%M:%S')
                    else:
                        check_out_str = str(check_out)

                processed_row = (
                    session_id,
                    employee_id,
                    work_date,
                    work_date_str,  # Thêm work_date_str vào vị trí index 3
                    check_in_str,  # index 4
                    check_out_str,  # index 5
                    working_hours,  # index 6
                    status  # index 7
                )
                processed_rows.append(processed_row)

            return processed_rows

        except Exception as e:
            print(f"Lỗi truy vấn dữ liệu: {e}")
            return []