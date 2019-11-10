@echo off
REM ***************************************************************************
REM    Deploy.bat
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

cd /d %~dp0

ECHO Compile
call Compile.bat

cd /d %~dp0

ECHO I18 Release
call ReleaseI18n.bat

@ECHO OFF
GOTO END

:ERROR
   echo "Failed!Deploy bat"
   set ERRORLEVEL=%ERRORLEVEL%
   pause
   
:END
@ECHO OFF
pause