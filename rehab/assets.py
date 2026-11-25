"""Imágenes del juego (carpeta assets/).

Cada imagen está en assets/<nombre>.png, ya con el fondo transparente. Las
genero con IA y antes de meterlas en la carpeta les quito el fondo.

Las imágenes se escalan una vez a cada tamaño que se pide y se guardan en
caché ya preparadas para pegarlas rápido (ver ui._blend). Si falta alguna,
el juego sigue y simplemente no la dibuja (sale un aviso en la consola).
"""
import math
import os
from functools import lru_cache

import cv2
import numpy as np

import config
from rehab import ui


@lru_cache(maxsize=None)
def load(name: str):
    """Imagen BGRA de assets/<name>.png, o None si no está."""
    path = os.path.join(config.ASSETS_DIR, f"{name}.png")
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED) if os.path.exists(path) else None
    if img is None:
        print(f"Aviso: falta la imagen {path}")
        return None
    if img.shape[2] == 3:  # sin transparencia (los fondos)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    return img


@lru_cache(maxsize=1024)
def _prepared(name, w, h, keep_aspect, angle, tint):
    src = load(name)
    if src is None:
        return None
    sh, sw = src.shape[:2]
    if keep_aspect:
        s = min(w / sw, h / sh)
        w, h = max(1, int(sw * s)), max(1, int(sh * s))
    img = cv2.resize(src, (w, h), interpolation=cv2.INTER_AREA if w < sw else cv2.INTER_LINEAR)
    if tint is not None:  # tiñe una imagen blanca/gris con un color (el de cada dedo en el piano)
        bgr = cv2.multiply(img[..., :3], np.full((h, w, 3), tint, np.uint8), scale=1 / 255)
        img = np.dstack([bgr, img[..., 3]])
    if angle:  # el trineo se inclina un poco al subir y bajar
        diag = int(math.hypot(w, h)) + 2
        m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        m[0, 2] += (diag - w) / 2
        m[1, 2] += (diag - h) / 2
        img = cv2.warpAffine(img, m, (diag, diag), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    alpha = cv2.merge([img[..., 3]] * 3)
    pre = cv2.multiply(np.ascontiguousarray(img[..., :3]), alpha, scale=1 / 255)
    return 255 - alpha, pre


def draw(img, name, center, w, h, angle=0.0, tint=None) -> bool:
    """Pega la imagen centrada en `center`, cabiendo en w x h (sin deformarla)."""
    item = _prepared(name, int(w), int(h), True, round(angle / 3) * 3, tint)
    if item is None:
        return False
    inv, pre = item
    ui._blend(img, inv, pre, int(center[0] - inv.shape[1] / 2), int(center[1] - inv.shape[0] / 2))
    return True


def draw_rect(img, name, rect, tint=None) -> bool:
    """Pega la imagen estirada para llenar justo el rectángulo (x1, y1, x2, y2)."""
    x1, y1, x2, y2 = (int(v) for v in rect)
    if x2 - x1 < 2 or y2 - y1 < 2:
        return False
    item = _prepared(name, x2 - x1, y2 - y1, False, 0, tint)
    if item is None:
        return False
    ui._blend(img, item[0], item[1], x1, y1)
    return True


@lru_cache(maxsize=8)
def background(name, w, h):
    """Fondo a pantalla completa (BGR), o None si no hay imagen."""
    img = load(name)
    return None if img is None else cv2.resize(img[..., :3], (w, h), interpolation=cv2.INTER_AREA)
