import matplotlib.pyplot as plt
import os
import gi


# Video width/Height
# ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 DJI_0047.MP4 
# width 3840x  height 2160

# Get Framet rate
# ffprobe -v error -select_streams v -of default=noprint_wrappers=1:nokey=1 -show_entries stream=r_frame_rate DJI_0047.MP4 

# Extract frames
# ffmpeg -i DJI_0047.MP4  -vf fps=1/29.97 %.1f.jpg
# ffmpeg -i DJI_0047.MP4 -r 1/1 %1d.jpg

# ffmpeg -i DJI_0047/DJI_0047.MP4 -i test.mp4 -c copy -map 0:v:0 -map 1:d:0 out.mp4



# import glob
# 
# files = []
# for file in glob.glob("/home/fragalop/SamplesFMV/multiplex/klv/*.klv"):
#     files.append(file)
# 
# out_data = b''
# for fn in files:
#     with open(fn, 'rb') as fp:
#         out_data += fp.read()
# with open('/home/fragalop/SamplesFMV/multiplex/all.klv', 'wb') as fp:
#     fp.write(out_data)

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject

vid_frames_folder = "/home/fragalop/SamplesFMV/multiplex/frames"
vid_frame_rate = 29.97
vid_width = 3840
vid_height = 2160
klv_file = "/home/fragalop/SamplesFMV/multiplex/all.klv"
klv_frame_rate = 30
klv_packet_size = 129
out_file = "/home/fragalop/SamplesFMV/multiplex/test2.mp4"


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
timestamp = 0

klv_done = False
vid_done = False
vid_frame_counter = 0
klv_frame_counter = 0

t = 0
last_klv_t = 0
last_vid_t = 0
while True:
    if vid_done and klv_done:
        break
    if t - last_klv_t >= 1.0 / klv_frame_rate:
        if not klv_done:
            klv_bytes = fh.read(klv_packet_size)
            if klv_bytes:
                klvbuf = Gst.Buffer.new_allocate(None, klv_packet_size, None)
                klvbuf.fill(0, klv_bytes)
                klvbuf.pts = int(t * 1e9)
                klvbuf.dts = int(t * 1e9)

                appsrc.emit("push-buffer", klvbuf)
                klv_frame_counter += 1
                last_klv_t = t
                print("klv {} {}".format(klv_frame_counter, last_klv_t))
            else:
                klv_done = True

    if t - last_vid_t >= 1.0 / vid_frame_rate:
        if not vid_done:
            frame_filename = '%s/%1d.jpg' % (vid_frames_folder, vid_frame_counter + 1)
            if os.path.isfile(frame_filename):
                vid_frame = plt.imread(frame_filename)
                data = vid_frame.tostring()
                vidbuf = Gst.Buffer.new_allocate(None, len(data), None)
                vidbuf.fill(0, data)
                vidbuf.pts = int(t * 1e9)
                vidbuf.dts = int(t * 1e9)

                vsrc.emit("push-buffer", vidbuf)
                vid_frame_counter += 1
                last_vid_t = t
                print("vid {} {}".format(vid_frame_counter, last_vid_t))
            else:
                vid_done = True
                continue

    t += 0.000001
    #print(t)

vsrc.emit("end-of-stream")
appsrc.emit("end-of-stream")

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
        #print("Error: %s" % err, debug)
        break
    elif t == Gst.MessageType.WARNING:
        err, debug = msg.parse_warning()
        #print("Warning: %s" % err, debug)
    elif t == Gst.MessageType.STATE_CHANGED:
        pass
    elif t == Gst.MessageType.STREAM_STATUS:
        pass
    else:
        pass
        #print(t)
        #print("Unknown message: %s" % msg)

pipeline.set_state(Gst.State.NULL)

print("Bye")
