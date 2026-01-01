"""
Pydantic models for Yoto API data structures.

These models represent the data structures used by the Yoto API.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from datetime import time as dt_time
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel as _BaseModel
from pydantic import ConfigDict, Field, model_validator


class BaseModel(_BaseModel):
    """Base model with common configuration."""

    model_config = ConfigDict(
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
        extra="ignore",
    )


# =============================================================================
# Track and Chapter Models
# =============================================================================


class Ambient(BaseModel):
    """Ambient display settings."""

    default_track_display: str | None = Field(default=None, alias="defaultTrackDisplay")


class TrackDisplay(BaseModel):
    """Track display icon configuration."""

    icon_16x16: str | None = Field(default=None, alias="icon16x16")


class Track(BaseModel):
    """
    Represents a Yoto track.

    Can be a local audio file or a streaming track.
    For streaming tracks:
        - type: "stream"
        - trackUrl: URL to the audio stream
        - format: format of the stream (e.g. "mp3", "aac")
    """

    title: str
    track_url: str = Field(alias="trackUrl")
    key: str
    format: str | None = None
    uid: str | None = None
    type: Literal["audio", "stream"]
    display: TrackDisplay | None = None
    overlay_label_override: str | None = Field(default=None, alias="overlayLabelOverride")
    overlay_label: str | None = Field(default=None, alias="overlayLabel")
    duration: float | None = None
    file_size: float | None = Field(default=None, alias="fileSize")
    channels: Literal["stereo", "mono", 1, 2] | None = None
    ambient: Ambient | None = None
    has_streams: bool | None = Field(default=None, alias="hasStreams")


class ChapterDisplay(BaseModel):
    """Chapter display icon configuration."""

    icon_16x16: str | None = Field(default=None, alias="icon16x16")


class Chapter(BaseModel):
    """Represents a chapter containing one or more tracks."""

    key: str
    title: str
    overlay_label: str | None = Field(default=None, alias="overlayLabel")
    overlay_label_override: str | None = Field(default=None, alias="overlayLabelOverride")
    tracks: list[Track]
    default_track_display: str | None = Field(default=None, alias="defaultTrackDisplay")
    default_track_ambient: str | None = Field(default=None, alias="defaultTrackAmbient")
    duration: float | None = None
    file_size: float | None = Field(default=None, alias="fileSize")
    display: ChapterDisplay | None = None
    hidden: bool | None = None
    has_streams: bool | None = Field(default=None, alias="hasStreams")
    ambient: Ambient | None = None
    available_from: str | None = Field(default=None, alias="availableFrom")


# =============================================================================
# Card Models
# =============================================================================


class CardStatus(BaseModel):
    """Card status information."""

    name: Literal["new", "inprogress", "complete", "live", "archived"]
    updated_at: str | None = Field(default=None, alias="updatedAt")


class CardCover(BaseModel):
    """Card cover image information."""

    image_l: str | None = Field(default=None, alias="imageL")


class CardMedia(BaseModel):
    """Card media information."""

    duration: float | None = None
    file_size: float | None = Field(default=None, alias="fileSize")
    has_streams: bool | None = Field(default=None, alias="hasStreams")


class CardConfig(BaseModel):
    """Card playback configuration."""

    autoadvance: str | None = None
    resume_timeout: int | None = Field(default=None, alias="resumeTimeout")
    system_activity: bool | None = Field(default=None, alias="systemActivity")
    track_number_overlay_timeout: int | None = Field(
        default=None, alias="trackNumberOverlayTimeout"
    )


class Category(str, Enum):
    """Card category types."""

    EMPTY = ""
    STORIES = "stories"
    MUSIC = "music"
    RADIO = "radio"
    PODCAST = "podcast"
    SFX = "sfx"
    ACTIVITIES = "activities"
    ALARMS = "alarms"
    NONE = "none"


class CardMetadata(BaseModel):
    """Card metadata information."""

    accent: str | None = None
    add_to_family_library: bool | None = Field(default=None, alias="addToFamilyLibrary")
    author: str | None = None
    category: Category | None = None
    copyright: str | None = None
    cover: CardCover | None = None
    description: str | None = None
    genre: list[str] | None = None
    languages: list[str] | None = None
    max_age: int | None = Field(default=None, alias="maxAge")
    media: CardMedia | None = None
    min_age: int | None = Field(default=None, alias="minAge")
    music_type: list[str] | None = Field(default=None, alias="musicType")
    note: str | None = None
    order: str | None = None
    audio_preview_url: str | None = Field(default=None, alias="audioPreviewUrl")
    read_by: str | None = Field(default=None, alias="readBy")
    share: bool | None = None
    status: CardStatus | None = None
    tags: list[str] | None = None
    feed_url: str | None = Field(default=None, alias="feedUrl")
    num_episodes: int | None = Field(default=None, alias="numEpisodes")
    playback_direction: Literal["DESC", "ASC"] | None = Field(
        default=None, alias="playbackDirection"
    )
    preview_audio: str = Field(default="", alias="previewAudio")
    hidden: bool = False


class CardContent(BaseModel):
    """Card content structure."""

    activity: str | None = None
    chapters: list[Chapter] | None = None
    config: CardConfig | None = None
    playback_type: Literal["linear", "interactive"] | None = Field(
        default=None, alias="playbackType"
    )
    version: str | None = None
    hidden: bool = False


class CardBase(BaseModel):
    """Represents a Yoto card (playlist)."""

    title: str
    metadata: CardMetadata | None = None
    content: CardContent | None = None
    tags: list[str] | None = None
    slug: str | None = None
    deleted: bool = False
    created_at: str | None = Field(default=None, alias="createdAt")
    created_by_client_id: str | None = Field(default=None, alias="createdByClientId")
    updated_at: str | None = Field(default=None, alias="updatedAt")
    user_id: str | None = Field(default=None, alias="userId")


class NewCardRequest(CardBase):
    """Request model for creating a new card."""

    card_id: None = Field(default=None, alias="cardId")
    created_at: None = Field(default=None, alias="createdAt")
    created_by_client_id: None = Field(default=None, alias="createdByClientId")
    updated_at: None = Field(default=None, alias="updatedAt")
    user_id: None = Field(default=None, alias="userId")


class Card(CardBase):
    """Request model for updating an existing card."""

    card_id: str = Field(..., alias="cardId")
    created_at: str | None = Field(default=None, alias="createdAt")
    created_by_client_id: str | None = Field(default=None, alias="createdByClientId")
    updated_at: str | None = Field(default=None, alias="updatedAt")
    user_id: str | None = Field(default=None, alias="userId")


# =============================================================================
# Device Models
# =============================================================================


class Device(BaseModel):
    """Represents a Yoto device."""

    device_id: str = Field(..., alias="deviceId")
    name: str
    description: str
    online: bool
    release_channel: str = Field(..., alias="releaseChannel")
    device_type: str = Field(..., alias="deviceType")
    device_family: str = Field(..., alias="deviceFamily")
    device_group: str = Field(..., alias="deviceGroup")


class CardInsertionState(int, Enum):
    """Card insertion states."""

    NO_CARD = 0
    PHYSICAL_CARD = 1
    REMOTE_PLAY = 2


class DayMode(int, Enum):
    """Day mode states."""

    UNKNOWN = -1
    NIGHT = 0
    DAY = 1


class PowerSource(int, Enum):
    """Power source types."""

    BATTERY_ONLY = 0
    V2_DOCK = 1
    USB_C = 2
    QI_DOCK = 3


class DeviceStatus(BaseModel):
    """Device status information."""

    active_card: str | None = Field(default=None, alias="activeCard")
    ambient_light_sensor_reading: int | None = Field(
        default=None, alias="ambientLightSensorReading"
    )
    average_download_speed_bytes_second: float | None = Field(
        None, alias="averageDownloadSpeedBytesSecond"
    )
    battery_level_percentage: float | None = Field(default=None, alias="batteryLevelPercentage")
    card_insertion_state: CardInsertionState | None = Field(
        default=None, alias="cardInsertionState"
    )
    day_mode: DayMode | None = Field(default=None, alias="dayMode")
    device_id: str = Field(..., alias="deviceId")
    free_disk_space_bytes: int | None = Field(default=None, alias="freeDiskSpaceBytes")
    is_audio_device_connected: bool | None = Field(default=None, alias="isAudioDeviceConnected")
    is_background_download_active: bool | None = Field(
        default=None, alias="isBackgroundDownloadActive"
    )
    is_bluetooth_audio_connected: bool | None = Field(
        default=None, alias="isBluetoothAudioConnected"
    )
    is_charging: bool | None = Field(default=None, alias="isCharging")
    is_online: bool | None = Field(default=None, alias="isOnline")
    network_ssid: str | None = Field(default=None, alias="networkSsid")
    nightlight_mode: str | None = Field(default=None, alias="nightlightMode")
    power_source: PowerSource | None = Field(default=None, alias="powerSource")
    system_volume_percentage: float | None = Field(default=None, alias="systemVolumePercentage")
    temperature_celsius: float | None = Field(default=None, alias="temperatureCelcius")
    total_disk_space_bytes: int | None = Field(default=None, alias="totalDiskSpaceBytes")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
    uptime: int | None = None
    user_volume_percentage: float = Field(..., alias="userVolumePercentage")
    utc_offset_seconds: int | None = Field(default=None, alias="utcOffsetSeconds")
    utc_time: datetime | None = Field(default=None, alias="utcTime")
    wifi_strength: int | None = Field(default=None, alias="wifiStrength")


# =============================================================================
# Device Configuration Models
# =============================================================================


Day = Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DAYS: list[Day] = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class ConfigAlarms(BaseModel):
    """Alarm configuration."""

    weekdays: dict[Day, bool]
    time: dt_time
    tone_id: str | None
    volume_level: str
    is_enabled: bool

    @model_validator(mode="before")
    @classmethod
    def decode(cls, data: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(data, dict):
            return data
        parts = data.split(",")
        parts_dict = dict(enumerate(parts))

        weekdays_part = parts_dict.get(0, "0000000")
        weekdays: dict[Day, bool] = {day: weekdays_part[idx] == "1" for idx, day in enumerate(DAYS)}

        time_str = parts_dict.get(1, "0000")
        hour = int(time_str[0:2])
        minute = int(time_str[2:4])
        alarm_time = dt_time(hour=hour, minute=minute)

        tone_id = parts_dict.get(2, "")
        volume_level = parts_dict.get(5, "0")
        is_enabled = parts_dict.get(6, "0") == "1"

        return {
            "weekdays": weekdays,
            "time": alarm_time,
            "tone_id": tone_id if tone_id else None,
            "volume_level": volume_level,
            "is_enabled": is_enabled,
        }

    def encode(self) -> str:
        """Encode alarm configuration to string format."""
        weekdays_part = "".join(["1" if self.weekdays.get(day, False) else "0" for day in DAYS])
        time_part = f"{self.time.hour:02}{self.time.minute:02}"
        tone_part = self.tone_id or ""
        volume_part = self.volume_level
        enabled_part = "1" if self.is_enabled else "0"
        return ",".join([weekdays_part, time_part, tone_part, "", "", volume_part, enabled_part])


class DeviceConfigResponseConfig(BaseModel):
    """Device configuration from API response."""

    locale: str
    bluetooth_enabled: str = Field(..., alias="bluetoothEnabled")
    repeat_all: bool = Field(..., alias="repeatAll")
    show_diagnostics: bool = Field(..., alias="showDiagnostics")
    bt_headphones_enabled: bool = Field(..., alias="btHeadphonesEnabled")
    pause_volume_down: bool = Field(..., alias="pauseVolumeDown")
    pause_power_button: bool = Field(..., alias="pausePowerButton")
    display_dim_timeout: str = Field(..., alias="displayDimTimeout")
    shutdown_timeout: str = Field(..., alias="shutdownTimeout")
    headphones_volume_limited: bool = Field(..., alias="headphonesVolumeLimited")
    day_time: str = Field(..., alias="dayTime")
    max_volume_limit: str = Field(..., alias="maxVolumeLimit")
    ambient_colour: str = Field(..., alias="ambientColour")
    day_display_brightness: str = Field(..., alias="dayDisplayBrightness")
    day_yoto_daily: str = Field(..., alias="dayYotoDaily")
    day_yoto_radio: str = Field(..., alias="dayYotoRadio")
    day_sounds_off: str = Field(..., alias="daySoundsOff")
    night_time: str = Field(..., alias="nightTime")
    night_max_volume_limit: str = Field(..., alias="nightMaxVolumeLimit")
    night_ambient_colour: str = Field(..., alias="nightAmbientColour")
    night_display_brightness: str = Field(..., alias="nightDisplayBrightness")
    night_yoto_daily: str = Field(..., alias="nightYotoDaily")
    night_yoto_radio: str = Field(..., alias="nightYotoRadio")
    night_sounds_off: str = Field(..., alias="nightSoundsOff")
    hour_format: str = Field(..., alias="hourFormat")
    display_dim_brightness: str = Field(..., alias="displayDimBrightness")
    system_volume: str = Field(..., alias="systemVolume")
    volume_level: str = Field(..., alias="volumeLevel")
    clock_face: str = Field(..., alias="clockFace")
    log_level: str = Field(..., alias="logLevel")
    alarms: list[ConfigAlarms]


class DeviceConfig(BaseModel):
    """Device configuration response wrapper."""

    class DeviceConfigResponseDevice(BaseModel):
        device_id: str = Field(..., alias="deviceId")
        name: str
        config: DeviceConfigResponseConfig

    device: DeviceConfigResponseDevice


# =============================================================================
# API Response Models
# =============================================================================


class TokenResponse(BaseModel):
    """OAuth token response."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: str | None = None
    scope: str | None = None


