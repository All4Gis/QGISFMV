import platform
from configparser import ConfigParser
import os
from os.path import dirname, abspath

try:
    from pydevd import *
except ImportError:
    None

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


EARTH_MEAN_RADIUS = 6371008.8
WGS84String = "WGS84"

isWindows = platform.system() == "Windows"

if isWindows:
    ffmpeg_path = os.path.join(ffmpegConf, "ffmpeg.exe")
    ffprobe_path = os.path.join(ffmpegConf, "ffprobe.exe")
else:
    ffmpeg_path = os.path.join(ffmpegConf, "ffmpeg")
    ffprobe_path = os.path.join(ffmpegConf, "ffprobe")
