:: QGIS development environment in eclipse for Windows

set OSGEO4W_ROOT=D:\OSGeo4W64
set JAVA_HOME=C:\Program Files\Java\jre1.8.0_221
set ECLIPSE_HOME=D:\eclipse

call "%OSGEO4W_ROOT%\bin\o4w_env.bat"
call "%OSGEO4W_ROOT%\bin\qt5_env.bat"
call "%OSGEO4W_ROOT%\bin\py3_env.bat"

set QT_QPA_PLATFORM_PLUGIN_PATH=%OSGEO4W_ROOT%\apps\Qt5\plugins
set PATH=%PATH%;%OSGEO4W_ROOT%\apps\qgis\bin;%OSGEO4W_ROOT%\bin

start "eclipse" "%ECLIPSE_HOME%\eclipse.exe" -vm "%JAVA_HOME%\bin\javaw.exe" -data .