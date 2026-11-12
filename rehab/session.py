"""Guardado del historial de sesiones en CSV (uno por modo de juego).

data/hombro.csv y data/mano.csv tienen una fila por partida. Así el
terapeuta puede abrirlos en Excel y nosotros pintar la evolución.
"""
import csv
import os

from config import DATA_DIR


def _path(game_key: str) -> str:
    return os.path.join(DATA_DIR, f"{game_key}.csv")


def save_session(game_key: str, row: dict) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    path = _path(game_key)
    is_new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if is_new:
            writer.writeheader()
        writer.writerow(row)
    return path


def load_history(game_key: str, patient: str) -> list:
    path = _path(game_key)
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("paciente") == patient]
