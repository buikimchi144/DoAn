import cv2
import time
import os
from PyQt5.QtCore import QThread, pyqtSignal
import numpy as np
from collections import deque
import threading
from collections import defaultdict
# Setup logging
import logging
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class Camera:
    def __init__(self, camera_id=0):
        self.cap = cv2.VideoCapture(camera_id)
        if not self.cap.isOpened():
            raise RuntimeError("Không mở được webcam")

        # Tối ưu settings cho chất lượng tốt hơn
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        self.cap.set(cv2.CAP_PROP_BRIGHTNESS, 0.6)
        self.cap.set(cv2.CAP_PROP_CONTRAST, 0.6)

    def capture_for_duration(self, seconds=5, save_dir="captured_frames", max_fps=10):
        os.makedirs(save_dir, exist_ok=True)
        start_time = time.time()
        frame_count = 0
        last_save_time = 0
        frame_interval = 1.0 / max_fps

        while time.time() - start_time < seconds:
            ret, frame = self.cap.read()
            if not ret:
                break

            current_time = time.time()
            if current_time - last_save_time >= frame_interval:
                filename = os.path.join(save_dir, f"frame_{frame_count:04d}.jpg")
                threading.Thread(
                    target=lambda f=frame.copy(), fn=filename: cv2.imwrite(fn, f),
                    daemon=True
                ).start()
                frame_count += 1
                last_save_time = current_time

            time.sleep(0.001)

        return frame_count

    def get_frame(self):
        ret, frame = self.cap.read()
        if ret:
            frame = self._enhance_frame_quality(frame)
            return frame
        return None

    def _enhance_frame_quality(self, frame):
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        frame = cv2.filter2D(frame, -1, kernel)
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        enhanced = cv2.merge([l, a, b])
        frame = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
        return frame

    def is_opened(self):
        return self.cap.isOpened()

    def release(self):
        if self.cap.isOpened():
            self.cap.release()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class WebcamThread(QThread):
    frame_processed = pyqtSignal(np.ndarray)
    attendance_logged = pyqtSignal(str, object, object)
    multiple_attendance_logged = pyqtSignal(list)
    face_detected = pyqtSignal(int)

    def __init__(self, face_recog, db, check_type, camera_id=0):
        super().__init__()
        self.face_recog = face_recog
        self.db = db
        self.camera_id = camera_id
        self.check_type = check_type
        self._running = True

        self.frame_count = 0
        self.fps_counter = 0
        self.fps_time = time.time()
        self.current_fps = 0

        self.cached_encodings = {}
        self.cache_time = 0
        self.cache_update_interval = 30

        self.max_concurrent_faces = 5
        self.recognition_interval = 0.1
        self.last_recognition_time = 0

        self.confidence_threshold = 0.6
        self.high_confidence = 0.7

        self.min_face_size = 30
        self.max_face_size = 400

        self.person_trackers = {}
        self.attendance_cooldowns = {}
        self.attendance_cooldown_time = 2.0

        self.current_recognitions = {}

        self.person_history = defaultdict(lambda: deque(maxlen=5))
        self.person_confidence_buffer = defaultdict(lambda: deque(maxlen=3))

        # --- BẮT ĐẦU SỬA ĐỔI: Thêm các bộ font chữ với kích thước khác nhau ---
        try:
            # Bạn có thể dùng file font bold (vd: arialbd.ttf) để có hiệu ứng đẹp hơn
            font_path = "arial.ttf"
            # Font tiêu chuẩn
            self.font_main = ImageFont.truetype(font_path, 18)
            self.font_status = ImageFont.truetype(font_path, 14)
            # Font nổi bật - BỰ VÀ RÕ HƠN
            self.font_main_highlight = ImageFont.truetype(font_path, 24)
            self.font_status_highlight = ImageFont.truetype(font_path, 20)

            logger.info(f"✅ Đã tải các bộ font chữ từ: {font_path}")
        except IOError:
            logger.error(f"❌ Không tìm thấy file font: {font_path}. Chữ tiếng Việt có thể bị lỗi.")
            self.font_main = None
            self.font_status = None
            self.font_main_highlight = None
            self.font_status_highlight = None
        # --- KẾT THÚC SỬA ĐỔI ---

    def run(self):
        cam = self._setup_camera()
        if not cam:
            return

        logger.info("🔥 Multi-person webcam thread started")

        while self._running:
            ret, frame = cam.read()
            if not ret:
                continue

            self.frame_count += 1
            self._update_fps()

            current_time = time.time()

            if current_time - self.last_recognition_time >= self.recognition_interval:
                self._perform_multi_person_recognition(frame, current_time)
                self.last_recognition_time = current_time

            display_frame = self._draw_multi_person_interface(frame)
            self.frame_processed.emit(display_frame)

        cam.release()
        logger.info("🔥 Multi-person webcam stopped")

    def _setup_camera(self):
        cam = cv2.VideoCapture(self.camera_id)
        if not cam.isOpened():
            self.attendance_logged.emit("❌ Không mở được webcam.", None, None)
            return None
        cam.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cam.set(cv2.CAP_PROP_FPS, 30)
        cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        return cam

    def _update_fps(self):
        self.fps_counter += 1
        current_time = time.time()
        if current_time - self.fps_time >= 1.0:
            self.current_fps = self.fps_counter
            self.fps_counter = 0
            self.fps_time = current_time

    def _perform_multi_person_recognition(self, frame, current_time):
        if current_time - self.cache_time > self.cache_update_interval:
            self._update_cache()

        faces = self._detect_multiple_faces(frame)
        if not faces:
            self.face_detected.emit(0)
            self.current_recognitions.clear()
            return

        self.face_detected.emit(len(faces))

        new_recognitions = {}
        attendance_batch = []

        for face_idx, face in enumerate(faces[:self.max_concurrent_faces]):
            recognition_result = self._recognize_single_face(frame, face, face_idx)

            if recognition_result:
                emp_id, similarity, bbox, face_img = recognition_result
                emp_info = self.db.employees.get_employee_info(emp_id)

                if emp_info:
                    new_recognitions[face_idx] = {
                        'emp_id': emp_id, 'name': emp_info[1], 'similarity': similarity,
                        'bbox': bbox, 'face_img': face_img, 'emp_info': emp_info, 'is_unknown': False
                    }
                    if self._should_process_attendance(emp_id, similarity, current_time):
                        attendance_info = self._process_individual_attendance(
                            emp_id, similarity, face_img, emp_info, current_time)
                        if attendance_info:
                            attendance_batch.append(attendance_info)
            else:
                try:
                    x1, y1, x2, y2 = [int(i) for i in face.bbox]
                    h, w, _ = frame.shape
                    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
                    if x2 > x1 and y2 > y1:
                        face_img = frame[y1:y2, x1:x2].copy()
                        if face_img.size > 0:
                            new_recognitions[face_idx] = {
                                'emp_id': None, 'name': 'Chưa đăng ký', 'similarity': 0.0,
                                'bbox': face.bbox, 'face_img': face_img, 'emp_info': None, 'is_unknown': True
                            }
                except Exception as e:
                    logger.error(f"Error processing unknown face {face_idx}: {e}")

        self.current_recognitions = new_recognitions
        if attendance_batch:
            self.multiple_attendance_logged.emit(attendance_batch)
            for att_info in attendance_batch:
                self.attendance_logged.emit(
                    att_info['message'], att_info['emp_info'], att_info['face_img'])

    def _detect_multiple_faces(self, frame):
        try:
            faces = self.face_recog.face_app.get(frame)
            if not faces: return []

            valid_faces = []
            for face in faces:
                bbox = face.bbox
                width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
                if self.min_face_size <= width <= self.max_face_size and self.min_face_size <= height <= self.max_face_size:
                    valid_faces.append(face)

            valid_faces.sort(key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
            return valid_faces[:self.max_concurrent_faces]
        except Exception as e:
            logger.error(f"Multi-face detection error: {e}")
            return []

    def _recognize_single_face(self, frame, face, face_idx):
        try:
            embedding = face.normed_embedding.tolist() if hasattr(face,
                                                                  'normed_embedding') and face.normed_embedding is not None else (
                face.embedding.tolist() if hasattr(face, 'embedding') and face.embedding is not None else None)
            if embedding is None:
                logger.warning(f"Face {face_idx}: No valid embedding found.")
                return None
            if not self.cached_encodings:
                return None

            best_match, best_similarity = None, 0
            for emp_id, known_emb in self.cached_encodings.items():
                match, similarity = self.face_recog.compare_faces(embedding, known_emb)
                if match and similarity >= self.confidence_threshold and similarity > best_similarity:
                    best_similarity, best_match = similarity, emp_id

            if best_match:
                x1, y1, x2, y2 = [int(i) for i in face.bbox]
                h, w, _ = frame.shape
                x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
                if x2 <= x1 or y2 <= y1: return None
                face_img = frame[y1:y2, x1:x2].copy()
                if face_img.size == 0: return None
                return best_match, best_similarity, face.bbox, face_img
            return None
        except Exception as e:
            logger.error(f"Single face recognition error: {e}", exc_info=True)
            return None

    def _should_process_attendance(self, emp_id, similarity, current_time):
        if similarity >= self.high_confidence: return True
        if emp_id in self.attendance_cooldowns and current_time - self.attendance_cooldowns[
            emp_id] < self.attendance_cooldown_time:
            return False
        self.person_confidence_buffer[emp_id].append(similarity)
        if len(self.person_confidence_buffer[emp_id]) >= 3:
            return np.mean(list(self.person_confidence_buffer[emp_id])) >= self.confidence_threshold
        return False

    def _process_individual_attendance(self, emp_id, similarity, face_img, emp_info, current_time):
        try:
            success = self.db.attendance.log_attendance(emp_id, self.check_type, face_img, similarity)
            if success:
                self.attendance_cooldowns[emp_id] = current_time
                self.person_confidence_buffer[emp_id].clear()
                action = "Vào" if self.check_type == 'Check In' else "Ra"
                message = f"✅ {action}: {emp_info[1]} - {similarity:.0%}"
                logger.info(f"🔥 Multi-person attendance: {emp_id} - {similarity:.3f} - {self.check_type}")
                return {'emp_id': emp_id, 'message': message, 'emp_info': emp_info, 'face_img': face_img,
                        'similarity': similarity, 'timestamp': current_time, 'check_type': self.check_type}
            else:
                return {'emp_id': emp_id, 'message': f"❌ Lỗi: {emp_info[1]}", 'emp_info': None,
                        'face_img': None, 'similarity': similarity, 'timestamp': current_time}
        except Exception as e:
            logger.error(f"Individual attendance error: {e}")
            return None

    # --- BẮT ĐẦU SỬA ĐỔI LỚN: HÀM VẼ GIAO DIỆN ---
    def _draw_multi_person_interface(self, frame):
        pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)

        for face_idx, recognition in self.current_recognitions.items():
            bbox = recognition['bbox']
            is_unknown = recognition['is_unknown']
            x1, y1, x2, y2 = [int(i) for i in bbox]

            h, w, _ = frame.shape
            x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
            if x1 >= x2 or y1 >= y2: continue

            # --- SỬA ĐỔI: Chọn font chữ động để làm nổi bật ---
            # Mặc định dùng font tiêu chuẩn
            main_font_to_use = self.font_main
            status_font_to_use = self.font_status

            if is_unknown:
                color = (255, 0, 0)
                main_text = "Chưa đăng ký"
                status = "Chưa đăng ký"
                # Dùng font to, đậm cho người lạ
                main_font_to_use = self.font_main_highlight
                status_font_to_use = self.font_status_highlight
            else:
                name = recognition['name']
                similarity = recognition['similarity']
                main_text = f"{name} ({similarity:.0%})"

                if similarity >= self.high_confidence:
                    color = (0, 255, 0)
                    status = "ĐÃ XÁC NHẬN"
                    # Dùng font to, đậm cho cả tên và trạng thái khi đã xác nhận
                    main_font_to_use = self.font_main_highlight
                    status_font_to_use = self.font_status_highlight
                elif similarity >= self.confidence_threshold:
                    color = (255, 165, 0)
                    status = "ĐANG XỬ LÝ"
                    # Giữ font thường cho trạng thái đang xử lý
                else:
                    color = (255, 0, 0)
                    status = "KHÔNG CHẮC CHẮN"
                    # Giữ font thường cho trạng thái không chắc chắn
            # --- KẾT THÚC SỬA ĐỔI ---

            draw.rectangle([x1, y1, x2, y2], outline=color, width=3)

            # --- Vẽ chữ bằng PIL với font đã được chọn ---
            if all([self.font_main, self.font_status, self.font_main_highlight, self.font_status_highlight]):
                # Vẽ text chính (tên hoặc "Chưa đăng ký")
                text_y = y1 - 10 if y1 > 40 else y2 + 30 # Tăng khoảng cách để không bị đè
                left, top, right, bottom = draw.textbbox((x1, text_y), main_text, font=main_font_to_use)
                draw.rectangle((left - 5, top - 5, right + 5, bottom + 5), fill=color)
                draw.text((x1 + 5, top - 5), main_text, font=main_font_to_use, fill=(255, 255, 255))

                # Vẽ text trạng thái
                status_y = y2 + 5 # Đặt vị trí status ngay dưới bounding box
                left, top, right, bottom = draw.textbbox((x1, status_y), status, font=status_font_to_use)
                draw.rectangle((left - 3, top - 2, right + 3, bottom + 2), fill=color)
                draw.text((x1 + 3, top - 2), status, font=status_font_to_use, fill=(255, 255, 255))
            else:
                cv2.rectangle(frame, (x1, y1 - 20), (x2, y1), color, -1)
                cv2.putText(frame, "Font error", (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

        # Vẽ thông tin hệ thống
        num_detected_faces = len(self.face_recog.last_frame_faces or [])
        cv2.rectangle(frame, (5, 5), (250, 120), (0, 0, 0), -1)
        cv2.putText(frame, f"FPS: {self.current_fps}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
        cv2.putText(frame, f"Detected: {num_detected_faces}", (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(frame, f"Recognized: {len([r for r in self.current_recognitions.values() if not r['is_unknown']])}", (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        cv2.putText(frame, f"Unknown: {len([r for r in self.current_recognitions.values() if r['is_unknown']])}", (10, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        cv2.putText(frame, "🔥 MULTI-PERSON MODE", (10, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 255), 1)

        return frame
    # --- KẾT THÚC SỬA ĐỔI LỚN ---

    def _update_cache(self):
        try:
            self.cached_encodings = self.db.employees.get_all_encodings()
            self.cache_time = time.time()
            logger.info(f"🔥 Cache updated: {len(self.cached_encodings)} faces")
        except Exception as e:
            logger.error(f"Cache error: {e}")

    def stop(self):
        logger.info("🔥 Stopping multi-person thread...")
        self._running = False
        self.wait(3000)
        if self.isRunning():
            self.terminate()

    def update_check_type(self, check_type):
        self.check_type = check_type

    def clear_cache(self):
        self.cached_encodings.clear()
        self.cache_time = 0
        self.attendance_cooldowns.clear()
        self.current_recognitions.clear()
        self.person_confidence_buffer.clear()
        self.person_history.clear()
        logger.info("🔥 All caches cleared")

    def set_multi_person_mode(self, max_faces=5, cooldown=2.0):
        self.max_concurrent_faces = max_faces
        self.attendance_cooldown_time = cooldown
        logger.info(f"🔥 Multi-person mode: {max_faces} faces, {cooldown}s cooldown")

    def get_statistics(self):
        return {
            'total_frames': self.frame_count, 'current_fps': self.current_fps,
            'cached_faces': len(self.cached_encodings), 'current_recognitions': len(self.current_recognitions),
            'active_cooldowns': len(self.attendance_cooldowns), 'max_concurrent_faces': self.max_concurrent_faces,
            'mode': 'multi_person_fast'
        }

    def get_current_recognitions(self):
        return dict(self.current_recognitions)