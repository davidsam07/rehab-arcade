@echo off
REM Instala Rehab Arcade en Windows. Ejecutar desde "Anaconda Prompt" dentro de la carpeta del proyecto.

call conda create -n rehab-arcade python=3.12 -y || goto :error
call conda activate rehab-arcade || goto :error
pip install -r requirements.txt || goto :error
python download_models.py || goto :error

echo.
echo ==============================================
echo  Instalacion completada. Para jugar:
echo    conda activate rehab-arcade
echo    python main.py --paciente "Nombre"
echo ==============================================
goto :eof

:error
echo.
echo Ha fallado la instalacion. Revisa el mensaje de error de arriba.
exit /b 1
