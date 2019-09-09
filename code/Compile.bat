@ECHO OFF 
cd /d %~dp0

call py3-env.bat
 
@ECHO ON

::Ui Compilation
call pyuic5 --import-from QGIS_FMV.gui ui\ui_ColorDialog.ui -o gui\ui_ColorDialog.py  
call pyuic5 --import-from QGIS_FMV.gui ui\ui_FmvAbout.ui -o gui\ui_FmvAbout.py  
call pyuic5 --import-from QGIS_FMV.gui ui\ui_FmvManager.ui -o gui\ui_FmvManager.py  
call pyuic5 --import-from QGIS_FMV.gui ui\ui_FmvMetadata.ui -o gui\ui_FmvMetadata.py  
call pyuic5 --import-from QGIS_FMV.gui ui\ui_FmvMultiplexer.ui -o gui\ui_FmvMultiplexer.py  
call pyuic5 --import-from QGIS_FMV.gui ui\ui_FmvOpenStream.ui -o gui\ui_FmvOpenStream.py  
call pyuic5 --import-from QGIS_FMV.gui ui\ui_FmvOptions.ui -o gui\ui_FmvOptions.py  
call pyuic5 --import-from QGIS_FMV.gui ui\ui_FmvPlayer.ui -o gui\ui_FmvPlayer.py  

::Resources
call pyrcc5 ui\resources.qrc -o gui\resources_rc.py

::Translations
cd..
call pull-transifex-translations.bat
cd..
call push-transifex-translations.bat

@ECHO OFF
GOTO END

:ERROR
   echo "Failed!"
   set ERRORLEVEL=%ERRORLEVEL%
   pause
   
:END
@ECHO OFF
pause
