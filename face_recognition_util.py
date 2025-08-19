import numpy as np
import cv2
from insightface.app import FaceAnalysis
import time
from collections import deque


class FaceRecognitionUtil:

    def __init__(self, det_size=(416, 416)):

        # Cấu hình tối ưu cho cả tốc độ và chính xác
        self.face_app = FaceAnalysis(
            name='buffalo_l',
            providers=['CPUExecutionProvider']
        )

        # Kích thước phát hiện tối ưu
        self.face_app.prepare(ctx_id=0, det_size=det_size)

        # Cache thông minh với tracking
        self.face_tracker = {}
        self.detection_history = deque(maxlen=5)
        self.last_frame_faces = []
        self.frame_cache_time = 0
        self.cache_duration = 0.033  # ~30 FPS

        # Tham số tối ưu cho chính xác và tốc độ - ĐIỀU CHỈNH
        self.min_face_area = 800  # Giảm để detect nhỏ hơn
        self.max_faces = 3  # Giảm để tăng tốc độ
        self.confidence_threshold = 0.6  # Threshold vừa phải

        # ROI adaptative để tăng tốc độ
        self.roi_enabled = False
        self.current_roi = None
        self.roi_expansion = 50

        # Frame enhancement - tối ưu
        self.clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))

        print("[INFO] FaceRecognitionUtil tối ưu - Chế độ cân bằng tốc độ và chính xác")

    # Phát hiện khuôn mặt tối ưu với validation và quality check
    def detect_face(self, frame):
        current_time = time.time()

        # Cải thiện chất lượng frame - tối ưu hóa
        enhanced_frame = self._enhance_frame(frame)

        # Sử dụng cache thông minh
        if (current_time - self.frame_cache_time < self.cache_duration and
                self.last_frame_faces and len(self.last_frame_faces) > 0):
            faces = self.last_frame_faces
        else:
            # Phát hiện khuôn mặt với kiểm tra
            faces = self._fast_face_detection(enhanced_frame)
            self.last_frame_faces = faces
            self.frame_cache_time = current_time

        if not faces:
            return None, None

        # Chọn khuôn mặt tốt nhất với scoring
        best_face = self._select_best_face(faces)

        # Cắt ảnh và trích xuất chính xác hơn
        aligned_face = self._get_aligned_face_crop(enhanced_frame, best_face)

        # Trích xuất Embedding và lưu vào biến
        embedding = self._get_fast_embedding(best_face)

        if embedding is None:
            return aligned_face, None

        return aligned_face, embedding

    # Cải thiệm chất lượng frame và tối ưu
    def _enhance_frame(self, frame):
        try:
            # Kiểm tra nhanh xem có cần enhance không
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            mean_brightness = np.mean(gray)

            # Chỉ enhance khi cần thiết
            if mean_brightness < 80 or mean_brightness > 180:
                # Chuyển sang LAB color space
                lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
                # Áp dụng CLAHE cho L channel
                lab[:, :, 0] = self.clahe.apply(lab[:, :, 0])
                # Chuyển về BGR
                enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
                return enhanced
            else:
                return frame
        except:
            return frame

    # Phát hiện và kiểm tra chất lượng
    def _fast_face_detection(self, frame):
        try:
            # ROI detection nếu enabled
            detection_frame = self._get_detection_region(frame)

            # Detection chính
            faces = self.face_app.get(detection_frame)

            if not faces:
                return []

            # Lọc khuôn mặt kém chất lượng
            validated_faces = []
            for face in faces[:self.max_faces]:
                if self._validate_face_quality_fast(face):
                    validated_faces.append(face)

            # Sắp xếp dựa trên điểm tổng hợp
            if len(validated_faces) > 1:
                validated_faces.sort(
                    key=lambda f: self._calculate_face_score(f),
                    reverse=True
                )
            return validated_faces

        except Exception as e:
            print(f"[ERROR] Detection failed: {e}")
            return []

    # Kiểm tra chất lượng khuôn mặt - tối ưu hóa
    def _validate_face_quality_fast(self, face):

        # 1. Confidence check nhanh
        confidence = getattr(face, 'det_score', 0.0)
        if confidence < self.confidence_threshold:
            return False

        # 2. Kiểm tra  kích thước
        bbox_area = (face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1])
        if bbox_area < self.min_face_area:
            return False

        # 3. Kiểm tra tỉ lệ khung hình
        width = face.bbox[2] - face.bbox[0]
        height = face.bbox[3] - face.bbox[1]
        if height > 0:
            aspect_ratio = width / height
            if not (0.6 <= aspect_ratio <= 1.6):  # Mở rộng range
                return False

        # 4. Bứớc kiểm tra nhanh biên bounding box
        if (face.bbox[0] < 0 or face.bbox[1] < 0 or
                face.bbox[2] < face.bbox[0] or face.bbox[3] < face.bbox[1]):
            return False

        return True

    #  Tính điểm tổng hợp cho khuôn mặt
    def _calculate_face_score(self, face):

        # Confidence score (60%) - tăng trọng số
        confidence = getattr(face, 'det_score', 0.0)
        confidence_score = confidence * 0.6

        # Kích thước khuôn mặt
        bbox_area = (face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1])
        max_reasonable_area = 120 * 120
        size_score = min(bbox_area / max_reasonable_area, 1.0) * 0.25

        # Tính tâm của khuôn mặt
        face_center_x = (face.bbox[0] + face.bbox[2]) / 2
        face_center_y = (face.bbox[1] + face.bbox[3]) / 2

        # Giả định tâm của khung hình
        frame_center_x, frame_center_y = 320, 240

        distance = np.sqrt((face_center_x - frame_center_x) ** 2 +
                           (face_center_y - frame_center_y) ** 2)
        max_distance = np.sqrt(320 ** 2 + 240 ** 2)
        position_score = (1.0 - distance / max_distance) * 0.15

        return confidence_score + size_score + position_score

    # Chọn khuôn mặt tốt nhất dựa trên composite scoring
    def _select_best_face(self, faces):

        if len(faces) == 1:
            return faces[0]

        best_face = faces[0]
        best_score = self._calculate_face_score(best_face)

        for face in faces[1:]:
            score = self._calculate_face_score(face)
            if score > best_score:
                best_score = score
                best_face = face

        return best_face

    # Crop khuôn mặt với alignment
    def _get_aligned_face_crop(self, frame, face):

        try:
            x1, y1, x2, y2 = map(int, face.bbox)

            # Tính toán margin nhỏ hơn để tăng tốc độ
            face_width = x2 - x1
            face_height = y2 - y1
            margin_x = int(face_width * 0.1)  # Giảm từ 15% xuống 10%
            margin_y = int(face_height * 0.1)

            # “Mở rộng bbox nhưng phải kiểm tra để không vượt mép ảnh
            h, w = frame.shape[:2]
            x1 = max(0, x1 - margin_x)
            y1 = max(0, y1 - margin_y)
            x2 = min(w, x2 + margin_x)
            y2 = min(h, y2 + margin_y)

            # Simple crop - bỏ alignment phức tạp để tăng tốc độ
            aligned_face = frame[y1:y2, x1:x2]
            return aligned_face

        except Exception as e:
            print(f"[ERROR] Face crop failed: {e}")
            # Fallback simple crop
            x1, y1, x2, y2 = map(int, face.bbox)
            return frame[y1:y2, x1:x2]

    # Trích xuất embedding với kiểm tra chất lượng
    def _get_fast_embedding(self, face):
    
        try:
            # Ưu tiên normed_embedding
            if hasattr(face, "normed_embedding") and face.normed_embedding is not None:
                embedding = face.normed_embedding.copy()
            elif hasattr(face, "embedding") and face.embedding is not None:
                embedding = face.embedding.copy()
                # Chuẩn hóa embedding thành vector đơn vị
                norm = np.linalg.norm(embedding, ord=2)
                if norm > 1e-6:
                    embedding = embedding / norm
                else:
                    return None
            else:
                return None

            # Kiểm tra và đánh giá chất lượng
            if not self._validate_embedding_quality(embedding):
                return None

            # Đảm bảo dữ liệu được lưu dạng số thực
            embedding = embedding.astype(np.float32)
            return embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)

        except Exception as e:
            print(f"[ERROR] Embedding extraction failed: {e}")
            return None

    # Kiểm tra chất lượng embedding
    def _validate_embedding_quality(self, embedding):

        try:
            # Check for NaN/Inf nhanh
            if np.any(np.isnan(embedding)) or np.any(np.isinf(embedding)):
                return False

            # Kiểm tra phạm vi
            norm = np.linalg.norm(embedding)
            if norm < 0.5 or norm > 1.5:  # Tightened range
                return False

            # Kiểm tra phương sai
            variance = np.var(embedding)
            if variance < 1e-5:
                return False

            return True
        except:
            return False

    # So sánh hai embedding khuôn mặt
    def compare_faces(self, embedding1, embedding2, threshold=0.5):

        if embedding1 is None or embedding2 is None:
            return False, 0.0

        try:
            emb1 = np.asarray(embedding1, dtype=np.float32)
            emb2 = np.asarray(embedding2, dtype=np.float32)

            # Chuẩn hóa embedding
            norm1 = np.linalg.norm(emb1)
            norm2 = np.linalg.norm(emb2)

            if norm1 > 1e-6 and norm2 > 1e-6:
                emb1_norm = emb1 / norm1
                emb2_norm = emb2 / norm2
            else:
                return False, 0.0

            # Cosine similarity - QUAN TRỌNG
            cosine_sim = float(np.dot(emb1_norm, emb2_norm))

            # Clip để tránh numerical error
            cosine_sim = np.clip(cosine_sim, -1.0, 1.0)

            # Euclidean distance
            euclidean_dist = float(np.linalg.norm(emb1_norm - emb2_norm))

            # Điểm tương đồng kết hợp
            similarity = cosine_sim * 0.8 + (2.0 - euclidean_dist) / 2.0 * 0.2

            # Vì cosine similarity tốt hơn cho face recognition
            final_similarity = cosine_sim * 0.9 + similarity * 0.1

            match = final_similarity > threshold

            return match, final_similarity

        except Exception as e:
            print(f"[ERROR] Face comparison failed: {e}")
            return False, 0.0

    # Xác định vùng khuôn mặt
    def _get_detection_region(self, frame):

        if not self.roi_enabled or self.current_roi is None:
            return frame

        # Lấy tọa độ vùng quan tâm
        x1, y1, x2, y2 = self.current_roi
        h, w = frame.shape[:2]

        # Kiểm tra ranh giới
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w, x2)
        y2 = min(h, y2)

        return frame[y1:y2, x1:x2]

    # Chỉ vẽ khi được yêu cầu rõ ràng (mặc định tắt)
    def draw_face_box(self, frame, draw_enabled=False):

        if not draw_enabled:
            return frame

        try:
            faces = self.last_frame_faces if self.last_frame_faces else self._fast_face_detection(frame)

            for i, face in enumerate(faces[:3]):
                x1, y1, x2, y2 = map(int, face.bbox)
                colors = [(0, 255, 0), (255, 0, 0), (0, 0, 255)]
                color = colors[i % len(colors)]

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                confidence = getattr(face, 'det_score', 0.0)
                score = self._calculate_face_score(face)
                label = f'ID:{i} Conf:{confidence:.2f} Score:{score:.2f}'

                (text_width, text_height), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(frame, (x1, y1 - text_height - 5), (x1 + text_width, y1), color, -1)
                cv2.putText(frame, label, (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        except Exception as e:
            print(f"[ERROR] Draw face box failed: {e}")
        return frame

    # Lấy thông tin chi tiết của faces
    def get_face_info_fast(self, frame):

        faces = self.last_frame_faces if self.last_frame_faces else self._fast_face_detection(frame)

        face_info = []
        for idx, face in enumerate(faces[:self.max_faces]):
            info = {
                'face_id': idx,
                'bbox': face.bbox.tolist(),
                'confidence': getattr(face, 'det_score', 0.0),
                'quality_score': self._calculate_face_score(face),
                'has_embedding': hasattr(face, 'embedding') and face.embedding is not None,
                'has_landmarks': hasattr(face, 'kps') and face.kps is not None,
                'face_area': (face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1])
            }
            face_info.append(info)

        return face_info

    # Thiết lập chế độ nhanh
    def set_ultra_fast_mode(self, enabled=True):

        if enabled:
            self.min_face_area = 600
            self.max_faces = 2
            self.cache_duration = 0.1
            self.confidence_threshold = 0.5
            print("[INFO] Ultra fast mode activated")
        else:
            self.min_face_area = 800
            self.max_faces = 3
            self.cache_duration = 0.033
            self.confidence_threshold = 0.6
            print("[INFO] Balanced mode restored")

    # Mode độ chính xác cao
    def set_high_accuracy_mode(self, enabled=True):

        if enabled:
            self.min_face_area = 1000  # Tăng
            self.max_faces = 5
            self.cache_duration = 0.02  # Giảm cache
            self.confidence_threshold = 0.7  # Tăng threshold
            print("[INFO] High accuracy mode activated")
        else:
            self.min_face_area = 800
            self.max_faces = 3
            self.cache_duration = 0.033
            self.confidence_threshold = 0.6
            print("[INFO] Balanced mode restored")

    # Bật/ tắt chế độ ROI
    def enable_roi_optimization(self, enabled=True):

        self.roi_enabled = enabled
        if not enabled:
            self.current_roi = None
        print(f"[INFO] ROI optimization {'enabled' if enabled else 'disabled'}")

    # Xóa tất cả dữ liệu được lưu trữ tạm thời
    def clear_cache(self):

        self.last_frame_faces = []
        self.frame_cache_time = 0
        self.face_tracker = {}
        self.detection_history.clear()

    # Khởi động và làm nóng mô hình học máy
    def warm_up(self, test_frame):

        print("[INFO] Warming up model...")
        try:
            # Khởi động nâng cao
            enhanced_frame = self._enhance_frame(test_frame)

            for _ in range(3):
                self.face_app.get(enhanced_frame)

            print("[INFO] Model warmed up successfully")

        except Exception as e:
            print(f"[WARNING] Warm up failed: {e}")

    # Thống kê chi tiết
    def get_statistics(self):

        return {
            'cached_faces': len(self.last_frame_faces), # Trả về số lượng phần tử trong danh sách
            'tracked_faces': len(self.face_tracker), # Trả về số lượng phần tử trong từ điển self.face_tracker
            'cache_duration': self.cache_duration,
            'min_face_area': self.min_face_area, # Diện tích khuôn mặt tối thiểu
            'max_faces': self.max_faces, # Số lượng khuôn mặt tối đa
            'confidence_threshold': self.confidence_threshold, # Ngưỡng tin cậy tối thiểu
            'roi_enabled': self.roi_enabled, # Trạng thái của tính năng tối ưu hóa vùng quan tâm
            'detection_size': getattr(self.face_app, 'det_size', 'unknown') # Kích thước của mô hình phát hiện khuôn mặt.
        }
