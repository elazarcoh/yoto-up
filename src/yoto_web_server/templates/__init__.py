"""
Templates package - PyDOM components for rendering HTML.
"""

from yoto_web_server.templates.alarms import AlarmCard, AlarmsSection
from yoto_web_server.templates.auth import AuthPage, AuthStatusPartial, DeviceCodeInstructions
from yoto_web_server.templates.base import BaseLayout, Navigation, render_page, render_partial
from yoto_web_server.templates.config_components import (
    ColorPickerSetting,
    ConfigSection,
    SelectSetting,
    SliderSetting,
    TabGroup,
    TimeSetting,
    ToggleSetting,
)
from yoto_web_server.templates.device_detail import (
    AlarmsPanel,
    PlaybackControlPanel,
    SettingsPanel,
    StatusMetric,
)
from yoto_web_server.templates.device_detail import (
    DeviceDetailPage as DeviceDetailPageRefactored,
)
from yoto_web_server.templates.devices import DeviceCard, DeviceDetailPage, DevicesPage
from yoto_web_server.templates.home import HomePage

# Additional component imports
from yoto_web_server.templates.htmx_helpers import (
    ClipboardCopyScript,
    FilePickerScript,
    SortableInitScript,
    ToastNotificationSystem,
    ToggleClassScript,
)
from yoto_web_server.templates.icon_components import (
    IconGridPartial,
    IconImg,
    IconSidebarPartial,
    LazyIconImg,
    LoadingIconIndicator,
    PaginationControls,
)
from yoto_web_server.templates.icons import IconGrid, IconSearchForm, IconSearchResults, IconsPage
from yoto_web_server.templates.playlist_components import (
    ChapterItem as ChapterItemComponent,
)
from yoto_web_server.templates.playlist_components import (
    TrackItem,
)
from yoto_web_server.templates.playlist_detail import (
    EditControlsPartial,
    PlaylistDetail,
)
from yoto_web_server.templates.playlists import (
    ChapterItem,
    PlaylistCard,
    PlaylistDetailPartial,
    PlaylistListPartial,
    PlaylistsPage,
)
from yoto_web_server.templates.upload_components import (
    ActiveUploadsSection,
    JsonDisplayModalPartial,
    NewPlaylistModalPartial,
    UploadModalPartial,
    UploadProgressPartial,
)

__all__ = [
    # Base
    "BaseLayout",
    "Navigation",
    "render_page",
    "render_partial",
    # Home
    "HomePage",
    # Auth
    "AuthPage",
    "AuthStatusPartial",
    "DeviceCodeInstructions",
    # Playlists
    "PlaylistCard",
    "PlaylistsPage",
    "ChapterItem",
    "PlaylistDetailPage",
    # Icons
    "IconGrid",
    "IconSearchForm",
    "IconsPage",
    "IconSearchResults",
    # Devices
    "DeviceCard",
    "DevicesPage",
    "DeviceDetailPage",
    # HTMX Helpers
    "ClipboardCopyScript",
    "FilePickerScript",
    "SortableInitScript",
    "ToastNotificationSystem",
    "ToggleClassScript",
    # Playlist Components
    "ChapterItemComponent",
    "TrackItem",
    # Icon Components
    "IconGridPartial",
    "IconImg",
    "IconSidebarPartial",
    "LazyIconImg",
    "LoadingIconIndicator",
    "PaginationControls",
    # Config Components
    "ColorPickerSetting",
    "ConfigSection",
    "SelectSetting",
    "SliderSetting",
    "TabGroup",
    "TimeSetting",
    "ToggleSetting",
    # Alarms
    "AlarmCard",
    "AlarmsSection",
    # Device Detail
    "AlarmsPanel",
    "DeviceDetailPageRefactored",
    "PlaybackControlPanel",
    "SettingsPanel",
    "StatusMetric",
    # Playlist Detail Refactored
    "EditControlsPartial",
    "PlaylistDetail",
    # Upload Components
    "ActiveUploadsSection",
    "JsonDisplayModalPartial",
    "NewPlaylistModalPartial",
    "UploadModalPartial",
    "UploadProgressPartial",
]
