@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "REPO_ROOT=%~dp0"
set "REPO_ROOT=%REPO_ROOT:~0,-1%"
set "PLUGIN_SOURCE=%REPO_ROOT%\code"
set "QGIS_PROFILE=%APPDATA%\QGIS\QGIS4\profiles\default"
set "PLUGIN_DIR=%QGIS_PROFILE%\python\plugins"
set "PLUGIN_NAME=QGISFMV"
set "FMV_PKGS=%USERPROFILE%\.qgis-fmv-packages"
if defined QGIS_FMV_PACKAGES set "FMV_PKGS=%QGIS_FMV_PACKAGES%"

echo ======================================
echo  QGIS FMV DEV INSTALL (Windows)
echo ======================================

if not exist "%PLUGIN_SOURCE%" (
    echo Error: Plugin source not found at %PLUGIN_SOURCE%
    exit /b 1
)

if not exist "%QGIS_PROFILE%" (
    echo Error: QGIS profile not found at %QGIS_PROFILE%
    echo Make sure QGIS 4 is installed and has been launched once.
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
echo Resolving QGIS / OSGeo4W Python...
set "PY_EXE="
if defined QGIS_PY if exist "%QGIS_PY%" set "PY_EXE=%QGIS_PY%"

if not defined PY_EXE if defined OSGEO4W_ROOT (
    if exist "%OSGEO4W_ROOT%\apps\Python312\python.exe" set "PY_EXE=%OSGEO4W_ROOT%\apps\Python312\python.exe"
    if not defined PY_EXE if exist "%OSGEO4W_ROOT%\apps\Python311\python.exe" set "PY_EXE=%OSGEO4W_ROOT%\apps\Python311\python.exe"
    if not defined PY_EXE if exist "%OSGEO4W_ROOT%\bin\python.exe" set "PY_EXE=%OSGEO4W_ROOT%\bin\python.exe"
)

if not defined PY_EXE if exist "C:\OSGeo4W\apps\Python312\python.exe" set "PY_EXE=C:\OSGeo4W\apps\Python312\python.exe"
if not defined PY_EXE if exist "C:\OSGeo4W\apps\Python311\python.exe" set "PY_EXE=C:\OSGeo4W\apps\Python311\python.exe"
if not defined PY_EXE if exist "C:\OSGeo4W\bin\python.exe" set "PY_EXE=C:\OSGeo4W\bin\python.exe"

if not defined PY_EXE (
    where python >nul 2>&1
    if not errorlevel 1 for /f "delims=" %%P in ('where python') do (
        set "PY_EXE=%%P"
        goto :have_python
    )
)

:have_python
if not defined PY_EXE (
    echo Warning: could not find QGIS/OSGeo4W Python.
    echo Install deps manually from the OSGeo4W Shell:
    echo   mkdir "%FMV_PKGS%"
    echo   python -m pip install --target "%FMV_PKGS%" -r "%PLUGIN_SOURCE%\requirements.txt"
    goto :done
)

echo Using Python: %PY_EXE%
echo Target packages: %FMV_PKGS%
if not exist "%FMV_PKGS%" mkdir "%FMV_PKGS%"

set "PYTHONNOUSERSITE=1"
set "PYTHONPATH=%FMV_PKGS%;%PYTHONPATH%"

echo Installing Python dependencies from code\requirements.txt...
"%PY_EXE%" -m pip install --upgrade --target "%FMV_PKGS%" pip setuptools wheel 2>nul
"%PY_EXE%" -m pip install --target "%FMV_PKGS%" -r "%PLUGIN_SOURCE%\requirements.txt"
if errorlevel 1 (
    echo.
    echo Warning: pip install failed. From OSGeo4W Shell try:
    echo   python -m pip install --target "%FMV_PKGS%" -r "%PLUGIN_SOURCE%\requirements.txt"
)

:done
echo.
echo Plugin linked:
dir "%PLUGIN_DIR%\%PLUGIN_NAME%"
echo.
echo Packages: %FMV_PKGS%  (added to sys.path by the plugin)
echo Open QGIS and reload the plugin.

endlocal
