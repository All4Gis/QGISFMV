# QGIS Full Motion Video (FMV) #

[![Build Status](https://travis-ci.org/All4Gis/QGISFMV.svg?branch=master)](https://travis-ci.org/All4Gis/QGISFMV)

![a](images/banner.png)

Plugin for **QGIS > 2.99** which allows to analyze, visualize and process videos inside the QGIS environment. **QGIS FMV** accepts multiple video formats such as _mp4, ts, avi_, etc. It is also able to extract video frames, to capture the current frame, to plot bitrate and to observe the video metadata with aerial images and more. It also offers the possibility to create reports with video metadata.

Standards supported:

  - "UAS Datalink Local Set", [ST0601.11](http://www.gwg.nga.mil/misb/docs/standards/ST0601.11.pdf)

## Table of Contents

- [Motivation](#motivation)
- [Dependencies](#dependencies)
- [For show video](#for-show-video)
- [Usage](#usage)
- [Recommended readings](#recommended-readings)
- [Installation](#installation)
    - [Installation on Windows](#installation-on-windows)
    - [Installation on Archlinux](#installation-on-archlinux)
- [Slides](#slides)
- [Screenshots](#screenshots)
- [Features](#features)
- [Contributing](#contributing)
    - [Contributing Code](#contributing-code)
    - [Contributing translations](#contributing-translations)
	- [Contributors List](#contributors-list)
- [License](#license)
- [Donations](#donations)
	
## Motivation

This development arises after observing that there was no free solution for the metadata extraction and video analysis in real time. All solutions are APIs or private tools such as
[Esri](http://www.esri.com/products/arcgis-capabilities/imagery/full-motion-video),
for this reason, I decided to develop this open source project and, this way, offer this open source alternative to the QGIS community.

&uparrow; [Back to top](#table-of-contents)

## Dependencies

* [FFMPEG](http://ffmpeg.org/download.html) : After downloading it, you should store it in an accessible folder and modify `fmvConfig.py` with the corresponding path.For example 'D://FFMPEG'

* [OpenCV](https://opencv.org/) : `python3 -m pip install opencv-python`

* [opencv-contrib-python](https://pypi.org/project/opencv-contrib-python/) : `python3 -m pip install opencv-contrib-python`

* [MatPlotLib](https://matplotlib.org/) : `python3 -m pip install matplotlib`

* [Klvdata](https://github.com/paretech/klvdata) : customized version of this library.

* [Homography](https://github.com/satellogic/homography) : `python3 -m pip install homography`

The plugin install automatically this requisites,but you can install it using:

`python3 -m pip install -r requirements.txt`

&uparrow; [Back to top](#table-of-contents)

## For show video

To see the video you need:

  - **Linux**: `sudo apt-get install gst123` (install GStreamer dependencies)
  - **Window**: install LAV Filters (install <a href="https://github.com/Nevcairiel/LAVFilters/releases" target="_blank">DirectShow Media Decoders</a>) 

&uparrow; [Back to top](#table-of-contents)

## Usage

The use of this application is simple.
It only needs a video with metadata, like for example one of these [(ESRI copyright)](https://drive.google.com/open?id=1-B2uaW7_cfYZohZYFozrgBhIaztI1MSP)
Then, open the plugin where the "video manager" will be shown, open the video and with a double-click, the "player" will be opened. 
At this moment, you will see that new shapes have been added and you will see the platform position, metadata, etc.

[Link to Usage Documentation!](https://all4gis.github.io/QGISFMV/Using)

&uparrow; [Back to top](#table-of-contents)

## Recommended readings

For more information about the Unmanned Air System (UAS) metadata from STANAG 4609

![a](images/demux.png)

* <a href="http://www.gwg.nga.mil/misb/faq.html" target="_blank">FAQ</a>
* <a href="http://www.gwg.nga.mil/misb/docs/nato_docs/STANAG_4609_Ed3.pdf" target="_blank">STANAG_4609_Ed3</a>
* <a href="http://www.gwg.nga.mil/misb/docs/standards/ST0601.13.pdf" target="_blank">ST0601.13</a>
* <a href="http://www.gwg.nga.mil/misb/docs/standards/ST0902.1.pdf" target="_blank">ST0902.1</a>

&uparrow; [Back to top](#table-of-contents)

## Installation

The installation can be done from the executable if it is in windows or from the zip

&uparrow; [Back to top](#table-of-contents)

## Installation on Windows

Windows automatically installs all, with user permission,If an error occurs, you should perform some checks.

[![Watch the video (Spanish)](https://i.imgur.com/vXpMJhS.png)](https://youtu.be/9C973pz5i6k "Como usa QGISFMV en windows")

## Installation on Archlinux

_Archlinux installation :_ 
```
pacman -S qgis python-matplotlib opencv ffmpeg 
pip install homography
```

_FFmpeg path_
```
ffmpeg = "/usr/bin/"
ffprobe = "/usr/bin/"
```

## Slides

* [Official presentation](https://slides.com/franraga/qgis-fmv/fullscreen)
* [Beyond imagery and Video](https://docs.google.com/presentation/d/e/2PACX-1vTKcb4AV71yapX2hrOCIUCCvdP0FIOUqO1OvfEG4cHKvo0wvVM9pmIA0vMuzLXVANmhySRlFOgTAHGf/pub?start=true&loop=false&delayms=10000&slide=id.p1)

&uparrow; [Back to top](#table-of-contents)

## Screenshots

![a](images/Screenshot0.png)

&uparrow; [Back to top](#table-of-contents)

## Features

- Convert videos to other format
- Extract metadata from video file
- Show Platform,Trajectory,Footprint and beams position in a QGIS
- Possibility of extracting parts of the video
- Capture of the current frame
- Extraction of all frames of the video
- Extract lon/lat/alt cursor coordinates
- Apply sobel filters, edge detection ...

&uparrow; [Back to top](#table-of-contents)

## Contributing

Contributions are welcome!

&uparrow; [Back to top](#table-of-contents)

### Contributing Code

Want to work on the project? Any kind of contribution is welcome!

Follow these steps:

	Fork the project.
	Create a new branch.
	Make your changes and write tests ( if is possible).
	Commit your changes to the new branch.
	Send a pull request.
	
See before [FMV Coding Standards!](https://all4gis.github.io/QGISFMV/CodingStandards)
	
And thanks for your code.

![a](images/thanks.gif)

### Contributing translations

Contributions are welcome!

[transifex](https://www.transifex.com/all4gis/QGISFMV/)

### Contributors List  

* <a href="https://github.com/ltbam" target="_blank">ltbam</a>
* <a href="https://all4gis.github.io//" target="_blank">Fran Raga</a>


## License

GNU Public License (GPL) Version 3

**Free Software, Hell Yeah!**


## Donations

Want to buy me a beer (or gadget)? Please use Paypal button on the project page, [![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.me/all4gis) , or contact me directly.

[![paypal](https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/cgi-bin/webscr?button=donate&business=5329N9XX4WQHY&item_name=QGIS+FMV+Plugin&quantity=&amount=&currency_code=EUR&shipping=&tax=&notify_url=&cmd=_donations&bn=JavaScriptButton_donate&env=www)
 
If this plugin is useful for you, consider to donate to the author.

&uparrow; [Back to top](#table-of-contents)

[© All4gis 2018]