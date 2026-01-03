"""YouTube feature UI components."""

from pydom import Component
from pydom import html as d

from yoto_web_server.features.youtube.service import YouTubeMetadata
from yoto_web_server.features.youtube import YouTubeFeature


class YouTubeFeatureCard(Component):
    """Card for YouTube feature in the feature details."""

    def __init__(self, feature: YouTubeFeature) -> None:
        self.feature = feature

    def render(self):
        """Render YouTube feature details card."""
        download_method = self.feature.get_download_method()
        version = self.feature.get_version()

        details = []
        if download_method:
            details.append(
                d.Div(classes="flex items-center gap-2 text-sm text-gray-600")(
                    d.Span(classes="font-medium")("Download Method:"),
                    d.Span(classes="font-mono bg-gray-100 px-2 py-1 rounded")(download_method),
                )
            )

        if version:
            details.append(
                d.Div(classes="flex items-center gap-2 text-sm text-gray-600")(
                    d.Span(classes="font-medium")("Version:"),
                    d.Span(classes="font-mono bg-gray-100 px-2 py-1 rounded")(version),
                )
            )

        return d.Div(classes="space-y-3")(
            *details,
        )


class YouTubeUploadModal(Component):
    """Modal for entering YouTube URL."""

    def __init__(self, show: bool = True) -> None:
        self.show = show

    def render(self):
        """Render the upload modal."""
        if not self.show:
            return d.Div(id="youtube-upload-modal", classes="hidden")

        return d.Div(
            id="youtube-upload-modal",
            classes="fixed inset-0 bg-black/50 flex items-center justify-center z-50",
        )(
            d.Div(classes="bg-white rounded-lg shadow-xl max-w-md w-full p-6")(
                d.Div(classes="flex justify-between items-center mb-4")(
                    d.H2(classes="text-xl font-bold text-gray-900")("Upload from YouTube"),
                    d.Button(
                        classes="text-gray-500 hover:text-gray-700",
                        hx_post="/youtube/upload-modal/close/",
                        hx_target="#youtube-upload-modal",
                        hx_swap="outerHTML",
                    )("✕"),
                ),
                d.Form(
                    classes="space-y-4",
                    id="youtube-upload-form",
                    hx_post="/youtube/use-url/",
                    hx_target="#pending-urls-list",
                    hx_swap="beforeend",
                )(
                    d.Div(classes="space-y-2")(
                        d.Label(
                            htmlFor="youtube-url",
                            classes="block text-sm font-medium text-gray-700",
                        )("YouTube URL or Video ID"),
                        d.Input(
                            type="text",
                            id="youtube-url",
                            name="youtube_url",
                            placeholder="https://www.youtube.com/watch?v=... or VIDEO_ID",
                            classes="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500",
                            required=True,
                        ),
                    ),
                    d.Div(classes="flex gap-2 justify-end")(
                        d.Button(
                            type="submit",
                            classes="px-4 py-2 text-white bg-indigo-600 rounded-md hover:bg-indigo-700 transition-colors",
                        )("Fetch Metadata"),
                        d.Button(
                            type="button",
                            classes="px-4 py-2 text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300 transition-colors",
                            hx_post="/youtube/upload-modal/close/",
                            hx_target="#youtube-upload-modal",
                            hx_swap="outerHTML",
                        )("Cancel"),
                    ),
                ),
            ),
        )


class YouTubeMetadataPreview(Component):
    """Preview of YouTube video metadata before upload."""

    def __init__(self, metadata: YouTubeMetadata) -> None:
        self.metadata = metadata

    def render(self):
        """Render metadata preview."""
        return d.Div(
            id="youtube-metadata-preview",
            classes="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-4",
        )(
            d.Div(classes="flex gap-4")(
                d.Img(
                    src=self.metadata.thumbnail_url,
                    alt=self.metadata.title,
                    classes="w-24 h-24 rounded object-cover",
                ),
                d.Div(classes="flex-1 space-y-2")(
                    d.H3(classes="font-semibold text-gray-900")(self.metadata.title),
                    d.P(classes="text-sm text-gray-600")(f"By {self.metadata.uploader}"),
                    d.P(classes="text-sm text-gray-600")(f"Duration: {self._format_duration()}"),
                    d.P(classes="text-sm text-gray-600")(f"Uploaded: {self.metadata.upload_date}"),
                ),
            ),
            d.Div(classes="text-sm text-gray-600 line-clamp-3")(self.metadata.description),
            d.Form(
                classes="flex gap-2 justify-end",
                hx_post="/youtube/add-to-pending/",
                hx_target="#pending-urls-list",
                hx_swap="beforeend",
            )(
                d.Input(type="hidden", name="video_id", value=self.metadata.video_id),
                d.Input(type="hidden", name="title", value=self.metadata.title),
                d.Input(
                    type="hidden",
                    name="duration_seconds",
                    value=str(self.metadata.duration_seconds),
                ),
                d.Button(
                    type="submit",
                    classes="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition-colors font-medium",
                )("Add to Upload"),
            ),
        )

    def _format_duration(self) -> str:
        """Format duration to MM:SS or HH:MM:SS."""
        seconds = self.metadata.duration_seconds
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"


