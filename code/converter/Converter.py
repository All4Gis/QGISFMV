# Original Code : https://github.com/senko/python-video-converter
# Modificated for work in QGIS FMV Plugin

from PyQt5.QtCore import QObject
from QGIS_FMV.converter.avcodecs import (video_codec_list,
                                         audio_codec_list,
                                         subtitle_codec_list)
from QGIS_FMV.converter.ffmpeg import FFMpeg
from QGIS_FMV.converter.formats import format_list
from QGIS_FMV.utils.QgsFmvLog import log
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu

try:
    from pydevd import *
except ImportError:
    None


class Converter(QObject):

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

    def convert(self, task, infile, outfile, options, twopass):
        try:
            while not task.isCanceled():
                self.ffmpeg = FFMpeg()
                info = self.ffmpeg.probe(infile)
                if info is None:
                    task.cancel()
                    return "Can't get information about source file"

                if not info.video and not info.audio:
                    task.cancel()
                    return 'Source file has no audio or video streams'

                if info.video and 'video' in options:
                    options = options.copy()
                    v = options['video'] = options['video'].copy()
                    v['src_width'] = info.video.video_width
                    v['src_height'] = info.video.video_height

                if info.format.duration < 0.01:
                    task.cancel()
                    return 'Zero-length media'

                if twopass:
                    optlist1 = self.parse_options(options, 1)
                    for timecode in self.ffmpeg.convert(infile, outfile, optlist1, task):
                        task.setProgress(
                            int((50.0 * timecode) / info.format.duration))

                    optlist2 = self.parse_options(options, 2)
                    for timecode in self.ffmpeg.convert(infile, outfile, optlist2, task):
                        task.setProgress(
                            int(50.0 + (50.0 * timecode) / info.format.duration))
                else:
                    optlist = self.parse_options(options, twopass)
                    for timecode in self.ffmpeg.convert(infile, outfile, optlist, task):
                        task.setProgress(
                            int((100.0 * timecode) / info.format.duration))
                task.setProgress(100)
            if task.isCanceled():
                return None
        except Exception:
            return None
        return {'task': task.description()}

    def probeToJson(self, task, fname, output):
        try:
            self.ffmpeg = FFMpeg()
            self.ffmpeg.probeToJson(fname, output)
            if task.isCanceled():
                return None
            return {'task': task.description()}
        except Exception:
            return None

    def probeShow(self, task, fname):
        try:
            self.ffmpeg = FFMpeg()
            self.bytes_value = self.ffmpeg.probeGetJson(fname)
            if task.isCanceled():
                return None
            return {'task': task.description()}
        except Exception:
            return None

    def probeInfo(self, fname, posters_as_video=True):
        try:
            self.ffmpeg = FFMpeg()
            info = self.ffmpeg.probe(fname, posters_as_video)
            return info
        except Exception:
            return None
