"""Paisaje nevado de noche con scroll en capas (efecto parallax).

Es el fondo de los menús y del trineo. Tiene tres capas: el cielo
(fondo_cielo.png, quieto), unas montañas lejanas que se mueven despacio y
las colinas con las casitas (colinas.png), que se mueven más rápido. Así
parece que hay profundidad. Encima cae nieve.

Cada capa se prepara una vez al arrancar y luego solo se copia el trozo que
se ve, que es muy rápido.
"""
import random

import cv2
import numpy as np

from rehab import assets, ui


class WinterScene:
    def __init__(self, w, h, seed=4):
        self.w, self.h = w, h
        self.t = 0.0
        self.scroll = 0.0
        sky = assets.background("fondo_cielo", w, h)
        self.sky = sky if sky is not None else np.full((h, w, 3), (60, 25, 15), np.uint8)
        self.layers = [self._mountains(random.Random(seed)) + (0.15,)]   # (imagen, máscara, velocidad)
        hills = self._hills()
        if hills is not None:
            self.layers.append(hills + (0.45,))
        # Cada capa se duplica en horizontal para poder recortar cualquier trozo sin salirse
        self.layers = [(np.concatenate([i, i], 1), np.concatenate([m, m], 1), s) for i, m, s in self.layers]
        self.snow = ui.Snow(80, seed=seed)

    def _mountains(self, rng):
        """Montañas lejanas: una silueta morada hecha con senos (se repite cada w píxeles)."""
        w, h = self.w, self.h
        x = np.arange(w)
        y = np.full(w, h * 0.62)
        for k, a in [(2, h * 0.05), (3, h * 0.04), (7, h * 0.015)]:
            y += a * np.sin(2 * np.pi * k * x / w + rng.uniform(0, 6.28))
        pts = np.array([(0, h)] + [(i, int(v)) for i, v in enumerate(y)] + [(w - 1, h)], np.int32)
        mask = np.zeros((h, w), np.uint8)
        cv2.fillPoly(mask, [pts], 255)
        img = np.zeros((h, w, 3), np.uint8)
        img[mask > 0] = (105, 52, 62)
        cv2.polylines(img, [pts[1:-1]], False, (200, 170, 185), 3, cv2.LINE_AA)   # un poco de nieve arriba
        return img, mask

    def _hills(self):
        """Colinas de primer plano (colinas.png), pegadas abajo del todo."""
        hills = assets.load("colinas")
        if hills is None:
            return None
        w, h = self.w, self.h
        ch = int(hills.shape[0] * w / hills.shape[1])
        hills = cv2.resize(hills, (w, ch))
        img = np.zeros((h, w, 3), np.uint8)
        mask = np.zeros((h, w), np.uint8)
        img[h - ch:] = hills[..., :3]
        mask[h - ch:] = (hills[..., 3] > 127).astype(np.uint8) * 255
        return img, mask

    def draw(self, frame, dt, speed=40.0, snow=True):
        """Pinta el paisaje en `frame`. speed: px/s de la capa de delante."""
        self.t += dt
        self.scroll += speed * dt
        frame[:] = self.sky
        for img, mask, rel in self.layers:
            off = int(self.scroll * rel) % self.w
            cv2.copyTo(img[:, off:off + self.w], mask[:, off:off + self.w], frame)
        if snow:
            self.snow.draw(frame, dt)
        return frame
