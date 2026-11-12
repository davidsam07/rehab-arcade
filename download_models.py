"""Descarga los modelos de MediaPipe que usa el juego (pose y manos)."""
import os

import requests
import tqdm

from config import MODELS_DIR

MODELS = {
    "pose_landmarker_full.task":
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
        "pose_landmarker_full/float16/latest/pose_landmarker_full.task",
    "hand_landmarker.task":
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
        "hand_landmarker/float16/latest/hand_landmarker.task",
}


def download(name: str, url: str) -> None:
    dest = os.path.join(MODELS_DIR, name)
    if os.path.exists(dest):
        print(f"{name} ya existe, se omite.")
        return
    print(f"Descargando {name} ...")
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))
    tmp = dest + ".part"
    with open(tmp, "wb") as f, tqdm.tqdm(total=total, unit="iB", unit_scale=True) as bar:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            bar.update(len(chunk))
    os.replace(tmp, dest)


if __name__ == "__main__":
    os.makedirs(MODELS_DIR, exist_ok=True)
    for model_name, model_url in MODELS.items():
        download(model_name, model_url)
    print("Modelos listos en", MODELS_DIR)
