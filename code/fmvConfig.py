# **********    Properties    **********

# Layer names
Platform_lyr = "Platform"
Beams_lyr = "Beams"
Footprint_lyr = "Footprint"
Trajectory_lyr = "Trajectory"
FrameCenter_lyr = "Frame Center"
Point_lyr = "Drawings Point"
Line_lyr = "Drawings Line"
Polygon_lyr = "Drawings Polygon"

# File extensions (first is default)
Exts = ["mpeg4", "mp4", "avi", "ts", "mpg", "H264", "mov"]

# Layers EPSG
epsg = 'EPSG:4326'

# Group Name
frames_g = "FMV Georeferenced Frames"

# DTM (Digital terrain Model - look data folder globe.tif)
# Change it using your path
DTM_file = "D:\\GitHub\\QGISFMV\\data\\SRTM\\SRTM_W_250m.tif"
# Raster square size in pixel that will be loaded from DTM
DTM_buffer_size = 80

# Reverse geocoding service that transforms point to address
Reverse_geocoding_url = "https://nominatim.openstreetmap.org/reverse.php?format=json&lat={}&lon={}"

# FFmpeg path
ffmpeg = "D:\\FFMPEG"
ffprobe = "D:\\FFMPEG"

# Buffer Metadata Reader Size (IMPORTANT : IF THIS VALUE IS VERY HIGH THE PLUGIN WILL FAIL)
min_buffer_size = 8
