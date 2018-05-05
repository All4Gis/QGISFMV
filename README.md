# QGIS Full Motion Video (FMV) #
 
![a](images/banner.png)

Plugin for QGIS > 2.99 which allows to analyze, visualize and process videos inside the QGIS environment. QGIS FMV accepts multiple video formats such as mp4, ts, avi, etc. It is also able to extract video frames, to capture the current frame, to plot bitrate and to observe the video metadata with aerial images and more. It also offers the possibility to create reports with video metadata.

Standards supported:

  - "UAS Datalink Local Set", [ST0601.11](http://www.gwg.nga.mil/misb/docs/standards/ST0601.8.pdf)

  
## Motivation

This development arises after observing that there was no free solution for the metadata extraction and video analysis in real time. All solutions are APIs or private tools such as
[Esri](http://www.esri.com/products/arcgis-capabilities/imagery/full-motion-video),
for this reason, I decided to develop this open source project and, this way, offer this open source alternative to the QGIS community.


## Dependencies

* [FFMPEG](http://ffmpeg.org/download.html) : After downloading it, you should store it in an accessible folder and modify `config.py` with the corresponding path.

* [OpenCV](https://opencv.org/) : `python3 -m pip install opencv-python`

* [MatPlotLib](https://matplotlib.org/) : `python3 -m pip install matplotlib`

* [Klvdata](https://github.com/paretech/klvdata) : customized version of this library.

The plugin install automatically this requisites,but you can install it using:

`python3 -m pip install -r requirements.txt`


## For show video

To see the video you need:

  - Linux: `sudo apt-get install gst123` (install GStreamer dependencies)
  - Window: install LAV Filters (install <a href="https://github.com/Nevcairiel/LAVFilters/releases" target="_blank">DirectShow Media Decoders</a>) 


## Usage

The use of this application is simple. It only needs a video with metadata, like for example one of these [videos](http://samples.ffmpeg.org/MPEG2/mpegts-klv/) or [these](https://drive.google.com/open?id=1-B2uaW7_cfYZohZYFozrgBhIaztI1MSP)
Then, open the plugin where the "video manager" will be shown, open the video and with a double-click, the "player" will be opened. 
At this moment, you will see that new shapes have been added and you will see the platform position, metadata, etc.


## Recommended readings

For more information about the Unmanned Air System (UAS) metadata from STANAG 4609

![a](images/demux.png)

* <a href="http://www.gwg.nga.mil/misb/faq.html" target="_blank">FAQ</a>
* <a href="http://www.gwg.nga.mil/misb/docs/nato_docs/STANAG_4609_Ed3.pdf" target="_blank">STANAG_4609_Ed3</a>
* <a href="http://www.gwg.nga.mil/misb/docs/standards/ST0601.11.pdf" target="_blank">ST0601.11</a>
* <a href="http://www.gwg.nga.mil/misb/docs/standards/ST0902.1.pdf" target="_blank">ST0902.1</a>

## Installation  TODO: Revisar

La instalacion puede realizarla desde el ejecutable si esta en windows o desde el zip desde el 
administrador de complementos de QGIS


## Screenshots

![a](images/Screenshot0.png)


## Features

- Convert videos to other format
- Extract metadata from video file
- Show Platform,trajectory and beams position in a QGIS
- Possibility of extracting parts of the video
- Change of color, contrast, etc. of the video
- Capture of the current frame
- Extraction of all frames of the video
- Extrac lon/lat cursor coordinates
- Apply sobel filters, edge detection ...


## TODO

* Open videos via UDP / TCP
* Possibility of drawing on the video and create shapes

....


## Contributing

Contributions are welcome!

Want to work on the project? Any kind of contribution is welcome!

Follow these steps:

	Fork the project.
	Create a new branch.
	Make your changes and write tests ( if is possible).
	Commit your changes to the new branch.
	Send a pull request.
	
And thanks for your code.


## License

GNU Public License (GPL) Version 3

**Free Software, Hell Yeah!**


## Contributors List

* <a href="https://all4gis.github.io//" target="_blank">Fran Raga</a>


## Donations

Want to buy me a beer (or gadget)? Please use Paypal button on the project page, [![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.me/all4gis) , or contact me directly.

[![paypal](https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/cgi-bin/webscr?button=donate&business=5329N9XX4WQHY&item_name=QGIS+FMV+Plugin&quantity=&amount=&currency_code=EUR&shipping=&tax=&notify_url=&cmd=_donations&bn=JavaScriptButton_donate&env=www)
 
If this plugin is useful for you, consider to donate to the author.


[© All4gis 2018]



