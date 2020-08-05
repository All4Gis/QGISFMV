import sys
from qgis.PyQt.QtWidgets import QApplication
app=QApplication([""])

from QGIS_FMV.klvdata.streamparser import StreamParser
from QGIS_FMV.klvdata.element import UnknownElement

print ('Number of arguments:', len(sys.argv), 'arguments.')

if len(sys.argv) == 2:
    
    print ("data: "+sys.argv[1])
    stdout_data = open(sys.argv[1], 'rb').read()
    
    for packet in StreamParser(stdout_data):
        if isinstance(packet, UnknownElement):
            print("Error interpreting klv data, metadata cannot be read.")
            continue
        data = packet.MetadataList()
        print("First Precision Time Stamp:"+ str(data[2]))
        #break