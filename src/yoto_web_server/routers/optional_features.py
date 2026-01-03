"""Router for optional features endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from pydom import html as d

from yoto_web_server.dependencies import (
    OptionalFeaturesDep,
    YouTubeFeatureDep,
)
from yoto_web_server.templates.base import render_page
from yoto_web_server.templates.optional_features_components import (
    FeatureCard,
)

router = APIRouter(prefix="/features", tags=["features"])


def _get_youtube_details(youtube_feature: YouTubeFeatureDep) -> d.Div | None:
    """Get YouTube-specific details component."""
    download_method = youtube_feature.get_download_method()
    version = youtube_feature.get_version()

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

    details.append(
        d.Button(
            classes="mt-4 px-4 py-2 bg-indigo-600 text-white rounded-md font-medium hover:bg-indigo-700 transition-colors",
            hx_get="/youtube/upload-modal/",
            hx_target="#youtube-upload-modal",
            hx_swap="outerHTML",
        )("Upload from YouTube")
    )

    return d.Div(classes="space-y-3")(*details) if details else None


@router.get("/", response_class=HTMLResponse, response_model=None)
async def features_page(
    request: Request,
    features_service: OptionalFeaturesDep,
    youtube_feature: YouTubeFeatureDep,
) -> str:
    """Render the optional features status page."""
    features = features_service.get_all_features()

    # Build feature cards with details
    feature_cards = []
    for feature_status in features:
        details = None

        # Add YouTube-specific details
        if feature_status.identifier == "youtube_upload":
            if feature_status.available:
                details = _get_youtube_details(youtube_feature)

        feature_cards.append(FeatureCard(status=feature_status, details=details))

    content = d.Div(classes="space-y-6")(
        d.Div(classes="bg-white rounded-lg shadow p-6")(
            d.H2(classes="text-2xl font-bold text-gray-900")("Optional Features"),
            d.P(classes="mt-2 text-gray-600")(
                f"Status: {sum(1 for f in features if f.available)} of {len(features)} features available"
            ),
        ),
        d.Div(classes="grid grid-cols-1 md:grid-cols-2 gap-6")(*feature_cards),
        # Hidden container for YouTube upload modal
        d.Div(id="youtube-upload-modal", classes="hidden"),
    )

    return render_page(
        request=request,
        content=content,
        title="Optional Features",
        is_authenticated=True,
    )
