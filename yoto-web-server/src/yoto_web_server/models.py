"""
Pydantic models for the Yoto Web Server.

Defines data structures for API requests/responses, templates, and internal services.
Re-exports models from api.models for convenience.
"""

from typing import Literal, Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

# Re-export Yoto API models for convenience
from yoto_web_server.api.models import (
    Card,
    Chapter,
    Track,
    ChapterDisplay,
    TrackDisplay,
    CardContent,
    CardMetadata as YotoCardMetadata,
    CardConfig,
    Device,
    DeviceStatus,
    DeviceConfig,
    ConfigAlarms,
    Day,
    DAYS,
    TokenData,
    TokenResponse,
    DisplayIcon,
    DisplayIconManifest,
)


# Upload Models


class UploadStatus(str, Enum):
    """Upload job status."""

    PENDING = "pending"
    QUEUED = "queued"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


class UploadJob(BaseModel):
    """Represents an upload job."""

    id: str
    filename: str
    status: UploadStatus = UploadStatus.QUEUED
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    error: Optional[str] = None
    temp_path: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class UploadFileStatus(BaseModel):
    """Status of a single file in an upload session."""

    file_id: str
    filename: str
    size_bytes: int
    status: UploadStatus = UploadStatus.PENDING
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    error: Optional[str] = None
    temp_path: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    processing_info: Dict[str, Any] = Field(
        default_factory=dict
    )  # normalization, analysis, etc.


UploadMode = Literal["chapters", "tracks"]


class UploadSession(BaseModel):
    """Represents an upload session with multiple files."""

    session_id: str
    playlist_id: str
    user_id: str
    user_session_id: Optional[str] = None  # The user's auth session ID for API calls
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Upload configuration
    upload_mode: UploadMode = "chapters"  # chapters or tracks
    normalize: bool = False
    target_lufs: float = -23.0
    normalize_batch: bool = False
    analyze_intro_outro: bool = False
    segment_seconds: float = 10.0
    similarity_threshold: float = 0.75
    show_waveform: bool = False

    # Session status
    files: List[UploadFileStatus] = Field(default_factory=list)
    overall_status: UploadStatus = UploadStatus.PENDING
    overall_progress: float = Field(default=0.0, ge=0.0, le=100.0)
    error_message: Optional[str] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class UploadSessionInitRequest(BaseModel):
    """Request to initialize an upload session."""

    upload_mode: UploadMode = "chapters"
    normalize: bool = False
    target_lufs: Optional[float] = -23.0
    normalize_batch: bool = False
    analyze_intro_outro: bool = False
    segment_seconds: Optional[float] = 10.0
    similarity_threshold: Optional[float] = 0.75
    show_waveform: bool = False


class UploadSessionResponse(BaseModel):
    """Response with upload session info."""

    session_id: str
    playlist_id: str
    message: str
    session: UploadSession


# Icon Models


class IconSource(str, Enum):
    """Icon source type."""

    OFFICIAL = "official"
    YOTOICONS = "yotoicons"
    LOCAL = "local"


class IconMetadata(BaseModel):
    """Metadata about an icon."""

    source: IconSource
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    color: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class Icon(BaseModel):
    """Icon data model."""

    id: str
    name: str
    data: str  # Base64 encoded image data or URL
    metadata: IconMetadata
    score: float = Field(default=1.0, ge=0.0, le=1.0)  # Relevance/match score

    class Config:
        json_encoders = {IconSource: lambda v: v.value}


class IconSearchRequest(BaseModel):
    """Request for icon search."""

    query: Optional[str] = None
    source: Optional[IconSource] = None
    fuzzy: bool = False
    threshold: float = Field(default=0.6, ge=0.0, le=1.0)


class IconSearchResponse(BaseModel):
    """Response from icon search."""

    query: Optional[str] = None
    source: Optional[IconSource] = None
    icons: List[Icon]
    total: int