@dataclass
class TokenData:
    """Token data with expiration tracking."""

    access_token: str
    refresh_token: str | None
    expires_at: float

    def is_expired(self, buffer_seconds: float = 30.0) -> bool:
        """Check if token is expired (with buffer)."""
        return time.time() >= (self.expires_at - buffer_seconds)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TokenData:
        """Create from dictionary."""
        return cls(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=data["expires_at"],
        )

    @classmethod
    def from_token_response(cls, response: TokenResponse) -> TokenData:
        """Create from token response."""
        expires_at = time.time() + response.expires_in
        return cls(
            access_token=response.access_token,
            refresh_token=response.refresh_token,
            expires_at=expires_at,
        )


class DeviceAuthResponse(BaseModel):
    """Response from device authorization flow."""

    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int = 5


class AudioUploadUrlResponse(BaseModel):
    """Response from audio upload URL request."""

    class Upload(BaseModel):
        upload_url: str | None = Field(default=None, alias="uploadUrl")
        upload_id: str = Field(..., alias="uploadId")

    upload: Upload


class TranscodedAudioResponse(BaseModel):
    """Response from transcoded audio endpoint."""

    class Transcode(BaseModel):
        class Progress(BaseModel):
            phase: str
            percent: float
            updated_at: datetime = Field(..., alias="updatedAt")

        class TranscodeInfo(BaseModel):
            duration: float
            codec: str
            format: str
            sample_rate: int = Field(..., alias="sampleRate")
            channels: str
            bitrate: int
            metadata: dict[str, Any]
            input_format: str = Field(..., alias="inputFormat")
            file_size: int | None = Field(default=None, alias="fileSize")

        upload_id: str = Field(..., alias="uploadId")
        upload_filename: str = Field(..., alias="uploadFilename")
        upload_sha256: str = Field(..., alias="uploadSha256")
        created_at: datetime = Field(..., alias="createdAt")
        options: dict[str, Any]
        started_at: datetime | None = Field(default=None, alias="startedAt")
        progress: Progress | None = None
        ffmpeg: dict[str, Any] | None = None
        transcoded_at: datetime | None = Field(default=None, alias="transcodedAt")
        transcoded_info: TranscodeInfo | None = Field(default=None, alias="transcodedInfo")
        transcoded_sha256: str | None = Field(default=None, alias="transcodedSha256")
        upload_info: TranscodeInfo | None = Field(default=None, alias="uploadInfo")

    transcode: Transcode


