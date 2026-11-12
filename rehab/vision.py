"""Envoltorio de MediaPipe: detección de pose (cuerpo) y de mano.

Las dos tareas se crean en modo VIDEO, que aprovecha el seguimiento entre
frames y es más estable que detectar imagen a imagen.
"""
import time

import cv2
import mediapipe as mp

# Índices de MediaPipe Pose que usamos (tren superior)
POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24), (15, 19), (16, 20),
]

# Conexiones de los 21 puntos de la mano
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
]


def to_px(landmark, width: int, height: int) -> tuple:
    """Convierte un landmark normalizado (0-1) a píxeles."""
    return (landmark.x * width, landmark.y * height)


class Tracker:
    """Crea los dos detectores una sola vez y los reutiliza en todo el juego."""

    def __init__(self, pose_model: str, hand_model: str):
        vision = mp.tasks.vision
        base = mp.tasks.BaseOptions

        self._pose = vision.PoseLandmarker.create_from_options(
            vision.PoseLandmarkerOptions(
                base_options=base(model_asset_path=pose_model),
                running_mode=vision.RunningMode.VIDEO,
                num_poses=1,
                min_pose_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        )
        self._hands = vision.HandLandmarker.create_from_options(
            vision.HandLandmarkerOptions(
                base_options=base(model_asset_path=hand_model),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        )
        # En modo VIDEO cada detector necesita timestamps estrictamente crecientes
        self._last_ts = {"pose": 0, "hands": 0}

    def _timestamp(self, key: str) -> int:
        ts = int(time.monotonic() * 1000)
        if ts <= self._last_ts[key]:
            ts = self._last_ts[key] + 1
        self._last_ts[key] = ts
        return ts

    @staticmethod
    def _to_mp_image(frame_bgr):
        # OpenCV trabaja en BGR pero MediaPipe espera RGB
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        return mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    def detect_pose(self, frame_bgr):
        """Devuelve la lista de 33 landmarks del cuerpo, o None."""
        result = self._pose.detect_for_video(self._to_mp_image(frame_bgr), self._timestamp("pose"))
        return result.pose_landmarks[0] if result.pose_landmarks else None

    def detect_hand(self, frame_bgr):
        """Devuelve la lista de 21 landmarks de la mano, o None."""
        result = self._hands.detect_for_video(self._to_mp_image(frame_bgr), self._timestamp("hands"))
        return result.hand_landmarks[0] if result.hand_landmarks else None

    def close(self):
        self._pose.close()
        self._hands.close()


def draw_pose(frame, landmarks, color=(255, 200, 0)):
    h, w = frame.shape[:2]
    for a, b in POSE_CONNECTIONS:
        pa, pb = to_px(landmarks[a], w, h), to_px(landmarks[b], w, h)
        cv2.line(frame, tuple(map(int, pa)), tuple(map(int, pb)), color, 3, cv2.LINE_AA)
    for idx in (11, 12, 13, 14, 15, 16, 23, 24):
        p = to_px(landmarks[idx], w, h)
        cv2.circle(frame, tuple(map(int, p)), 6, (255, 255, 255), -1, cv2.LINE_AA)


def draw_hand(frame, landmarks, color=(255, 200, 0)):
    h, w = frame.shape[:2]
    for a, b in HAND_CONNECTIONS:
        pa, pb = to_px(landmarks[a], w, h), to_px(landmarks[b], w, h)
        cv2.line(frame, tuple(map(int, pa)), tuple(map(int, pb)), color, 2, cv2.LINE_AA)
    for lm in landmarks:
        p = to_px(lm, w, h)
        cv2.circle(frame, tuple(map(int, p)), 4, (255, 255, 255), -1, cv2.LINE_AA)
