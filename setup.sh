#!/usr/bin/env bash
# Instala Rehab Arcade en macOS / Linux. Ejecutar dentro de la carpeta del proyecto:  bash setup.sh
set -e

eval "$(conda shell.bash hook)"
conda create -n rehab-arcade python=3.12 -y
conda activate rehab-arcade
pip install -r requirements.txt
python download_models.py

echo
echo "=============================================="
echo " Instalacion completada. Para jugar:"
echo "   conda activate rehab-arcade"
echo "   python main.py --paciente \"Nombre\""
echo "=============================================="
