@echo off
REM ***************************************************************************
REM    py3-env.bat
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

set OSGEO4W_ROOT=D:\OSGeo4W64

set PATH=%OSGEO4W_ROOT%\bin;%PATH%
set PATH=%PATH%;%OSGEO4W_ROOT%\apps\qgis\bin

@echo off
call %OSGEO4W_ROOT%\bin\o4w_env.bat
call qt5_env.bat
call py3_env.bat
@echo off
path %OSGEO4W_ROOT%\apps\qgis\bin;%PATH%

cd /d %~dp0