@ECHO ON
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