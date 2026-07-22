@echo off
setlocal EnableExtensions
cd /d "%~dp0\..\.."
python -m pip install -q pytest
python -m pytest code/tests %*
endlocal