class YouTubeUploadingIndicator(Component):
    """Shows uploading progress."""

    def __init__(self, video_title: str) -> None:
        self.video_title = video_title

    def render(self):
        """Render uploading indicator."""
        return d.Div(
            id="youtube-upload-modal",
            classes="fixed inset-0 bg-black/50 flex items-center justify-center z-50",
        )(
            d.Div(classes="bg-white rounded-lg shadow-xl max-w-md w-full p-6 text-center")(
                d.Div(
                    classes="animate-spin h-12 w-12 border-4 border-indigo-500 rounded-full border-t-transparent mx-auto mb-4"
                ),
                d.P(classes="text-gray-700 font-medium")("Downloading and processing..."),
                d.P(classes="text-sm text-gray-600 mt-2")(self.video_title),
            ),
        )


class YouTubePendingURLEntry(Component):
    """Displays a pending YouTube URL entry in the pending URLs list."""

    def __init__(
        self,
        task_id: str,
        youtube_url: str,
        is_loading: bool = True,
        title: str | None = None,
        duration_seconds: int | None = None,
    ) -> None:
        self.task_id = task_id
        self.youtube_url = youtube_url
        self.is_loading = is_loading
        self.title = title
        self.duration_seconds = duration_seconds

    def render(self):
        """Render a pending URL entry."""
        entry_id = f"youtube-pending-{self.task_id}"
        # attrs = {
        #     "id": entry_id,
        #     "classes": "flex items-center justify-between bg-white border border-gray-200 rounded p-2 text-sm",
        #     "data-youtube-url": self.youtube_url,
        # }

        if self.is_loading:
            # Loading state with HTMX polling
            return d.Div(
                id=entry_id,
                classes="flex items-center justify-between bg-white border border-gray-200 rounded p-2 text-sm",
                hx_get=f"/youtube/pending/{self.task_id}/",
                hx_trigger="load delay:1s",
                hx_swap="outerHTML",
            )(
                d.Div(classes="flex-1 flex items-center gap-3")(
                    d.Div(
                        classes="animate-spin h-4 w-4 border-2 border-indigo-500 rounded-full border-t-transparent"
                    ),
                    d.Div(
                        d.P(classes="text-xs text-gray-600")("Fetching metadata..."),
                        d.P(classes="text-xs text-gray-400 font-mono")(
                            self.youtube_url[:50] + "..."
                            if len(self.youtube_url) > 50
                            else self.youtube_url
                        ),
                    ),
                ),
                d.Button(
                    type="button",
                    classes="text-red-600 hover:text-red-800 font-semibold text-sm ml-2",
                    hx_delete=f"/youtube/pending/{self.task_id}/",
                    hx_target=f"#{entry_id}",
                    hx_swap="outerHTML swap:1s",
                )("✕"),
            )
        else:
            # Completed state showing metadata
            if self.title is None or self.duration_seconds is None:
                return d.Div(
                    id=entry_id,
                    classes="flex items-center justify-between bg-white border border-red-200 rounded p-2 text-sm",
                    data_youtube_url=self.youtube_url,
                )(
                    d.Div(classes="flex-1")(
                        d.P(classes="font-medium text-red-600")("Failed to fetch metadata"),
                        d.P(classes="text-xs text-gray-500")(self.youtube_url),
                    ),
                    d.Button(
                        type="button",
                        classes="text-red-600 hover:text-red-800 font-semibold text-sm ml-2",
                        hx_delete=f"/youtube/pending/{self.task_id}/",
                        hx_target=f"#{entry_id}",
                        hx_swap="outerHTML swap:1s",
                    )("✕"),
                )

            minutes = self.duration_seconds // 60
            seconds = self.duration_seconds % 60

            return d.Div(
                id=entry_id,
                classes="flex items-center justify-between bg-white border border-green-200 rounded p-2 text-sm",
                data_youtube_url=self.youtube_url,
            )(
                d.Div(classes="flex-1")(
                    d.P(classes="font-medium text-gray-900 truncate")(self.title),
                    d.P(classes="text-xs text-gray-500")(f"Duration: {minutes}:{seconds:02d}"),
                ),
                d.Button(
                    type="button",
                    classes="text-red-600 hover:text-red-800 font-semibold text-sm ml-2",
                    hx_delete=f"/youtube/pending/{self.task_id}/",
                    hx_target=f"#{entry_id}",
                    hx_swap="outerHTML swap:1s",
                )("✕"),
            )
