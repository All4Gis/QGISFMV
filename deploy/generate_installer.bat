@ECHO OFF

cd /D %~dp0\..\\code\\
call py3-env.bat

cd /D %~dp0

call python utils.py

:CONTINUE
   echo "Zip generated for QGIS version %QGIS_VERSION%"
   set ERRORLEVEL=0
   goto END
   
:ERROR
   echo "Error generating zip for QGIS version %QGIS_VERSION%"
   set ERRORLEVEL=%ERRORLEVEL%
   pause

:END
pause