class CoverImageData(BaseModel):
    """Cover image data from upload response."""

    media_id: str = Field(..., alias="mediaId")
    media_url: str = Field(..., alias="mediaUrl")


class CoverImageUploadResponse(BaseModel):
    """Response from cover image upload."""

    cover_image: CoverImageData = Field(..., alias="coverImage")


class IconUploadResponse(BaseModel):
    """Response from icon upload."""

    media_id: str = Field(..., alias="mediaId", description="Media ID for the uploaded icon")
    url: str = Field(..., description="URL to the uploaded icon")


class CoverType(str, Enum):
    """Cover image types."""

    SQUARE = "square"
    RECTANGLE = "rectangle"


# =============================================================================
# Display Icon Models
# =============================================================================


class DisplayIcon(BaseModel):
    """Represents a public icon from the Yoto API manifest."""

    created_at: str = Field(alias="createdAt", description="ISO 8601 timestamp of creation")
    display_icon_id: str = Field(alias="displayIconId", description="Yoto ID for this display icon")
    media_id: str = Field(alias="mediaId", description="Media ID used to fetch the icon")
    new: bool | None = Field(default=None, description="Whether this is a new icon")
    public: bool = Field(description="Whether this icon is publicly available")
    public_tags: list[str] | None = Field(
        default_factory=list, alias="publicTags", description="Tags for public discovery"
    )
    title: str | None = Field(default=None, description="Human-readable title/name")
    url: str = Field(description="Direct URL to the icon image")
    user_id: str = Field(alias="userId", description="User ID of the icon owner")


