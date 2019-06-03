
# How use QGIS FMV #

For the use of the QGIS FMV plugin you must have the [requirements](../index.md#dependencies) previously installed.

Once you have them, click on the icon that will appear in QGIS, to open the manager.  ![](code/images/icon.png)

# Table of Contents

- [Video Manager](#video-manager)
- [Video Player](#video-player)
	- [General Tools](#general-tools)
	- [Utils Toolbar](#utils-toolbar)
	- [Customize Plugin](#customize-plugin)
- [Shortcuts](#shortcuts)

##  Video Manager

From the manager, you can open and manage your play list.
For adding a video, simply click on **File -> Open Video File** and select a video from the dialog window to add it to the play list.
If you want to play a video after adding it to the play list, *double-click* on any video in the manager and the player will be opened playing the selected video. 
For playing another video, it is not necessary to close the player, just click on a different video and it will be played.

![](images/remove.png)

If you want to remove it from the list, click on the selected video, click on the mouse right button hover on row that you want and then on **Remove fron list**.

## Video Player

The player is the plugin core and the most important part. 

### General Tools

The options offered are the following:

- **Filters**: This option applies the selected filter on the video in real time.

![](images/filters.png)

- **Frames**: This option extracts the current frame, all the frames of the video or capture current georeferenced frame. To do it, you have to select one of these options and to select the destination directory; 
then, a background process will start that will store the current frame or all the video frames in this folder.

- ![](code/images/show-metadata.png)**Metadata**: This option opens a dock, where you can see the information extracted from the video.This dock can move where we want.

![](images/metadata_dock.png)

If we want to save the information about the current frame we can do it in a **.csv** file or in a more elaborated report in **.pdf**.
For them, simply click on **Save** and select option.

![](images/save_report.png)

- ![](code/images/video-converter.png)**Conversion**: This option allows to convert the video into a different format. To do it, you have to select the corresponding extension in the save dialog window.

- ![](code/images/video-info.png)**Video information**: This option allows to save the video information in json format o to show the information in a dialog window.

![](images/video_info.png)

- ![](code/images/show-bitrate.png)**Plot**: This option allows to show or save the information about the audio or video channels.If the video has no audio, the audio options are disabled.

- **Map**: This option centers the map on the platform, footprint or target.If we deactivate any of the options, the centering is free for the user.

- ![](code/images/record.png)**Record**: This option extracts parts of the video and store them in the destination directory.

- ![](code/images/mosaic.png)**Mosaic**: This option extracts all the georeferenced frames in real time and adds them to the canvas in a new group. While the button is checked its function is performed.

- **Cursor Coordinates**: This option allows you to see the cursor coordinates in WGS84 or MGRS (Military Grid Reference System).

![](images/cursor_coordinates.png)

The player also offers the typical options such as stop, rewind, fast-forward, go to the first or last frame and volume controller.

![](images/player.png)

If we want to hide these options, simply click on ![](code/images/down.png) and If we right click on the video we can see a menu, with the options that we see in the following image.

![](images/contextMenu.png)


### Utils Toolbar

The utility bar offers us tools to interact with the video. This bar can hide it if we right click and unchecking the option "Utils Toolbar".

![](images/hide_draw_toolbar.png)

If on the contrary we want to leave it but we don't like where it is, we can move it where we want.

![](images/willmove_draw_toolbar.png)

And we release it where we want,

![](images/moved_draw_toolbar.png)

The options offered are the following:

- ![](code/images/magnifier-glass.png)**Magnifying Glass**: This option zooms the part of the video in which the magnifying glass is located. To use it, we can left click on the video or if we want to move it fluidly,, we must keep pressing the left click and move the mouse. We can change its shape between circle and square.

![](images/magnifier.png)

- ![](code/images/draw-polygon.png)**Draw Polygon**: This option allows you to draw a polygon on the video. This drawing will be drawn on the canvas too. We can erase the last drawing or all.

- ![](code/images/draw-point.png)**Draw Point**: This option allows you to draw a point on the video. This drawing will be drawn on the canvas too. We can erase the last drawing or all.

- ![](code/images/draw-polyline.png)**Draw Polyline**: This option allows you to draw a polyline on the video. This drawing will be drawn on the canvas too. We can erase the last drawing or all.

- ![](code/images/ruler.png)**Measure Distance**: This option allows us to measure the distance in meters over the video.

- ![](code/images/ruler_surface.png)**Measure Area**: This option allows us to measure the area in square meters and square kilometers over the video.

- ![](code/images/censure-pencil.png)**Censure**: This option allows you to draw a black area on the video. This drawing will be drawn on the canvas too. We can erase the last drawing or all.

- ![](code/images/rubber-stamp.png)**Stamp**: This option allows us to put the "Confidential" mark on the video.

- ![](code/images/object-tracking.png)**Object Tracking**: This option allows us to make a rectangle on the video and follow an object. The trajectory of the object followed is painted on the canvas.

### Customize Plugin

In this option we can modify the parameters of the magnifying glass and the drawing parameters.
To access this menu we must right click and select the option **Options**.

![](images/contextMenu.png)

And magnifying glass options tab,

![](images/customize_magnifier.png)

And drawings options tab,

![](images/customize_drawings.png)

These values are saved in the general configuration of QGIS,so if you want to return to the original colors of the plugin, you must select **Default color**

![](images/select_color2.png)


## Shortcuts

Some options are also available through keyboard shortcuts and clicking on the mouse right button on the video.

| Shortcut Keys | Description |
| ------ | ------ |
| Alt+F | Open FMV |
| Alt+A | Show about |
| Ctrl+T | show metadata/telemetry dock |
| Ctrl+R | Record Video |
| Ctrl+M | Create mosaic from video |
| Ctrl+Q | Capture Current Frame |
| Ctrl+U | Mute/Unmute |
| Ctrl+A | Extract All Frames |
| Ctrl+Shift+P | Save metadata/telemetry as PDF |
| Ctrl+Shift+C | Save metadata/telemetry as CSV |
| Ctrl+Left | Start Of Media |
| Left | Rewind |
| Ctrl+S | Stop |
| Ctrl+P | Play/Pause |
| Right | Forward |
| Ctrl+Right | End Of Media |
| Ctrl+L | Repeat |


*Enjoy!*
