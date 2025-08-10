import pyodbc
import logging
import hashlib
import cv2
import os

class EmployeeOperations:
    def __init__(self, conn, cursor):
        self.conn = conn
        self.cursor = cursor

    def get_all_employees(self):
        """Get all employee details including user role."""
        try:
            self.cursor.execute("""
                SELECT e.[EmployeeID],
                       e.[FullName],
                       e.[Department],
                       e.[Gender],
                       e.[Position],
                       e.[DateOfBirth],
                       e.[JoinDate],
                       CASE 
                           WHEN LOWER(u.[Role]) = 'admin' THEN 'Admin'
                           WHEN LOWER(u.[Role]) = 'user' THEN N'Nhân viên'
                           ELSE u.[Role]
                       END AS [Quyền]
                FROM Employees e
                LEFT JOIN Users u ON e.EmployeeID = u.EmployeeID
            """)
            return self.cursor.fetchall()
        except Exception as e:
            logging.error(f"Error getting all employees: {e}")
            return []

    def get_employee_face_image(self, employee_id):
        """Lấy ảnh đại diện của employee"""
        try:
            cursor = self.conn.cursor()
            query = "SELECT face_image FROM employees WHERE employee_id = ?"
            cursor.execute(query, employee_id)
            result = cursor.fetchone()

            if result and result[0]:
                return result[0]  # Trả về bytes data của ảnh
            return None

        except pyodbc.Error as e:
            print(f"Database error in get_employee_face_image: {e}")
            return None
        except Exception as e:
            print(f"Error in get_employee_face_image: {e}")
            return None
        finally:
            if cursor:
                cursor.close()

    def update_employee_face_image(self, employee_id: int, face_img_bytes):
        """Cập nhật ảnh đại diện của employee"""
        try:
            cursor = self.conn.cursor()
            query = "UPDATE employees SET face_image = ? WHERE employee_id = ?"
            cursor.execute(query, face_img_bytes, employee_id)
            self.conn.commit()

            # Kiểm tra xem có row nào được update không
            if cursor.rowcount > 0:
                print(f"Successfully updated face image for employee_id: {employee_id}")
                return True
            else:
                print(f"No employee found with employee_id: {employee_id}")
                return False

        except pyodbc.Error as e:
            print(f"Database error in update_employee_face_image: {e}")
            self.conn.rollback()
            return False
        except Exception as e:
            print(f"Error in update_employee_face_image: {e}")
            return False
        finally:
            if cursor:
                cursor.close()

    def update_employee_encoding(self, employee_id, encoding_str):
        """Cập nhật face encoding của employee"""
        try:
            cursor = self.conn.cursor()
            query = "UPDATE employees SET face_encoding = ? WHERE employee_id = ?"
            cursor.execute(query, encoding_str, employee_id)
            self.conn.commit()

            # Kiểm tra xem có row nào được update không
            if cursor.rowcount > 0:
                print(f"Successfully updated face encoding for employee_id: {employee_id}")
                return True
            else:
                print(f"No employee found with employee_id: {employee_id}")
                return False

        except pyodbc.Error as e:
            print(f"Database error in update_employee_encoding: {e}")
            self.conn.rollback()
            return False
        except Exception as e:
            print(f"Error in update_employee_encoding: {e}")
            return False
        finally:
            if cursor:
                cursor.close()

    def add_employee(self, full_name, department, gender, position, dob, join_date, face_img=None):
        """Add a new employee to the Employees table."""
        try:
            query = """
                    INSERT INTO Employees (FullName, Department, Gender, Position, DateOfBirth, JoinDate, CreatedAt,
                                           FaceImg)
                        OUTPUT INSERTED.EmployeeID
                    VALUES (?, ?, ?, ?, ?, ?, GETDATE(), ?)
                    """
            self.cursor.execute(query, (full_name, department, gender, position, dob, join_date, face_img))
            emp_id = self.cursor.fetchone()[0]
            self.conn.commit()
            print(f"[✔] Đã thêm nhân viên: {emp_id} - {full_name}")
            return emp_id

        except Exception as e:
            print("[❌] Lỗi khi thêm nhân viên:", e)
            self.conn.rollback()
            return None

    def add_user(self, username, password, role, employee_id):
        """Add new user to Users table, hashing the password before saving"""
        try:
            # Mã hóa mật khẩu trước khi lưu vào DB
            password_hash = hashlib.sha256(password.encode()).hexdigest()

            cursor = self.conn.cursor()
            query = """
                    INSERT INTO Users (Username, Password_Hash, Role, EmployeeID, Created_At)
                    VALUES (?, ?, ?, ?, GETDATE())
                    """
            cursor.execute(query, (username, password_hash, role, employee_id))
            self.conn.commit()
            cursor.close()
            print(f"User {username} added successfully")

        except Exception as e:
            print(f"Error adding user: {e}")
            raise e

    def delete_employee(self, employee_id):
        """Xóa nhân viên theo EmployeeID"""
        cursor = None
        try:
            cursor = self.conn.cursor()

            # Kiểm tra xem nhân viên có tồn tại không
            cursor.execute("SELECT COUNT(*) FROM Employees WHERE EmployeeID = ?", (employee_id,))
            count = cursor.fetchone()[0]

            if count == 0:
                raise Exception(f"Không tìm thấy nhân viên với ID: {employee_id}")

            # Xóa các bản ghi liên quan trước (nếu có)
            cursor.execute("DELETE FROM WorkSessions WHERE EmployeeID = ?", (employee_id,))
            cursor.execute("DELETE FROM AttendanceLogs WHERE EmployeeID = ?", (employee_id,))
            cursor.execute("DELETE FROM FaceEncodings WHERE EmployeeID = ?", (employee_id,))
            # Xóa nhân viên
            cursor.execute("DELETE FROM Employees WHERE EmployeeID = ?", (employee_id,))

            # Commit transaction
            self.conn.commit()

            logging.info(f"Đã xóa nhân viên với ID: {employee_id}")
            return True

        except Exception as e:
            # Rollback nếu có lỗi
            if self.conn:
                self.conn.rollback()
            logging.error(f"Lỗi khi xóa nhân viên: {str(e)}")
            raise e
        finally:
            # Đóng cursor nếu đã tạo
            if cursor:
                cursor.close()

    def add_encoding(self, emp_id, encoding_str):
        """
        Lưu mã hóa khuôn mặt (face embedding) dưới dạng chuỗi vào bảng FaceEncodings.

        Args:
            emp_id (str): Mã nhân viên.
            encoding_str (str): Chuỗi encoding, ví dụ '0.123,0.456,...'
        """
        try:
            query = """
                    INSERT INTO FaceEncodings (EmployeeID, Encoding, CreatedAt)
                    VALUES (?, ?, GETDATE())
                    """
            self.cursor.execute(query, (emp_id, encoding_str))
            self.conn.commit()

        except Exception as e:
            logging.error(f"[Lỗi add_encoding] emp_id={emp_id}, error: {e}")

    def get_all_encodings(self):
        """Return all encodings as a dict: {EmployeeID: encoding_list}"""
        print("Step 1: Executing query to fetch EmployeeID and Encoding from database")
        self.cursor.execute("SELECT EmployeeID, Encoding FROM FaceEncodings")

        print("Step 2: Fetching all results from the database")
        results = self.cursor.fetchall()
        print(f"Number of records fetched: {len(results)}")

        encodings = {}
        for i, (emp_id, encoding_str) in enumerate(results, 1):
            print(f"Step 3.{i}: Processing EmployeeID = {emp_id}")
            print(f" - Original encoding string: {encoding_str}")

            try:
                # Chuyển chuỗi encoding thành danh sách số float
                parts = encoding_str.split(',')
                encoding = []
                for x in parts:
                    x = x.strip()
                    try:
                        encoding.append(float(x))
                    except ValueError:
                        print(f"  ⚠️ Bỏ qua giá trị không hợp lệ: '{x}'")

                # Lưu kết quả nếu danh sách đủ độ dài (512 chiều)
                if len(encoding) == 512:
                    encodings[emp_id] = encoding
                    print(f" - Converted encoding (first 5 values): {encoding[:5]}... ✅")
                else:
                    print(f"  ⚠️ Bỏ qua vì độ dài encoding không đúng (length = {len(encoding)})")

            except Exception as e:
                print(f" [Lỗi khi xử lý encoding cho EmployeeID={emp_id}]: {e}")

        print("Step 4: Returning the complete encodings dictionary")
        return encodings

    def get_employee_info(self, emp_id):
        """Lấy thông tin nhân viên theo ID"""
        self.cursor.execute("SELECT * FROM Employees WHERE EmployeeID = ?", emp_id)
        return self.cursor.fetchone()

    def update_employee(self, employee_id, full_name, department, gender, position, dob, join_date, role):
        """Cập nhật thông tin nhân viên và vai trò"""
        try:
            print(f"employee_id: {employee_id}")
            print(f"full_name: {full_name}")
            print(f"department: {department}")
            print(f"gender: {gender}")
            print(f"position: {position}")
            print(f"dob: {dob}")
            print(f"join_date: {join_date}")
            print(f"role: {role}")

            cursor = self.conn.cursor()

            # Cập nhật thông tin nhân viên trong bảng Employees
            cursor.execute("""
                           UPDATE Employees
                           SET FullName    = ?,
                               Department  = ?,
                               Gender      = ?,
                               Position    = ?,
                               DateOfBirth = ?,
                               JoinDate    = ?
                           WHERE EmployeeID = ?
                           """, (full_name, department, gender, position, dob, join_date, employee_id))

            # Xác định mật khẩu theo role và mã hóa bằng sha256
            if role.lower() == "user":
                raw_password = "456"
            elif role.lower() == "admin":
                raw_password = "123"
            else:
                raw_password = None  # Nếu role khác thì không thay đổi mật khẩu

            if raw_password is not None:
                hashed_password = hashlib.sha256(raw_password.encode()).hexdigest()
                cursor.execute("""
                               UPDATE Users
                               SET Role          = ?,
                                   Password_Hash = ?
                               WHERE EmployeeID = ?
                               """, (role, hashed_password, employee_id))
            else:
                cursor.execute("""
                               UPDATE Users
                               SET Role = ?
                               WHERE EmployeeID = ?
                               """, (role, employee_id))

            self.conn.commit()

        except Exception as e:
            self.conn.rollback()
            logging.error(f"Lỗi cập nhật nhân viên hoặc vai trò: {e}")
            raise e

    def update_face_encoding(self, employee_id, encoding_str):
        """Cập nhật face encoding của nhân viên"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE FaceEncodings
                SET Encoding = ?
                WHERE EmployeeID = ?
            """, (encoding_str, employee_id))
            self.conn.commit()
            print(f"Updated face encoding for employee {employee_id}")
        except Exception as e:
            print(f"Error updating face encoding: {e}")
            raise e

    def update_employee_face_image(self, employee_id, face_img_bytes):
        """Cập nhật ảnh khuôn mặt của nhân viên"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE Employees
                SET FaceImg = ?
                WHERE EmployeeID = ?
            """, (face_img_bytes, employee_id))
            self.conn.commit()
            print(f"Updated face image for employee {employee_id}")
        except Exception as e:
            print(f"Error updating face image: {e}")
            raise e

    def get_employee_face_image(self, employee_id):
        """Lấy ảnh khuôn mặt của nhân viên"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT FaceImg FROM Employees WHERE EmployeeID = ?", (employee_id,))
            result = cursor.fetchone()
            return result[0] if result and result[0] else None
        except Exception as e:
            print(f"Error getting employee face image: {e}")
            return None