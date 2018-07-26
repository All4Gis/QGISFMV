@echo ON

cd /d %~dp0

call "py3-env.bat"

cd /D %UserProfile%

python3 -m pip install matplotlib==2.0.0
python3 -m pip install opencv-python==3.4.0.12
python3 -m pip install homography==0.1.5
pause