class DisplayIconManifest(BaseModel):
    """Container for the list of public display icons from Yoto API."""

    display_icons: list[DisplayIcon] = Field(
        default_factory=list, alias="displayIcons", description="List of all public icons"
    )


class DeviceConfigResponseShortcutsMode(BaseModel):
    class Content(BaseModel):
        cmd: str
        params: dict[str, str]

    content: list[Content]


class DeviceConfigResponseShortcuts(BaseModel):
    version_id: str = Field(..., alias="versionId")
    modes: dict[Literal["day", "night"], DeviceConfigResponseShortcutsMode]


class DeviceConfigUpdate(BaseModel):
    class UpdateConfig(BaseModel):
        locale: str | None = None
        bluetooth_enabled: Annotated[str | None, Field(alias="bluetoothEnabled")] = None
        repeat_all: Annotated[bool | None, Field(alias="repeatAll")] = None
        show_diagnostics: Annotated[bool | None, Field(alias="showDiagnostics")] = None
        bt_headphones_enabled: Annotated[bool | None, Field(alias="btHeadphonesEnabled")] = None
        pause_volume_down: Annotated[bool | None, Field(alias="pauseVolumeDown")] = None
        pause_power_button: Annotated[bool | None, Field(alias="pausePowerButton")] = None
        display_dim_timeout: Annotated[str | None, Field(alias="displayDimTimeout")] = None
        shutdown_timeout: Annotated[str | None, Field(alias="shutdownTimeout")] = None
        headphones_volume_limited: Annotated[
            bool | None, Field(alias="headphonesVolumeLimited")
        ] = None
        day_time: Annotated[str | None, Field(alias="dayTime")] = None
        max_volume_limit: Annotated[str | None, Field(alias="maxVolumeLimit")] = None
        ambient_colour: Annotated[str | None, Field(alias="ambientColour")] = None
        day_display_brightness: Annotated[
            str | None, Field(default=None, alias="dayDisplayBrightness")
        ] = None
        day_yoto_daily: Annotated[str | None, Field(alias="dayYotoDaily")] = None
        day_yoto_radio: Annotated[str | None, Field(alias="dayYotoRadio")] = None
        day_sounds_off: Annotated[str | None, Field(alias="daySoundsOff")] = None
        night_time: Annotated[str | None, Field(alias="nightTime")] = None
        night_max_volume_limit: Annotated[str | None, Field(alias="nightMaxVolumeLimit")] = None
        night_ambient_colour: Annotated[str | None, Field(alias="nightAmbientColour")] = None
        night_display_brightness: Annotated[
            str | None, Field(default=None, alias="nightDisplayBrightness")
        ] = None
        night_yoto_daily: Annotated[str | None, Field(alias="nightYotoDaily")] = None
        night_yoto_radio: Annotated[str | None, Field(alias="nightYotoRadio")] = None
        night_sounds_off: Annotated[str | None, Field(alias="nightSoundsOff")] = None
        hour_format: Annotated[str | None, Field(alias="hourFormat")] = None
        display_dim_brightness: Annotated[
            str | None, Field(default=None, alias="displayDimBrightness")
        ] = None
        system_volume: Annotated[str | None, Field(alias="systemVolume")] = None
        volume_level: Annotated[str | None, Field(alias="volumeLevel")] = None
        clock_face: Annotated[str | None, Field(alias="clockFace")] = None
        log_level: Annotated[str | None, Field(alias="logLevel")] = None
        alarms: list[ConfigAlarms] | None = None

    name: str
    config: UpdateConfig
