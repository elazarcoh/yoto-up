"""
Pydantic models for the Yoto Web Server.

Defines data structures for API requests/responses, templates, and internal services.
Re-exports models from api.models for convenience.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

# Upload Models


class FileUploadStatus(str, Enum):
    """Upload job status."""

    PENDING = "pending"
    QUEUED = "queued"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    YOTO_UPLOADING = "yoto_uploading"
    DONE = "done"
    ERROR = "error"


class SessionUploadStatus(str, Enum):
    """Session job status."""

    PENDING = "pending"
    PROCESSING = "processing"

    DONE_SUCCESS = "success"
    DONE_PARTIAL_SUCCESS = "partial_success"
    DONE_ALL_ERROR = "all_error"


class UploadFileStatus(BaseModel):
    """Status of a single file in an upload session."""

    file_id: str
    filename: str
    size_bytes: int
    status: FileUploadStatus = FileUploadStatus.PENDING
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    error: str | None = None
    temp_path: str | None = None
    uploaded_at: datetime | None = None
    current_step: str | None = None
    original_title: str | None = None  # For URL uploads, store the original metadata title


UploadMode = Literal["chapters", "tracks"]


class UploadSession(BaseModel):
    """Represents an upload session with multiple files."""

    session_id: str
    playlist_id: str
    user_id: str
    user_session_id: str | None = None  # The user's auth session ID for API calls
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

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
    files: list[UploadFileStatus] = Field(default_factory=list)
    error_message: str | None = None
    new_chapter_ids: list[str] = Field(default_factory=list)
    session_done: bool = False

    # File registration tracking
    files_registered: bool = False  # Set to True when client pre-registers file count
    expected_file_count: int = 0  # Number of files expected to be uploaded
    all_files_uploaded: bool = False  # Set to True when finalize endpoint is called

    # Processing queue - tracks which files still need to be processed
    files_to_process: list[str] = Field(default_factory=list)  # List of file_ids pending processing

    @property
    def overall_progress(self) -> float:
        if not self.files:
            return 0.0
        total = sum(file.progress for file in self.files)
        return total / len(self.files)

    @property
    def overall_status(self) -> SessionUploadStatus:
        statuses = [file.status for file in self.files]

        completed = (
            all(status in [FileUploadStatus.DONE, FileUploadStatus.ERROR] for status in statuses)
            and self.session_done
        )

        if completed:
            if all(status == FileUploadStatus.ERROR for status in statuses):
                return SessionUploadStatus.DONE_ALL_ERROR
            elif all(status == FileUploadStatus.DONE for status in statuses):
                return SessionUploadStatus.DONE_SUCCESS
            else:
                return SessionUploadStatus.DONE_PARTIAL_SUCCESS
        else:
            if any(status == FileUploadStatus.PROCESSING for status in statuses):
                return SessionUploadStatus.PROCESSING
            else:
                return SessionUploadStatus.PENDING

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class UploadSessionInitRequest(BaseModel):
    """Request to initialize an upload session."""

    upload_mode: UploadMode = "chapters"
    normalize: bool = False
    target_lufs: float = -23.0
    normalize_batch: bool = False
    analyze_intro_outro: bool = False
    segment_seconds: float = 10.0
    similarity_threshold: float = 0.75
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
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    color: str | None = None
    width: int | None = None
    height: int | None = None


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

    query: str | None = None
    source: IconSource | None = None
    fuzzy: bool = False
    threshold: float = Field(default=0.6, ge=0.0, le=1.0)


class IconSearchResponse(BaseModel):
    """Response from icon search."""

    query: str | None = None
    source: IconSource | None = None
    icons: list[Icon]
    total: int


# Playlist/Card Models


class CardMetadata(BaseModel):
    """Metadata for a card (server model)."""

    category: str | None = None
    genre: list[str] | None = None
    author: str | None = None
    description: str | None = None
    cover: dict[str, str] | None = None
    image_l: str | None = Field(None, alias="imageL")
    image_m: str | None = Field(None, alias="imageM")
    image_s: str | None = Field(None, alias="imageS")
    extra: dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"  # Allow additional metadata fields


class PlaylistCard(BaseModel):
    """A card (playlist item) from the Yoto API."""

    card_id: str = Field(..., alias="cardId")
    title: str
    metadata: CardMetadata | None = None
    tags: list[str] | None = None
    slug: str | None = None
    created_at: datetime | None = Field(None, alias="createdAt")
    extra: dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


class CardFilterRequest(BaseModel):
    """Request to filter cards."""

    title_filter: str | None = None
    category: str | None = None
    genre: str | None = None  # Comma-separated


class CardListResponse(BaseModel):
    """Response with list of cards."""

    cards: list[PlaylistCard]
    total: int
    filters: CardFilterRequest | None = None


# Authentication Models


class TokenInfo(BaseModel):
    """OAuth token information."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    refresh_token: str | None = None
    id_token: str | None = None


class OAuthCallbackRequest(BaseModel):
    """OAuth callback request data."""

    code: str
    state: str
    error: str | None = None
    error_description: str | None = None


# UI Models


class PageContent(BaseModel):
    """Generic page content wrapper."""

    title: str
    content: str  # HTML content
    metadata: dict[str, Any] = Field(default_factory=dict)


class PartialContent(BaseModel):
    """Generic partial content wrapper."""

    content: str  # HTML content
    context: dict[str, Any] = Field(default_factory=dict)


# Playlist Request Models


class CreatePlaylistRequest(BaseModel):
    """Request to create a new playlist."""

    title: str = Field(..., min_length=1, description="Playlist title")
    category: str | None = None


class ReorderChaptersRequest(BaseModel):
    """Request to reorder chapters in a playlist."""

    playlist_id: str
    new_order: list[int] = Field(..., description="List of chapter indices in new order")


class UpdateChapterIconRequest(BaseModel):
    """Request to update chapter/track icons."""

    icon_id: str = Field(..., description="Icon ID to assign")
    chapter_ids: list[int] = Field(
        default_factory=list, description="Indices of chapters to update"
    )
    track_ids: list[int] = Field(
        default_factory=list, description="Indices of tracks to update (future)"
    )


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
    session: UploadSession | None = None


class UploadSessionStatusResponse(BaseModel):
    """Response with upload session status."""

    status: str
    session_id: str
    session: UploadSession


class PlaylistUploadSessionsResponse(BaseModel):
    """Response with list of upload sessions."""

    status: str
    playlist_id: str
    sessions: list[UploadSession]
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
    details: dict[str, Any] | None = None


class SuccessResponse(BaseModel):
    """Standard success response."""

    success: bool = True
    message: str
    data: dict[str, Any] | None = None


# API Service Models


class AuthStatus(BaseModel):
    """Current authentication status."""

    authenticated: bool
    user_id: str | None = None
    login_url: str | None = None
