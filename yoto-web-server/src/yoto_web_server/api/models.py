"""
Pydantic models for Yoto API data structures.

These models represent the data structures used by the Yoto API.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, time as dt_time
from enum import Enum
from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# =============================================================================
# Track and Chapter Models
# =============================================================================


class Ambient(BaseModel):
    """Ambient display settings."""

    defaultTrackDisplay: Optional[str] = None


class TrackDisplay(BaseModel):
    """Track display icon configuration."""

    icon16x16: Optional[str] = None


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
    trackUrl: str
    key: str
    format: Optional[str] = None
    uid: Optional[str] = None
    type: Literal["audio", "stream"]
    display: Optional[TrackDisplay] = None
    overlayLabelOverride: Optional[str] = None
    overlayLabel: Optional[str] = None
    duration: Optional[float] = None
    fileSize: Optional[float] = None
    channels: Optional[Literal["stereo", "mono", 1, 2]] = None
    ambient: Optional[Ambient] = None
    hasStreams: Optional[bool] = None


class ChapterDisplay(BaseModel):
    """Chapter display icon configuration."""

    icon16x16: Optional[str] = None


class Chapter(BaseModel):
    """Represents a chapter containing one or more tracks."""

    key: str
    title: str
    overlayLabel: Optional[str] = None
    overlayLabelOverride: Optional[str] = None
    tracks: list[Track]
    defaultTrackDisplay: Optional[str] = None
    defaultTrackAmbient: Optional[str] = None
    duration: Optional[float] = None
    fileSize: Optional[float] = None
    display: Optional[ChapterDisplay] = None
    hidden: Optional[bool] = None
    hasStreams: Optional[bool] = None
    ambient: Optional[Ambient] = None
    availableFrom: Optional[str] = None


# =============================================================================
# Card Models
# =============================================================================


class CardStatus(BaseModel):
    """Card status information."""

    name: Literal["new", "inprogress", "complete", "live", "archived"]
    updatedAt: Optional[str] = None


class CardCover(BaseModel):
    """Card cover image information."""

    imageL: Optional[str] = None


class CardMedia(BaseModel):
    """Card media information."""

    duration: Optional[float] = None
    fileSize: Optional[float] = None
    hasStreams: Optional[bool] = None


class CardConfig(BaseModel):
    """Card playback configuration."""

    autoadvance: Optional[str] = None
    resumeTimeout: Optional[int] = None
    systemActivity: Optional[bool] = None
    trackNumberOverlayTimeout: Optional[int] = None


class CardMetadata(BaseModel):
    """Card metadata information."""

    accent: Optional[str] = None
    addToFamilyLibrary: Optional[bool] = None
    author: Optional[str] = None
    category: Optional[
        Literal[
            "",
            "none",
            "stories",
            "music",
            "radio",
            "podcast",
            "sfx",
            "activities",
            "alarms",
        ]
    ] = None
    copyright: Optional[str] = None
    cover: Optional[CardCover] = None
    description: Optional[str] = None
    genre: Optional[list[str]] = None
    languages: Optional[list[str]] = None
    maxAge: Optional[int] = None
    media: Optional[CardMedia] = None
    minAge: Optional[int] = None
    musicType: Optional[list[str]] = None
    note: Optional[str] = None
    order: Optional[str] = None
    audioPreviewUrl: Optional[str] = None
    readBy: Optional[str] = None
    share: Optional[bool] = None
    status: Optional[CardStatus] = None
    tags: Optional[list[str]] = None
    feedUrl: Optional[str] = None
    numEpisodes: Optional[int] = None
    playbackDirection: Optional[Literal["DESC", "ASC"]] = None
    previewAudio: str = ""
    hidden: bool = False


class CardContent(BaseModel):
    """Card content structure."""

    activity: Optional[str] = None
    chapters: Optional[list[Chapter]] = None
    config: Optional[CardConfig] = None
    playbackType: Optional[Literal["linear", "interactive"]] = None
    version: Optional[str] = None
    hidden: bool = False


class Card(BaseModel):
    """Represents a Yoto card (playlist)."""

    cardId: Optional[str] = None
    title: str
    metadata: Optional[CardMetadata] = None
    content: Optional[CardContent] = None
    tags: Optional[list[str]] = None
    slug: Optional[str] = None
    deleted: bool = False
    createdAt: Optional[str] = None
    createdByClientId: Optional[str] = None
    updatedAt: Optional[str] = None
    userId: Optional[str] = None


# =============================================================================
# Device Models
# =============================================================================


class Device(BaseModel):
    """Represents a Yoto device."""

    deviceId: str
    name: str
    description: str
    online: bool
    releaseChannel: str
    deviceType: str
    deviceFamily: str
    deviceGroup: str


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

    active_card: Optional[str] = Field(None, alias="activeCard")
    ambient_light_sensor_reading: Optional[int] = Field(None, alias="ambientLightSensorReading")
    average_download_speed_bytes_second: Optional[float] = Field(
        None, alias="averageDownloadSpeedBytesSecond"
    )
    battery_level_percentage: Optional[float] = Field(None, alias="batteryLevelPercentage")
    card_insertion_state: Optional[CardInsertionState] = Field(None, alias="cardInsertionState")
    day_mode: Optional[DayMode] = Field(None, alias="dayMode")
    device_id: str = Field(..., alias="deviceId")
    free_disk_space_bytes: Optional[int] = Field(None, alias="freeDiskSpaceBytes")
    is_audio_device_connected: Optional[bool] = Field(None, alias="isAudioDeviceConnected")
    is_background_download_active: Optional[bool] = Field(None, alias="isBackgroundDownloadActive")
    is_bluetooth_audio_connected: Optional[bool] = Field(None, alias="isBluetoothAudioConnected")
    is_charging: Optional[bool] = Field(None, alias="isCharging")
    is_online: Optional[bool] = Field(None, alias="isOnline")
    network_ssid: Optional[str] = Field(None, alias="networkSsid")
    nightlight_mode: Optional[str] = Field(None, alias="nightlightMode")
    power_source: Optional[PowerSource] = Field(None, alias="powerSource")
    system_volume_percentage: Optional[float] = Field(None, alias="systemVolumePercentage")
    temperature_celsius: Optional[float] = Field(None, alias="temperatureCelcius")
    total_disk_space_bytes: Optional[int] = Field(None, alias="totalDiskSpaceBytes")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")
    uptime: Optional[int] = None
    user_volume_percentage: float = Field(..., alias="userVolumePercentage")
    utc_offset_seconds: Optional[int] = Field(None, alias="utcOffsetSeconds")
    utc_time: Optional[datetime] = Field(None, alias="utcTime")
    wifi_strength: Optional[int] = Field(None, alias="wifiStrength")


# =============================================================================
# Device Configuration Models
# =============================================================================


Day = Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DAYS: list[Day] = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class ConfigAlarms(BaseModel):
    """Alarm configuration."""

    weekdays: dict[Day, bool]
    time: dt_time
    tone_id: Optional[str]
    volume_level: str
    is_enabled: bool

    @model_validator(mode="before")
    @classmethod
    def decode(cls, data: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(data, dict):
            return data
        parts = data.split(",")
        parts_dict = {idx: part for idx, part in enumerate(parts)}

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

        model_config = ConfigDict(extra="ignore")

    device: DeviceConfigResponseDevice


# =============================================================================
# API Response Models
# =============================================================================


class TokenResponse(BaseModel):
    """OAuth token response."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    scope: Optional[str] = None


