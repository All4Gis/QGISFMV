@echo off
REM ***************************************************************************
REM    QGIS_env_eclipse.bat
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

:: QGIS development environment in eclipse for Windows

set OSGEO4W_ROOT=D:\OSGeo4W64
set JAVA_HOME=C:\Program Files\Java\jre1.8.0_221
set ECLIPSE_HOME=D:\eclipse

@echo off
call %OSGEO4W_ROOT%\bin\o4w_env.bat
call qt5_env.bat
call py3_env.bat

@echo off
path %OSGEO4W_ROOT%\apps\qgis\bin;%PATH%

set GDAL_FILENAME_IS_UTF8=YES
set VSI_CACHE=TRUE
set VSI_CACHE_SIZE=1000000
set QT_PLUGIN_PATH=%OSGEO4W_ROOT%\apps\qgis\qtplugins;%OSGEO4W_ROOT%\apps\qt5\plugins
set QT_QPA_PLATFORM_PLUGIN_PATH=%OSGEO4W_ROOT%\apps\Qt5\plugins\platforms
set QGIS_PREFIX_PATH=%OSGEO4W_ROOT%\apps\qgis

cd /d %~dp0

start "eclipse" "%ECLIPSE_HOME%\eclipse.exe" -vm "%JAVA_HOME%\bin\javaw.exe" -data .
