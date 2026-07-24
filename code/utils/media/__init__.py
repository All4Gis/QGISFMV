# -*- coding: utf-8 -*-
"""Video, stream, ffmpeg, and MISB metadata I/O.

- ``QgsFmvMultimedia`` — public player factory / playlist façade
- ``QgsFmvMediaTypes`` — playback / media-status enums
- ``QgsFmvMediaProbe`` — path and stream-info helpers
- ``QgsFmvDecodeWorkers`` — OpenCV + FFmpeg background decode workers
- ``QgsFmvOpenCvPlayer`` — OpenCV/FFmpeg QMediaPlayer-compatible backend
- ``QgsFmvQtMediaAdapter`` — Qt multimedia fallback
- ``QgsFmvPlaylist`` — playlist helpers
- ``QgsFfmpegRunner`` / ``QgsFfmpegProbe`` — ffmpeg process + probe helpers
- ``QgsFmvKlvReader`` / ``QgsFmvMetadataWorker`` — MISB metadata I/O
- ``QgsFmvGeocode`` / ``QgsFmvStreamUtils`` — geocode + stream URI helpers
"""
