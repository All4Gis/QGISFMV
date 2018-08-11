@echo ON

cd /d %~dp0

call "py3-env.bat"

python3 -m pip install -r requirements.txt

pause
