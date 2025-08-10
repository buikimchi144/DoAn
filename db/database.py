import pyodbc
import logging
from .employee_operations import EmployeeOperations
from .attendance_operations import AttendanceOperations
import hashlib


class Database:
    def __init__(self):
        try:
            self.conn = pyodbc.connect(
                'DRIVER={SQL Server};SERVER=KIMCHI;DATABASE=FaceAttendanceDB1;UID=Sinhvien;PWD=123456'
            )
            self.cursor = self.conn.cursor()
            logging.info("Database connection established successfully.")

            # Instantiate operation classes, passing the connection and cursor
            self.employees = EmployeeOperations(self.conn, self.cursor)
            self.attendance = AttendanceOperations(self.conn, self.cursor)

        except pyodbc.Error as ex:
            sqlstate = ex.args[0]
            if sqlstate == '28000':
                logging.error("Authentication error: Invalid UID or PWD.")
            else:
                logging.error(f"Database connection error: {ex}")
            raise # Re-raise the exception to indicate connection failure
        except Exception as e:
            logging.error(f"An unexpected error occurred during database initialization: {e}")
            raise

    def authenticate_user(self, username, password):
        """Authenticate user against database"""
        try:
            # Băm mật khẩu đầu vào
            password_hash = hashlib.sha256(password.encode()).hexdigest()

            # Tạo cursor từ kết nối
            cursor = self.conn.cursor()

            query = """
                SELECT u.UserID, u.Username, u.Role, u.EmployeeID, e.FullName, e.Department,e.Position,e.JoinDate
                FROM Users u
                LEFT JOIN Employees e ON u.EmployeeID = e.EmployeeID
                WHERE u.Username = ?
                  AND u.Password_Hash = ?
            """

            # Thực thi câu truy vấn với tham số
            cursor.execute(query, (username, password_hash))

            # Lấy 1 dòng kết quả
            result = cursor.fetchone()

            # Đóng cursor
            cursor.close()

            if result:
                # Gán thông tin user cho thuộc tính current_user
                self.current_user = {
                    'id': result[0],
                    'username': result[1],
                    'role': result[2],
                    'employee_id': result[3],
                    'full_name': result[4] if result[4] else username,
                    'department': result[5],
                    'position': result[6],
                    'join_date': result[7],
                }
                return True

            # Nếu không có kết quả (username hoặc mật khẩu sai)
            return False

        except Exception as e:
            print(f"Authentication error: {e}")
            return False

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            logging.info("Database connection closed.")