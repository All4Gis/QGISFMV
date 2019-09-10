@ECHO OFF 
cd /d %~dp0
:: Upload file to Transifex
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