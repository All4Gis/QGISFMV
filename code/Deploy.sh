#!/bin/sh
###########################################################################
#    Deploy.sh
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

echo "Compile"
sh Compile.sh

echo "i18n"
sh ReleaseI18n.sh
