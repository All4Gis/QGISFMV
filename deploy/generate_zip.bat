@echo off
REM ***************************************************************************
REM    generate_zip.bat
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

:: Generate Zip for upload to QGIS Repo


cd /D %~dp0\..\\code\\
call py3-env.bat

cd /D %~dp0

call python3 plugin_zip.py

:CONTINUE
   echo "Zip generated for QGIS version %QGIS_VERSION%"
   set ERRORLEVEL=0
   goto END
   
:ERROR
   echo "Error generating zip for QGIS version %QGIS_VERSION%"
   set ERRORLEVEL=%ERRORLEVEL%
   pause

:END