# Playlist/Card Models


class CardMetadata(BaseModel):
    """Metadata for a card (server model)."""

    category: Optional[str] = None
    genre: Optional[List[str]] = None
    author: Optional[str] = None
    description: Optional[str] = None
    cover: Optional[Dict[str, str]] = None
    imageL: Optional[str] = None
    imageM: Optional[str] = None
    imageS: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"  # Allow additional metadata fields


class PlaylistCard(BaseModel):
    """A card (playlist item) from the Yoto API."""

    cardId: str
    title: str
    metadata: Optional[CardMetadata] = None
    tags: Optional[List[str]] = None
    slug: Optional[str] = None
    createdAt: Optional[datetime] = None
    extra: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


class CardFilterRequest(BaseModel):
    """Request to filter cards."""

    title_filter: Optional[str] = None
    category: Optional[str] = None
    genre: Optional[str] = None  # Comma-separated


class CardListResponse(BaseModel):
    """Response with list of cards."""

    cards: List[PlaylistCard]
    total: int
    filters: Optional[CardFilterRequest] = None


# Authentication Models


class TokenInfo(BaseModel):
    """OAuth token information."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: Optional[int] = None
    refresh_token: Optional[str] = None
    id_token: Optional[str] = None


class OAuthCallbackRequest(BaseModel):
    """OAuth callback request data."""

    code: str
    state: str
    error: Optional[str] = None
    error_description: Optional[str] = None


# UI Models


class PageContent(BaseModel):
    """Generic page content wrapper."""

    title: str
    content: str  # HTML content
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PartialContent(BaseModel):
    """Generic partial content wrapper."""

    content: str  # HTML content
    context: Dict[str, Any] = Field(default_factory=dict)


# Playlist Request Models


class CreatePlaylistRequest(BaseModel):
    """Request to create a new playlist."""

    title: str = Field(..., min_length=1, description="Playlist title")
    category: Optional[str] = None


class ReorderChaptersRequest(BaseModel):
    """Request to reorder chapters in a playlist."""

    playlist_id: str
    new_order: List[int] = Field(
        ..., description="List of chapter indices in new order"
    )


class UpdateChapterIconRequest(BaseModel):
    """Request to update chapter/track icons."""

    icon_id: str = Field(..., description="Icon ID to assign")
    chapter_ids: List[int] = Field(default_factory=list, description="Indices of chapters to update")
    track_ids: List[int] = Field(default_factory=list, description="Indices of tracks to update (future)")


# Playlist Response Models


class UpdateChapterIconResponse(BaseModel):
    """Response from updating chapter/track icons."""

    status: str
    icon_id: str
    updated_count: int
    icon_field: str


class ReorderChaptersResponse(BaseModel):
    """Response from reordering chapters."""

    status: str
    playlist_id: str


class DeletePlaylistResponse(BaseModel):
    """Response from deleting a playlist."""

    status: str
    playlist_id: str


class FileUploadResponse(BaseModel):
    """Response from uploading a file to a session."""

    status: str
    file_id: str
    filename: str
    session_id: str
    session: Optional[UploadSession] = None


class UploadSessionStatusResponse(BaseModel):
    """Response with upload session status."""

    status: str
    session_id: str
    session: UploadSession


class PlaylistUploadSessionsResponse(BaseModel):
    """Response with list of upload sessions."""

    status: str
    playlist_id: str
    sessions: List[UploadSession]
    count: int


class DeleteUploadSessionResponse(BaseModel):
    """Response from deleting an upload session."""

    status: str
    message: str
    session_id: str


# Response Models


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    message: str
    details: Optional[Dict[str, Any]] = None


class SuccessResponse(BaseModel):
    """Standard success response."""

    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None


# API Service Models


class AuthStatus(BaseModel):
    """Current authentication status."""

    authenticated: bool
    user_id: Optional[str] = None
    login_url: Optional[str] = None
