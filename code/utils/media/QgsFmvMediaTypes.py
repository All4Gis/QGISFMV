# -*- coding: utf-8 -*-
"""Playback / media-status enums and public aliases for FMV multimedia."""

from enum import IntEnum


class PlaybackState(IntEnum):
    """Media playback state constants."""
    Stopped = 0
    Playing = 1
    Paused = 2


class MediaStatus(IntEnum):
    """Media source status constants."""
    NoMedia = 0
    Loading = 1
    Loaded = 2
    Buffering = 3
    Buffered = 4
    Stalled = 5
    Invalid = 6
    EndOfMedia = 7


class PlaylistMode(IntEnum):
    """Playlist playback mode constants."""
    Sequential = 0
    Loop = 1


# Backward-compatible aliases used across player / manager / video widgets.
PlayingState = PlaybackState.Playing
PausedState = PlaybackState.Paused
StoppedState = PlaybackState.Stopped

NoMedia = MediaStatus.NoMedia
LoadingMedia = MediaStatus.Loading
LoadedMedia = MediaStatus.Loaded
BufferingMedia = MediaStatus.Buffering
BufferedMedia = MediaStatus.Buffered
StalledMedia = MediaStatus.Stalled
InvalidMedia = MediaStatus.Invalid
EndOfMedia = MediaStatus.EndOfMedia

PlaylistSequential = PlaylistMode.Sequential
PlaylistLoop = PlaylistMode.Loop
