@ECHO OFF 
:: Download data from Transifex
cd /d %~dp0

@ECHO ON

call "code/py3-env.bat"

tx pull -a -f --skip

@ECHO OFF
GOTO END

:ERROR
   echo "Failed!Download data from Transifex"
   set ERRORLEVEL=%ERRORLEVEL%
   pause
   
:END
@ECHO OFF