@dataclass
class TokenData:
    """Token data with expiration tracking."""

    access_token: str
    refresh_token: Optional[str]
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
    def from_dict(cls, data: dict[str, Any]) -> "TokenData":
        """Create from dictionary."""
        return cls(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=data["expires_at"],
        )

    @classmethod
    def from_token_response(cls, response: TokenResponse) -> "TokenData":
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
        upload_url: Optional[str] = Field(None, alias="uploadUrl")
        upload_id: str = Field(..., alias="uploadId")

    upload: Upload


class TranscodedAudioResponse(BaseModel):
    """Response from transcoded audio endpoint."""

    class Transcode(BaseModel):
        class Progress(BaseModel):
            phase: str
            percent: float
            updated_at: datetime = Field(..., alias="updatedAt")

            model_config = ConfigDict(extra="ignore")

        class TranscodeInfo(BaseModel):
            duration: float
            codec: str
            format: str
            sample_rate: int = Field(..., alias="sampleRate")
            channels: str
            bitrate: int
            metadata: dict[str, Any]
            input_format: str = Field(..., alias="inputFormat")
            file_size: Optional[int] = Field(None, alias="fileSize")

            model_config = ConfigDict(extra="ignore")

        model_config = ConfigDict(extra="ignore")

        upload_id: str = Field(..., alias="uploadId")
        upload_filename: str = Field(..., alias="uploadFilename")
        upload_sha256: str = Field(..., alias="uploadSha256")
        created_at: datetime = Field(..., alias="createdAt")
        options: dict[str, Any]
        started_at: Optional[datetime] = Field(None, alias="startedAt")
        progress: Optional[Progress] = None
        ffmpeg: Optional[dict[str, Any]] = None
        transcoded_at: Optional[datetime] = Field(None, alias="transcodedAt")
        transcoded_info: Optional[TranscodeInfo] = Field(None, alias="transcodedInfo")
        transcoded_sha256: Optional[str] = Field(None, alias="transcodedSha256")
        upload_info: Optional[TranscodeInfo] = Field(None, alias="uploadInfo")

    transcode: Transcode


