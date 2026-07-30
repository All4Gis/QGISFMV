# -*- coding: utf-8 -*-
"""Frame/mosaic/video export, format conversion, bitrate plots, and audio probing."""

import os.path
import subprocess

from qgis.core import Qgis as QGis
from qgis.core import QgsTask
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtWidgets import QFileDialog

from QGISFMV.utils.core.QgsFmvUtils import (
    BurnDrawingsImage,
    GetGeotransform_affine,
    _spawn,
    askForFiles,
    askForFolder,
)
from QGISFMV.utils.layers.QgsFmvExport import (
    exportGroupToGPX,
    exportGroupToKML,
    exportObjectTrack,
)
from QGISFMV.utils.logging import log
from QGISFMV.utils.media.QgsFfmpegProbe import (
    convert_video,
    is_valid_media,
    save_probe_json_task,
    show_probe_json_task,
)
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu

try:
    from osgeo import gdal
except ImportError:
    gdal = None
try:
    import cv2
except ImportError:
    cv2 = None


class ExportController:
    """Own frame/video/mosaic export, format conversion, and audio-availability checks."""

    def __init__(self, player):
        self._player = player

    def hasAudio(self, videoPath):
        """Check if video have Metadata or not
        @type videoPath: String
        @param videoPath: Video file path
        """
        try:
            p = _spawn(
                [
                    "-i",
                    videoPath,
                    "-show_streams",
                    "-select_streams",
                    "a",
                    "-loglevel",
                    "error",
                ],
                t="probe",
            )

            stdout_data, _ = p.communicate(timeout=15)

            if stdout_data == b"":
                return False

            return True
        except subprocess.TimeoutExpired:
            p.kill()
            return False
        except Exception as e:
            log.debug("hasAudio probe failed: %s", e)
            return False

    def checkAudioTask(self, task, videoPath):
        """Background task: probe whether *videoPath* has an audio stream."""
        if task.isCanceled():
            return None
        hasAudio = self.hasAudio(videoPath)
        return {"hasAudio": hasAudio, "videoPath": videoPath}

    def audioCheckFinished(self, e, result=None):
        """Slot: handle audio-probe completion and enable/disable audio actions."""
        player = self._player
        if player.closing:
            return
        if result is not None and result.get("videoPath") not in (
            None,
            player.fileName,
        ):
            return
        if e is not None or result is None:
            player.actionAudio.setEnabled(False)
            player.actionSave_Audio.setEnabled(False)
            player.hasFileAudio = False
            return
        if not result.get("hasAudio"):
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate(
                    "QgsFmvPlayer", "This video doesn't have Audio ! "
                )
            )
            player.actionAudio.setEnabled(False)
            player.actionSave_Audio.setEnabled(False)
            player.hasFileAudio = False
            return
        player.hasFileAudio = True
        player.actionAudio.setEnabled(True)
        player.actionSave_Audio.setEnabled(True)

    def saveInfoToJson(self):
        """Save video Info to json"""
        player = self._player
        media_path = player._probe_media_path()
        if not media_path:
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate("QgsFmvPlayer", "No video file loaded."),
                level=QGis.MessageLevel.Warning,
            )
            return

        out_json, _ = askForFiles(
            player._dialog_parent(),
            QCoreApplication.translate("QgsFmvPlayer", "Save Json"),
            isSave=True,
            exts="json",
        )

        if not out_json:
            return

        player._add_background_task(
            QgsTask.fromFunction(
                "Save Video Info to Json Task",
                save_probe_json_task,
                fname=media_path,
                output=out_json,
                on_finished=player.taskResults.finishedTask,
                flags=QgsTask.Flag.CanCancel,
            )
        )
        return

    def showVideoInfo(self, checked=False):
        """Show default probe info"""
        player = self._player
        media_path = player._probe_media_path()
        if not media_path:
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate("QgsFmvPlayer", "No video file loaded."),
                level=QGis.MessageLevel.Warning,
            )
            return

        player._add_background_task(
            QgsTask.fromFunction(
                "Show Video Info Task",
                show_probe_json_task,
                fname=media_path,
                on_finished=player.taskResults.finishedTask,
                flags=QgsTask.Flag.CanCancel,
            )
        )
        return

    def showVideoInfoDialog(self, outjson):
        """Show Video Information Dialog
        @type outjson: QByteArray
        @param outjson: Json file data
        """
        from QGISFMV.player.dialogs.QgsFmvVideoInfo import VideoInfoDialog

        player = self._player
        if outjson is None:
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate(
                    "QgsFmvPlayer", "Could not read video information."
                ),
                level=QGis.MessageLevel.Warning,
            )
            return

        dlg = VideoInfoDialog(player._dialog_parent())
        if not dlg.load_json(outjson):
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate(
                    "QgsFmvPlayer", "Could not parse video information."
                ),
                level=QGis.MessageLevel.Warning,
            )
            return

        dlg.setWindowTitle(
            QCoreApplication.translate("QgsFmvPlayer", "Video Information : ")
            + player.fileName
        )
        dlg.expand_all()
        # Size comes from ui_FmvVideoInfo.ui
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        player.VideoInfoDialog = dlg

    def convertVideoTask(self, task, infile, outfile):
        """Background task: convert *infile* to *outfile* via ffmpeg."""
        if task.isCanceled():
            return None
        if not is_valid_media(infile):
            raise ValueError(
                QCoreApplication.translate(
                    "QgsFmvPlayer", "Could not probe video file."
                )
            )
        return convert_video(task, infile, outfile)

    def convertVideo(self):
        """Convert Video To Other Format"""
        player = self._player
        out, _ = askForFiles(
            player._dialog_parent(),
            QCoreApplication.translate("QgsFmvPlayer", "Save Video as..."),
            isSave=True,
            exts=["mp4", "ogg", "avi", "mkv", "webm", "flv", "mov", "mpg", "mp3"],
        )

        if not out:
            return

        player._add_background_task(
            QgsTask.fromFunction(
                "Converting Video Task",
                self.convertVideoTask,
                infile=player.fileName,
                outfile=out,
                on_finished=player.taskResults.finishedTask,
                flags=QgsTask.Flag.CanCancel,
            )
        )

    def CreateBitratePlot(self, checked=False):
        """Create video Plot Bitrate Thread"""
        player = self._player
        sender = player.sender()
        senderName = sender.objectName() if sender is not None else ""

        if not player.fileName or not os.path.isfile(player.fileName):
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate("QgsFmvPlayer", "No video file loaded."),
                level=QGis.MessageLevel.Warning,
            )
            return

        task_name = ""
        output = None
        plot_type = ""
        if senderName == "actionAudio":
            task_name = "Show Audio Bitrate"
            plot_type = "audio"
        elif senderName == "actionVideo":
            task_name = "Show Video Bitrate"
            plot_type = "video"
        elif senderName == "actionSave_Audio":
            fileaudio, _ = askForFiles(
                player._dialog_parent(),
                QCoreApplication.translate("QgsFmvPlayer", "Save Audio Bitrate Plot"),
                isSave=True,
                exts=["png", "pdf", "pgf", "eps", "ps", "raw", "rgba", "svg", "svgz"],
            )
            if not fileaudio:
                return
            task_name = "Save Action Audio Bitrate"
            output = fileaudio
            plot_type = "audio"
        elif senderName == "actionSave_Video":
            filevideo, _ = askForFiles(
                player._dialog_parent(),
                QCoreApplication.translate("QgsFmvPlayer", "Save Video Bitrate Plot"),
                isSave=True,
                exts=["png", "pdf", "pgf", "eps", "ps", "raw", "rgba", "svg", "svgz"],
            )
            if not filevideo:
                return
            task_name = "Save Action Video Bitrate"
            output = filevideo
            plot_type = "video"
        else:
            qgsu.showUserAndLogMessage(
                "", "Unknown bitrate plot action: " + senderName, onlyLog=True
            )
            return

        player._add_background_task(
            QgsTask.fromFunction(
                task_name,
                player.BitratePlot.CreatePlot,
                fileName=player.fileName,
                output=output,
                t=plot_type,
                on_finished=player.taskResults.finishedTask,
                flags=QgsTask.Flag.CanCancel,
            )
        )

    def ExtractAllFrames(self):
        """Extract All Video Frames Task"""
        player = self._player
        directory = askForFolder(
            player._dialog_parent(),
            QCoreApplication.translate("QgsFmvPlayer", "Save all Frames"),
            options=QFileDialog.Option.DontResolveSymlinks
            | QFileDialog.Option.ShowDirsOnly,
        )

        if directory:
            player._add_background_task(
                QgsTask.fromFunction(
                    "Save All Frames Task",
                    self.SaveAllFrames,
                    fileName=player.fileName,
                    directory=directory,
                    on_finished=player.taskResults.finishedTask,
                    flags=QgsTask.Flag.CanCancel,
                )
            )
        return

    def SaveAllFrames(self, task, fileName, directory):
        """Extract and save all video frames into directory"""
        # Try OpenCV first (fast, frame-by-frame with progress)
        if cv2 is not None:
            return self._saveAllFramesCv2(task, fileName, directory)
        # Fallback: use FFmpeg subprocess
        return self._saveAllFramesFfmpeg(task, fileName, directory)

    def _saveAllFramesCv2(self, task, fileName, directory):
        vidcap = cv2.VideoCapture(fileName)
        length = int(vidcap.get(cv2.CAP_PROP_FRAME_COUNT))
        count = 0
        while not task.isCanceled():
            success, image = vidcap.read()
            if not success or image is None:
                break
            cv2.imwrite(os.path.join(directory, f"frame_{count:06d}.jpg"), image)
            if length > 0:
                task.setProgress(count * 100 / length)
            count += 1
        vidcap.release()
        cv2.destroyAllWindows()
        if task.isCanceled():
            return None
        return {"task": task.description()}

    def _saveAllFramesFfmpeg(self, task, fileName, directory):
        from QGISFMV.utils.media.QgsFfmpegRunner import available, popen_ffmpeg

        if not available():
            return {"task": task.description(), "error": "FFmpeg is not configured"}

        out_pattern = os.path.join(directory, "frame_%06d.jpg")
        try:
            proc = popen_ffmpeg(
                [
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    fileName,
                    "-vsync",
                    "0",
                    out_pattern,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except RuntimeError as exc:
            return {"task": task.description(), "error": str(exc)}
        try:
            _, stderr_data = proc.communicate(timeout=600)
        except subprocess.TimeoutExpired:
            proc.kill()
            return {
                "task": task.description(),
                "error": "Frame extraction timed out after 10 minutes.",
            }
        if task.isCanceled():
            return None
        if proc.returncode != 0:
            err = stderr_data.decode("utf-8", errors="replace") if stderr_data else ""
            return {"task": task.description(), "error": f"FFmpeg failed: {err}"}
        return {"task": task.description()}

    def ExtractCurrentFrame(self):
        """Extract Current Frame Task
        The drawings are saved by default
        """
        player = self._player
        image = BurnDrawingsImage(
            player.videoWidget.currentFrame(),
            player.videoWidget.grab(player.videoWidget.surface.videoRect()).toImage(),
        )

        output, _ = askForFiles(
            player._dialog_parent(),
            QCoreApplication.translate("QgsFmvPlayer", "Save Current Frame"),
            isSave=True,
            exts=["png", "jpg", "bmp", "tiff"],
        )

        if not output:
            return

        player._add_background_task(
            QgsTask.fromFunction(
                "Save Current Frame Task",
                self.SaveCapture,
                image=image,
                output=output,
                on_finished=player.taskResults.finishedTask,
                flags=QgsTask.Flag.CanCancel,
            )
        )
        return

    def SaveCapture(self, task, image, output):
        """Save Current Frame"""
        image.save(output)
        if task.isCanceled():
            return None
        return {"task": task.description()}

    def ExtractCurrentGeoFrame(self):
        """Extract Current GeoReferenced Frame Task"""
        player = self._player
        image = BurnDrawingsImage(
            player.videoWidget.currentFrame(),
            player.videoWidget.grab(player.videoWidget.surface.videoRect()).toImage(),
        )

        geotransform = GetGeotransform_affine()
        position = str(player.player.position())
        directory = askForFolder(
            player._dialog_parent(),
            QCoreApplication.translate(
                "QgsFmvPlayer", "Save Current Georeferenced Frame"
            ),
            options=QFileDialog.Option.DontResolveSymlinks
            | QFileDialog.Option.ShowDirsOnly,
        )

        if not directory:
            return

        player._add_background_task(
            QgsTask.fromFunction(
                "Save Current Georeferenced Frame Task",
                self.SaveGeoCapture,
                image=image,
                output=directory,
                p=position,
                geotransform=geotransform,
                on_finished=player.taskResults.finishedTask,
                flags=QgsTask.Flag.CanCancel,
            )
        )
        return

    def SaveGeoCapture(self, task, image, output, p, geotransform):
        """Save Current GeoReferenced Frame"""
        if gdal is None:
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate(
                    "QgsFmvPlayer",
                    "GDAL is not available; cannot save georeferenced frame.",
                )
            )
            return
        ext = ".tiff"
        t = "out_" + p + ext
        name = "g_" + p
        src_file = os.path.join(output, t)

        image.save(src_file)

        # Opens source dataset
        src_ds = gdal.OpenEx(
            src_file,
            gdal.OF_RASTER | gdal.OF_READONLY,
            open_options=["NUM_THREADS=ALL_CPUS"],
        )
        if src_ds is None:
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate(
                    "QgsFmvPlayer", "Could not open frame for georeferencing."
                )
            )
            return

        # Open destination dataset
        dst_filename = os.path.join(output, name + ext)
        dst_ds = gdal.GetDriverByName("GTiff").CreateCopy(
            dst_filename,
            src_ds,
            0,
            options=[
                "TILED=NO",
                "BIGTIFF=NO",
                "COMPRESS_OVERVIEW=DEFLATE",
                "COMPRESS=LZW",
                "NUM_THREADS=ALL_CPUS",
                "predictor=2",
            ],
        )
        src_ds = None
        from QGISFMV.utils.core.QgsFmvUtils import _get_wgs84_srs

        dst_ds.SetProjection(_get_wgs84_srs().ExportToWkt())

        # Set location
        dst_ds.SetGeoTransform(geotransform)
        dst_ds.GetRasterBand(1).SetNoDataValue(0)
        dst_ds.FlushCache()
        # Close files
        dst_ds = None
        os.remove(src_file)
        if task.isCanceled():
            return None
        return {"task": task.description(), "file": dst_filename}

    def exportToKML(self):
        """Export the current video layers to KML."""
        player = self._player
        exportGroupToKML(group_name=player._videoGroupName())

    def exportToGPX(self):
        """Export the current video layers to GPX."""
        player = self._player
        exportGroupToGPX(group_name=player._videoGroupName())

    def exportObjectTrack(self):
        """Export the object track layer to KML."""
        player = self._player
        exportObjectTrack(
            parent=player._dialog_parent(), group_name=player._videoGroupName()
        )
