@echo off
REM ***************************************************************************
REM    QGIS_env_PyCharm.bat
REM    ---------------------
REM    begin                : June 2017
REM    copyright            : (C) 2017 by Fran Raga
REM    email                : franka1986 at gmail dot com
REM ***************************************************************************
REM *                                                                         *
REM *   This program is free software; you can redistribute it and/or modify  *
REM *   it under the terms of the GNU General Public License as published by  *
REM *   the Free Software Foundation; either version 2 of the License, or     *
REM *   (at your option) any later version.                                   *
REM *                                                                         *
REM ***************************************************************************

:: QGIS development environment in PyCharm for Windows

set OSGEO4W_ROOT=D:\OSGeo4W64

@echo off
call %OSGEO4W_ROOT%\bin\o4w_env.bat
call qt5_env.bat
call py3_env.bat

set QT_QPA_PLATFORM_PLUGIN_PATH=%OSGEO4W_ROOT%\apps\Qt5\plugins
set PATH=%PATH%;%OSGEO4W_ROOT%\apps\qgis\bin;%OSGEO4W_ROOT%\bin

start "QGIS PyCharm" /B "C:\Program Files\JetBrains\PyCharm Community Edition 2019.2.1\bin\pycharm64.exe" %*
