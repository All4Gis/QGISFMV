import platform
from configparser import ConfigParser
import os
from os.path import dirname, abspath

# Settings
parser = ConfigParser()
fileConfig = os.path.join(dirname(abspath(__file__)), "settings.ini")
parser.read(fileConfig)

ffmpegConf = parser["GENERAL"]["ffmpeg"]
DemConf = parser["GENERAL"]["DTM_file"]
min_buffer_size = int(parser["GENERAL"]["min_buffer_size"])

Platform_lyr = parser["LAYERS"]["Platform_lyr"]
Beams_lyr = parser["LAYERS"]["Beams_lyr"]
Footprint_lyr = parser["LAYERS"]["Footprint_lyr"]
FrameCenter_lyr = parser["LAYERS"]["FrameCenter_lyr"]
FrameAxis_lyr = parser["LAYERS"]["FrameAxis_lyr"]
Point_lyr = parser["LAYERS"]["Point_lyr"]
Line_lyr = parser["LAYERS"]["Line_lyr"]
Polygon_lyr = parser["LAYERS"]["Polygon_lyr"]
frames_g = parser["LAYERS"]["frames_g"]
Trajectory_lyr = parser["LAYERS"]["Trajectory_lyr"]
epsg = parser["LAYERS"]["epsg"]
Reverse_geocoding_url = parser["GENERAL"]["Reverse_geocoding_url"]
dtm_buffer = int(parser["GENERAL"]["DTM_buffer_size"])

# Geo variables
EARTH_MEAN_RADIUS = 6371008.8
WGS84String = "WGS84"
encoding = "utf-8"

# Klv variables
UASLocalMetadataSet = b"\x06\x0e+4\x02\x0b\x01\x01\x0e\x01\x03\x01\x01\x00\x00\x00"
KlvHeaderKeyOther = b"\x06\x0e+4\x02\x01\x01\x01\x0e\x01\x01\x02\x01\x01\x00\x00"

# OS variables
isWindows = platform.system() == "Windows"

if isWindows:
    ffmpeg_path = os.path.join(ffmpegConf, "ffmpeg.exe")
    ffprobe_path = os.path.join(ffmpegConf, "ffprobe.exe")
else:
    ffmpeg_path = os.path.join(ffmpegConf, "ffmpeg")
    ffprobe_path = os.path.join(ffmpegConf, "ffprobe")
