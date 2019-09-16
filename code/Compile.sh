#!/bin/sh
###########################################################################
#    Compile.sh
#    ---------------------
#    Date                 : June 2017
#    Copyright            : (C) 2017 by Fran Raga
#    Email                : franka1986 at gmail dot com
###########################################################################
#                                                                         #
#   This program is free software; you can redistribute it and/or modify  #
#   it under the terms of the GNU General Public License as published by  #
#   the Free Software Foundation; either version 2 of the License, or     #
#   (at your option) any later version.                                   #
#                                                                         #
###########################################################################

echo "converting ui files"

pyuic5 --import-from QGIS_FMV.gui ui/ui_ColorDialog.ui -o gui/ui_ColorDialog.py  
pyuic5 --import-from QGIS_FMV.gui ui/ui_FmvAbout.ui -o gui/ui_FmvAbout.py  
pyuic5 --import-from QGIS_FMV.gui ui/ui_FmvManager.ui -o gui/ui_FmvManager.py  
pyuic5 --import-from QGIS_FMV.gui ui/ui_FmvMetadata.ui -o gui/ui_FmvMetadata.py  
pyuic5 --import-from QGIS_FMV.gui ui/ui_FmvMultiplexer.ui -o gui/ui_FmvMultiplexer.py  
pyuic5 --import-from QGIS_FMV.gui ui/ui_FmvOpenStream.ui -o gui/ui_FmvOpenStream.py  
pyuic5 --import-from QGIS_FMV.gui ui/ui_FmvOptions.ui -o gui/ui_FmvOptions.py  
pyuic5 --import-from QGIS_FMV.gui ui/ui_FmvPlayer.ui -o gui/ui_FmvPlayer.py  

echo "converting resources file"

pyrcc5 ui/resources.qrc -o gui/resources_rc.py

echo "Translations"
cd ..
sh pull-transifex-translations.sh
sh push-transifex-translations.sh