@ECHO OFF 
cd /d %~dp0

call py3-env.bat
 
call "C:\Program Files (x86)\Microsoft Visual Studio 14.0\VC\vcvarsall.bat" amd64
call lrelease i18n\qgisfmv.pro -compress -removeidentical

@ECHO OFF
GOTO END

:ERROR
   echo "Failed!Release i18n"
   set ERRORLEVEL=%ERRORLEVEL%
   pause
   
:END
@ECHO OFF
