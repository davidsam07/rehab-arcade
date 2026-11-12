"""Guardado del historial de sesiones en CSV (uno por modo de juego).

data/hombro.csv y data/mano.csv tienen una fila por partida. Así el
terapeuta puede abrirlos en Excel y nosotros pintar la evolución.
Si una versión nueva del juego añade columnas, el CSV se reescribe con
todas ellas y las partidas antiguas quedan con esas casillas vacías.
"""
import csv
import os

from config import DATA_DIR


def _path(game_key: str) -> str:
    return os.path.join(DATA_DIR, f"{game_key}.csv")


def save_session(game_key: str, row: dict) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    path = _path(game_key)
    old_rows, fields = [], []
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fields = list(reader.fieldnames or [])
            old_rows = list(reader)
    new_fields = [k for k in row if k not in fields]
    if new_fields or not fields:
        # Columnas nuevas (o fichero nuevo): reescribimos con la cabecera completa
        fields += new_fields
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, restval="")
            writer.writeheader()
            writer.writerows(old_rows)
            writer.writerow(row)
    else:
        with open(path, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=fields, restval="").writerow(row)
    return path


def load_history(game_key: str, patient: str) -> list:
    path = _path(game_key)
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("paciente") == patient]
