@echo off
setlocal EnableExtensions

set "REPO_ROOT=%~dp0"
set "REPO_ROOT=%REPO_ROOT:~0,-1%"
set "PLUGIN_SOURCE=%REPO_ROOT%\code"
set "QGIS_PROFILE=%APPDATA%\QGIS\QGIS4\profiles\default"
set "PLUGIN_DIR=%QGIS_PROFILE%\python\plugins"
set "PLUGIN_NAME=QGISFMV"

echo ======================================
echo  QGIS FMV DEV INSTALL (Windows)
echo ======================================

if not exist "%PLUGIN_SOURCE%" (
    echo Error: Plugin source not found at %PLUGIN_SOURCE%
    exit /b 1
)

if not exist "%QGIS_PROFILE%" (
    echo Error: QGIS profile not found at %QGIS_PROFILE%
    echo Make sure QGIS 4 is installed.
    exit /b 1
)

if not exist "%PLUGIN_DIR%" mkdir "%PLUGIN_DIR%"

if exist "%PLUGIN_DIR%\%PLUGIN_NAME%" (
    echo Removing previous plugin link...
    rmdir "%PLUGIN_DIR%\%PLUGIN_NAME%" 2>nul
    del "%PLUGIN_DIR%\%PLUGIN_NAME%" 2>nul
)

echo Linking plugin code...
mklink /J "%PLUGIN_DIR%\%PLUGIN_NAME%" "%PLUGIN_SOURCE%"
if errorlevel 1 (
    echo Failed to create plugin junction. Run this script as Administrator or enable Developer Mode.
    exit /b 1
)

if exist "%PLUGIN_SOURCE%\vendor" (
    echo Removing legacy vendor link...
    rmdir "%PLUGIN_SOURCE%\vendor" 2>nul
)

if exist "%PLUGIN_SOURCE%\python_deps" (
    echo Removing legacy python_deps folder...
    rmdir /s /q "%PLUGIN_SOURCE%\python_deps"
)

echo.
echo Installing Python dependencies from code\requirements.txt...
where python >nul 2>&1
if errorlevel 1 (
    echo Warning: python not on PATH. Install deps manually from QGIS OSGeo4W shell:
    echo   python -m pip install -r "%PLUGIN_SOURCE%\requirements.txt"
) else (
    python -m pip install --upgrade pip setuptools wheel
    python -m pip install -r "%PLUGIN_SOURCE%\requirements.txt"
)

echo.
echo Plugin linked:
dir "%PLUGIN_DIR%\%PLUGIN_NAME%"
echo.
echo Open QGIS and reload the plugin.

endlocal
