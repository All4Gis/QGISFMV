@echo off
REM ***************************************************************************
REM    ReleaseI18n.bat
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

call py3-env.bat
 
call "C:\Program Files (x86)\Microsoft Visual Studio\2017\Community\VC\Auxiliary\Build\vcvarsall.bat" amd64
call lrelease i18n\qgisfmv.pro -compress -removeidentical

@echo off
GOTO END

:ERROR
   echo "Failed!Release i18n"
   set ERRORLEVEL=%ERRORLEVEL%
   pause
   
:END
@ECHO OFF