class CoverImageUploadResponse(BaseModel):
    """Response from cover image upload."""

    cover_image: str = Field(..., alias="coverImage")
    cover_type: Optional[str] = Field(None, alias="coverType")


class IconUploadResponse(BaseModel):
    """Response from icon upload."""

    mediaId: str = Field(..., description="Media ID for the uploaded icon")
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

    createdAt: str = Field(description="ISO 8601 timestamp of creation")
    displayIconId: str = Field(description="Yoto ID for this display icon")
    mediaId: str = Field(description="Media ID used to fetch the icon")
    new: Optional[bool] = Field(None, description="Whether this is a new icon")
    public: bool = Field(description="Whether this icon is publicly available")
    publicTags: Optional[list[str]] = Field(
        default_factory=list, description="Tags for public discovery"
    )
    title: Optional[str] = Field(default=None, description="Human-readable title/name")
    url: str = Field(description="Direct URL to the icon image")
    userId: str = Field(description="User ID of the icon owner")

    model_config = ConfigDict(populate_by_name=True)


class DisplayIconManifest(BaseModel):
    """Container for the list of public display icons from Yoto API."""

    displayIcons: list[DisplayIcon] = Field(
        default_factory=list, description="List of all public icons"
    )

    model_config = ConfigDict(populate_by_name=True)


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
        locale: Optional[str] = None
        bluetooth_enabled: Annotated[Optional[str], Field(alias="bluetoothEnabled")] = None
        repeat_all: Annotated[Optional[bool], Field(alias="repeatAll")] = None
        show_diagnostics: Annotated[Optional[bool], Field(alias="showDiagnostics")] = None
        bt_headphones_enabled: Annotated[
            Optional[bool], Field(alias="btHeadphonesEnabled")
        ] = None
        pause_volume_down: Annotated[Optional[bool], Field(alias="pauseVolumeDown")] = None
        pause_power_button: Annotated[Optional[bool], Field(alias="pausePowerButton")] = None
        display_dim_timeout: Annotated[Optional[str], Field(alias="displayDimTimeout")] = None
        shutdown_timeout: Annotated[Optional[str], Field(alias="shutdownTimeout")] = None
        headphones_volume_limited: Annotated[
            Optional[bool], Field(alias="headphonesVolumeLimited")
        ] = None
        day_time: Annotated[Optional[str], Field(alias="dayTime")] = None
        max_volume_limit: Annotated[Optional[str], Field(alias="maxVolumeLimit")] = None
        ambient_colour: Annotated[Optional[str], Field(alias="ambientColour")] = None
        day_display_brightness: Annotated[
            Optional[str], Field(None, alias="dayDisplayBrightness")
        ] = None
        day_yoto_daily: Annotated[Optional[str], Field(alias="dayYotoDaily")] = None
        day_yoto_radio: Annotated[Optional[str], Field(alias="dayYotoRadio")] = None
        day_sounds_off: Annotated[Optional[str], Field(alias="daySoundsOff")] = None
        night_time: Annotated[Optional[str], Field(alias="nightTime")] = None
        night_max_volume_limit: Annotated[
            Optional[str], Field(alias="nightMaxVolumeLimit")
        ] = None
        night_ambient_colour: Annotated[
            Optional[str], Field(alias="nightAmbientColour")
        ] = None
        night_display_brightness: Annotated[
            Optional[str], Field(None, alias="nightDisplayBrightness")
        ] = None
        night_yoto_daily: Annotated[Optional[str], Field(alias="nightYotoDaily")] = None
        night_yoto_radio: Annotated[Optional[str], Field(alias="nightYotoRadio")] = None
        night_sounds_off: Annotated[Optional[str], Field(alias="nightSoundsOff")] = None
        hour_format: Annotated[Optional[str], Field(alias="hourFormat")] = None
        display_dim_brightness: Annotated[
            Optional[str], Field(None, alias="displayDimBrightness")
        ] = None
        system_volume: Annotated[Optional[str], Field(alias="systemVolume")] = None
        volume_level: Annotated[Optional[str], Field(alias="volumeLevel")] = None
        clock_face: Annotated[Optional[str], Field(alias="clockFace")] = None
        log_level: Annotated[Optional[str], Field(alias="logLevel")] = None
        alarms: Optional[list[ConfigAlarms]] = None

    config: UpdateConfig
