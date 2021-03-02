# -*- coding: utf-8 -*-
import matplotlib.pyplot as plt
import os
import gi
import cv2

# Author : Fran Raga , 2021
# proof of concept to ingest KLV telemetry into a video. Multiplexer concept to create a MISB Video.
# Related with : https://github.com/All4Gis/QGISFMV/blob/master/code/manager/QgsMultiplexor.py

# Get Video width/Height
# ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 DJI_0047.MP4 
# width 3840x  height 2160

# Get Frame rate
# ffprobe -v error -select_streams v -of default=noprint_wrappers=1:nokey=1 -show_entries stream=r_frame_rate DJI_0047.MP4 

# Merge all klv from QGISFMV to use in this code
# import glob
# 
# files = []
# for file in glob.glob("/home/fragalop/SamplesFMV/multiplexor/klv/*.klv"):
#     files.append(file)
# 
# out_data = b''
# for fn in files:
#     with open(fn, 'rb') as fp:
#         out_data += fp.read()
# with open('/home/fragalop/SamplesFMV/multiplexor/all.klv', 'wb') as fp:
#     fp.write(out_data)

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject

vid_file = "/home/fragalop/SamplesFMV/multiplexor/DJI_0047/0.0.mp4"
vid_frame_rate = 30
vid_width = 3840
vid_height = 2160
klv_file = "/home/fragalop/SamplesFMV/multiplexor/all.klv"
klv_packet_size = 112 # Extracted from QGISFMV "Create MISB Tool"
out_file = "/home/fragalop/SamplesFMV/multiplexor/MISB.mp4"
tmp_image= "/home/fragalop/SamplesFMV/multiplexor/tmp.jpg"

GObject.threads_init()
Gst.init(None)

# video source elements
vsrc = Gst.ElementFactory.make("appsrc", "vidsrc")
vqueue = Gst.ElementFactory.make("queue")
vtee = Gst.ElementFactory.make("tee")

# klv source elements
appsrc = Gst.ElementFactory.make("appsrc")
queue_klv = Gst.ElementFactory.make("queue")

# display elements
#queue_display = Gst.ElementFactory.make("queue")
#vcvt = Gst.ElementFactory.make("videoconvert", "vidcvt")
#vsink = Gst.ElementFactory.make("autovideosink", "vidsink")

# recording elements
queue_record = Gst.ElementFactory.make("queue")
vcvt_encoder = Gst.ElementFactory.make("videoconvert")
encoder = Gst.ElementFactory.make("x264enc")
muxer = Gst.ElementFactory.make("mpegtsmux")
filesink = Gst.ElementFactory.make("filesink")

# configure video element
caps_str = "video/x-raw"
caps_str += ",format=(string)RGB,width={},height={}".format(vid_width,vid_height)
caps_str += ",framerate={}/1".format(int(vid_frame_rate))
vcaps = Gst.Caps.from_string(caps_str)
vsrc.set_property("caps", vcaps);
vsrc.set_property("format", Gst.Format.TIME)

# configure appsrc element
caps_str = "meta/x-klv"
caps_str += ",parsed=True"
caps = Gst.Caps.from_string(caps_str)
appsrc.set_property("caps", caps)
# appsrc.connect("need-data", klv_need_data)
appsrc.set_property("format", Gst.Format.TIME)

# configure encoder
encoder.set_property("noise-reduction", 1000)
encoder.set_property("threads", 4)
encoder.set_property("bitrate", 1755)

# configure filesink
filesink.set_property("location", out_file)
filesink.set_property("async", 0)

pipeline = Gst.Pipeline()
pipeline.add(vsrc)
pipeline.add(vqueue)
pipeline.add(vtee)
pipeline.add(appsrc)
pipeline.add(queue_klv)
#pipeline.add(queue_display)
#pipeline.add(vcvt)
#pipeline.add(vsink)
pipeline.add(queue_record)
pipeline.add(vcvt_encoder)
pipeline.add(encoder)
pipeline.add(muxer)
pipeline.add(filesink)

