
"""
Playlist schema models for Yoto card content.

Translates from Zod schema definitions to Python Pydantic models.
Provides type-safe validation for track, chapter, and content structures.
"""

from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class TrackDisplay(BaseModel):
    """Display configuration for a track, including icon reference."""
    icon16x16: Optional[str] = Field(None, description="16x16 icon identifier")


class TrackAmbient(BaseModel):
    """Ambient audio configuration for a track."""
    defaultTrackDisplay: Optional[str] = Field(None, description="Default ambient track display setting")


class Track(BaseModel):
    """
    Represents a single playable track within a chapter.
    
    Can be either a local audio file (type="audio") or a streaming track (type="stream").
    
    Example:
        Track(
            key="01",
            title="Chapter Introduction",
            trackUrl="https://example.com/intro.mp3",
            type="stream",
            format="mp3",
            duration=120.5,
            fileSize=2048000,
            display=TrackDisplay(icon16x16="yoto:#ZuVmuvnoFiI4el6pBPvq0ofcgQ18HjrCmdPEE7GCnP8"),
            overlayLabel="Intro",
            channels="stereo"
        )
    """
    title: str = Field(..., description="Human-readable track title")
    trackUrl: str = Field(..., description="URL to the audio track file or stream")
    key: str = Field(..., description="Unique identifier for the track within the chapter")
    format: str = Field(..., description="Audio format (e.g., 'mp3', 'aac', 'wav')")
    uid: Optional[str] = Field(None, description="Unique user identifier for the track")
    type: Literal["audio", "stream"] = Field(..., description="Track type: local audio file or streaming")
    display: Optional[TrackDisplay] = Field(None, description="Display configuration including icon")
    overlayLabelOverride: Optional[str] = Field(None, description="Optional override for the overlay label")
    overlayLabel: str = Field(..., description="Label to display on the device overlay")
    duration: float = Field(..., description="Track duration in seconds")
    fileSize: float = Field(..., description="Track file size in bytes")
    channels: Optional[Literal["stereo", "mono"]] = Field(None, description="Audio channel configuration")
    ambient: Optional[TrackAmbient] = Field(None, description="Ambient audio configuration")
    hasStreams: Optional[bool] = Field(None, description="Whether track contains streaming content")

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Introduction",
                "trackUrl": "https://yoto.dev/audio/intro.mp3",
                "key": "01",
                "format": "mp3",
                "type": "stream",
                "overlayLabel": "Intro",
                "duration": 120.5,
                "fileSize": 2048000,
                "channels": "stereo"
            }
        }


class ChapterDisplay(BaseModel):
    """Display configuration for a chapter, including icon reference."""
    icon16x16: Optional[str] = Field(None, description="16x16 icon identifier")


class ChapterAmbient(BaseModel):
    """Ambient audio configuration for a chapter."""
    defaultTrackDisplay: Optional[str] = Field(None, description="Default ambient track display setting")


class Chapter(BaseModel):
    """
    Represents a chapter containing multiple tracks.
    
    Chapters organize tracks within a card and can have their own metadata,
    icons, and default track display/ambient settings.
    
    Example:
        Chapter(
            key="chapter_1",
            title="Part One",
            overlayLabel="Part 1",
            tracks=[track1, track2],
            duration=600.0,
            fileSize=10240000,
            display=ChapterDisplay(icon16x16="yoto:#example")
        )
    """
    key: str = Field(..., description="Unique identifier for the chapter")
    title: str = Field(..., description="Human-readable chapter title")
    overlayLabel: Optional[str] = Field(None, description="Label to display on the device overlay")
    overlayLabelOverride: Optional[str] = Field(None, description="Optional override for the overlay label")
    tracks: List[Track] = Field(..., description="List of tracks in this chapter", min_items=1)
    defaultTrackDisplay: Optional[str] = Field(None, description="Default track display setting for this chapter")
    defaultTrackAmbient: Optional[str] = Field(None, description="Default ambient audio setting for this chapter")
    duration: Optional[float] = Field(None, description="Total chapter duration in seconds (calculated from tracks)")
    fileSize: Optional[float] = Field(None, description="Total chapter file size in bytes (calculated from tracks)")
    display: ChapterDisplay = Field(..., description="Display configuration including icon")
    hidden: Optional[bool] = Field(False, description="Whether the chapter is hidden from the UI")
    hasStreams: Optional[bool] = Field(None, description="Whether chapter contains streaming content")
    ambient: Optional[ChapterAmbient] = Field(None, description="Ambient audio configuration")
    availableFrom: Optional[str] = Field(None, description="ISO timestamp for when this chapter becomes available")

    class Config:
        json_schema_extra = {
            "example": {
                "key": "ch_001",
                "title": "Chapter One",
                "overlayLabel": "Ch 1",
                "tracks": [],
                "display": {"icon16x16": "yoto:#example"},
                "duration": 600.0,
                "fileSize": 10240000
            }
        }


class PlaylistContent(BaseModel):
    """
    Container for playlist content structure.
    
    Represents the complete hierarchical organization of chapters and tracks
    that make up a playable card.
    """
    chapters: List[Chapter] = Field(..., description="List of chapters in the playlist", min_items=1)
    playbackType: Optional[Literal["linear", "interactive"]] = Field(
        None, description="How chapters/tracks should be played"
    )
    version: Optional[str] = Field(None, description="Schema version for this content structure")
    
    class Config:
        json_schema_extra = {
            "example": {
                "chapters": [],
                "playbackType": "linear",
                "version": "1.0"
            }
        }
