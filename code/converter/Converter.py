# Original Code : https://github.com/senko/python-video-converter
# Modificated for work in QGIS FMV Plugin

import traceback

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from QGIS_FMV.converter.avcodecs import (video_codec_list,
                                         audio_codec_list,
                                         subtitle_codec_list)
from QGIS_FMV.converter.ffmpeg import FFMpeg
from QGIS_FMV.converter.formats import format_list
from QGIS_FMV.utils.QgsFmvLog import log


try:
    from pydevd import *
except ImportError:
    None


class Converter(QObject):

    finished = pyqtSignal(str, str)
    finishedJson = pyqtSignal(str, str, bytes)
    error = pyqtSignal(str, Exception, basestring)
    progress = pyqtSignal(float)

    video_codecs = {}
    audio_codecs = {}
    subtitle_codecs = {}
    formats = {}

    for cls in audio_codec_list:
        name = cls.codec_name
        audio_codecs[name] = cls

    for cls in video_codec_list:
        name = cls.codec_name
        video_codecs[name] = cls

    for cls in subtitle_codec_list:
        name = cls.codec_name
        subtitle_codecs[name] = cls

    for cls in format_list:
        name = cls.format_name
        formats[name] = cls

    def parse_options(self, opt, twopass=None):

        f = opt['format']
        if f not in self.formats:
            log.error('Requested unknown format: ' + str(f))

        format_options = self.formats[f]().parse_options(opt)
        if format_options is None:
            log.error('Unknown container format error')

        ''' audio options'''
        if 'audio' not in opt or twopass == 1:
            opt_audio = {'codec': None}
        else:
            opt_audio = opt['audio']
            if not isinstance(opt_audio, dict) or 'codec' not in opt_audio:
                log.error('Invalid audio codec specification')

        c = opt_audio['codec']
        if c not in self.audio_codecs:
            log.error('Requested unknown audio codec ' + str(c))

        audio_options = self.audio_codecs[c]().parse_options(opt_audio)
        if audio_options is None:
            log.error('Unknown audio codec error')

        ''' video options'''
        if 'video' not in opt:
            opt_video = {'codec': None}
        else:
            opt_video = opt['video']
            if not isinstance(opt_video, dict) or 'codec' not in opt_video:
                log.error('Invalid video codec specification')

        c = opt_video['codec']
        if c not in self.video_codecs:
            log.error('Requested unknown video codec ' + str(c))

        video_options = self.video_codecs[c]().parse_options(opt_video)
        if video_options is None:
            log.error('Unknown video codec error')

        if 'subtitle' not in opt:
            opt_subtitle = {'codec': None}
        else:
            opt_subtitle = opt['subtitle']
            if not isinstance(opt_subtitle, dict) or 'codec' not in opt_subtitle:
                log.error('Invalid subtitle codec specification')

        c = opt_subtitle['codec']
        if c not in self.subtitle_codecs:
            log.error('Requested unknown subtitle codec ' + str(c))

        subtitle_options = self.subtitle_codecs[c](
        ).parse_options(opt_subtitle)
        if subtitle_options is None:
            log.error('Unknown subtitle codec error')

        ''' aggregate all options'''
        optlist = audio_options + video_options + subtitle_options + format_options

        if twopass == 1:
            optlist.extend(['-pass', '1'])
        elif twopass == 2:
            optlist.extend(['-pass', '2'])

        return optlist

    @pyqtSlot(str, str, dict, bool)
    def convert(self, infile, outfile, options, twopass):
        try:
            timeout = 10

            self.ffmpeg = FFMpeg()
            info = self.ffmpeg.probe(infile)
            if info is None:
                self.error.emit(
                    "convert", "", "Can't get information about source file")

            if not info.video and not info.audio:
                self.error.emit(
                    "convert", "", 'Source file has no audio or video streams')

            if info.video and 'video' in options:
                options = options.copy()
                v = options['video'] = options['video'].copy()
                v['src_width'] = info.video.video_width
                v['src_height'] = info.video.video_height

            if info.format.duration < 0.01:
                self.error.emit("convert", "", 'Zero-length media')

            if twopass:
                optlist1 = self.parse_options(options, 1)
                for timecode in self.ffmpeg.convert(infile, outfile, optlist1,
                                                    timeout=timeout):
                    self.progress.emit(
                        int((50.0 * timecode) / info.format.duration))

                optlist2 = self.parse_options(options, 2)
                for timecode in self.ffmpeg.convert(infile, outfile, optlist2,
                                                    timeout=timeout):
                    self.progress.emit(
                        int(50.0 + (50.0 * timecode) / info.format.duration))
            else:
                optlist = self.parse_options(options, twopass)
                for timecode in self.ffmpeg.convert(infile, outfile, optlist,
                                                    timeout=timeout):
                    self.progress.emit(
                        int((100.0 * timecode) / info.format.duration))
            self.progress.emit(100)
            self.finished.emit("convert", "convert correct Finished!")
        except Exception as e:
            self.error.emit("convert", e, traceback.format_exc())
            return

    @pyqtSlot(str, str)
    def probeToJson(self, fname, output=None):
        try:
            self.ffmpeg = FFMpeg()
            self.ffmpeg.probeToJson(fname, output)
            self.finished.emit(
                "probeToJson", "Extract Information To Json succesfully!")
        except Exception as e:
            self.error.emit("probeToJson", e, traceback.format_exc())
            return

    @pyqtSlot(str)
    def probeShow(self, fname):
        try:
            self.ffmpeg = FFMpeg()
            bytes_value = self.ffmpeg.probeGetJson(fname)
            self.finishedJson.emit(
                "probeShow", "Extract Information succesfully!", bytes_value)
        except Exception as e:
            self.error.emit("probeShow", e, traceback.format_exc())
            return

    def probeInfo(self, fname, posters_as_video=True):
        try:
            self.ffmpeg = FFMpeg()
            info = self.ffmpeg.probe(fname, posters_as_video)
            return info
        except Exception:
            return None