# link video elements
vsrc.link(vqueue)
vqueue.link(vtee)

# link display elements
#vtee.link(queue_display)
#queue_display.link(vcvt)
#vcvt.link(vsink)

# link recording elements
vtee.link(queue_record)
queue_record.link(vcvt_encoder)
vcvt_encoder.link(encoder)
encoder.link(muxer)
muxer.link(filesink)

# link klv elements
appsrc.link(queue_klv)
queue_klv.link(muxer)

pipeline.set_state(Gst.State.PLAYING)

fh = open(klv_file, 'rb')


vid_frame_counter = 0
klv_frame_counter = 0


inject_klv = 0
duration = 1.0 / vid_frame_rate * Gst.SECOND

cap = cv2.VideoCapture(vid_file)

while cap.isOpened():

    try:
        ret, frame = cap.read()
        if ret == False:
            break
        #data = frame.tostring()
        # cap.get(cv2.CAP_PROP_POS_MSEC)\n
        cv2.imwrite(tmp_image,frame)
        # The result video has corrupted image, why?
        # tmp fix using the saved image
        vid_frame = plt.imread(tmp_image)
        data = vid_frame.tostring()
        vidbuf = Gst.Buffer.new_allocate(None, len(data), None)
        vidbuf.fill(0, data)
        vidbuf.duration = duration
        timestamp = vid_frame_counter * duration
        #timestamp = cap.get(cv2.CAP_PROP_POS_MSEC)
        vidbuf.pts = vidbuf.dts = int(timestamp)
        vidbuf.offset = timestamp
        retval = vsrc.emit("push-buffer", vidbuf)

        if retval != Gst.FlowReturn.OK:
            print(retval)
        vid_frame_counter += 1
        inject_klv +=1
        print("video {}".format(vid_frame_counter))
        
        if inject_klv >= vid_frame_rate or vid_frame_counter==1:
            # Inject KLV, We have 1 packet each second. 
            klv_bytes = fh.read(klv_packet_size)
            klvbuf = Gst.Buffer.new_allocate(None, klv_packet_size, None)
            klvbuf.fill(0, klv_bytes)
            timestamp = cap.get(cv2.CAP_PROP_POS_MSEC)
            klvbuf.duration = 1.0  * Gst.SECOND
            klvbuf.pts = klvbuf.dts = int(timestamp)
            klvbuf.offset = timestamp
            retval = appsrc.emit("push-buffer", klvbuf)
            if retval != Gst.FlowReturn.OK:
                print(retval)
            klv_frame_counter += 1
            inject_klv=0
            print("klv {}".format(klv_frame_counter))
        
    except Exception as e:
        print("An exception occurred, video ",e)
        break
    

print("end-of-stream")
vsrc.emit("end-of-stream")
appsrc.emit("end-of-stream")
# Destroy openCV
cap.release()
# Remove temporal image
os.remove(tmp_image)

cv2.destroyAllWindows()
bus = pipeline.get_bus()
 
while True:
    msg = bus.poll(Gst.MessageType.ANY, Gst.CLOCK_TIME_NONE)
    t = msg.type
    if t == Gst.MessageType.EOS:
        print("EOS")
        break
        pipeline.set_state(Gst.State.NULL)
    elif t == Gst.MessageType.ERROR:
        err, debug = msg.parse_error()
        print("Error: %s" % err, debug)
        break
    elif t == Gst.MessageType.WARNING:
        err, debug = msg.parse_warning()
        print("Warning: %s" % err, debug)
    elif t == Gst.MessageType.STATE_CHANGED:
        pass
    elif t == Gst.MessageType.STREAM_STATUS:
        pass
    else:
        pass
        #print(t)
        print("Unknown message: %s" % msg)

pipeline.set_state(Gst.State.NULL)

print("Bye")