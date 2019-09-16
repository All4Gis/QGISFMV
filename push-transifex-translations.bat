@echo off
REM ***************************************************************************
REM    push-transifex-translations.bat
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

:: Upload file to Transifex

cd /d %~dp0

@ECHO ON

call "code/py3-env.bat"

tx push -s -t --skip

@ECHO OFF
GOTO END

:ERROR
   echo "Failed!Upload file to Transifex"
   set ERRORLEVEL=%ERRORLEVEL%
   pause
   
:END
@ECHO OFF