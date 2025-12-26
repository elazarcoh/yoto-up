"""
Icons router - icon media fetching endpoints.

Handles lazy-loading of icon media with HTMX integration.
Downloads icons from Yoto API on demand using the public manifest.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from loguru import logger

from yoto_up_server.dependencies import IconServiceDep, YotoClientDep
from yoto_up_server.templates.icon_components import IconImg, LoadingIconIndicator
from yoto_up_server.templates.base import render_partial

router = APIRouter(prefix="/icons", tags=["icons"])


@router.get("/{media_id}", response_class=HTMLResponse)
async def get_icon_media(
    media_id: str,
    icon_service: IconServiceDep,
    api_dep: YotoClientDep,
) -> str:
    """
    Fetch an icon image by its media ID from the Yoto public icons manifest.

    This endpoint:
    1. Looks up the icon in the public manifest
    2. Downloads the icon from the URL if not cached
    3. Returns an <img> element with the icon

    Used with HTMX polling - caller should retry if icon is still loading.

    Args:
        media_id: The media ID from DisplayIcon.mediaId
        icon_service: Icon service for fetching icons

    Returns:
        HTML string containing an <img> element
    """
    try:
        # Try to get the icon (this downloads if not cached)
        icon_bytes = await icon_service.get_icon_by_media_id(media_id, api_dep)

        if icon_bytes is None:
            logger.warning(f"Icon {media_id} not found or failed to download")
            # Return retry indicator - HTMX will keep polling
            return render_partial(
                LoadingIconIndicator(media_id=media_id, status="not_found")
            )

        # Success - return the icon image component
        return render_partial(
            _create_icon_img(media_id=media_id, icon_bytes=icon_bytes)
        )

    except Exception as e:
        logger.error(f"Error fetching icon {media_id}: {e}")
        # Return retry indicator on error
        return render_partial(LoadingIconIndicator(media_id=media_id, status="error"))


def _create_icon_img(media_id: str, icon_bytes: bytes) -> "IconImg":
    """
    Helper to create IconImg with base64-encoded icon bytes.

    Args:
        media_id: The icon media ID
        icon_bytes: Raw icon image bytes

    Returns:
        IconImg component with data URL
    """
    import base64

    # Detect image type from content (basic detection)
    if icon_bytes.startswith(b"\x89PNG"):
        mime_type = "image/png"
    elif icon_bytes.startswith(b"\xff\xd8\xff"):
        mime_type = "image/jpeg"
    elif icon_bytes.startswith(b"GIF"):
        mime_type = "image/gif"
    elif icon_bytes.startswith(b"WEBP"):
        mime_type = "image/webp"
    else:
        mime_type = "image/png"  # default

    base64_data = base64.b64encode(icon_bytes).decode("utf-8")
    src = f"data:{mime_type};base64,{base64_data}"

    return IconImg(icon_id=media_id, title=f"Icon", src=src)


@router.get("/{media_id}/raw")
async def get_icon_raw(
    media_id: str,
    icon_service: IconServiceDep,
    api_dep: YotoClientDep,
) -> StreamingResponse:
    """
    Fetch raw icon bytes by media ID.

    Returns the image with appropriate content-type header.

    Args:
        media_id: The media ID from DisplayIcon.mediaId
        icon_service: Icon service for fetching icons

    Returns:
        Raw image bytes with appropriate content-type
    """
    try:
        icon_bytes = await icon_service.get_icon_by_media_id(media_id, api_dep)

        if icon_bytes is None:
            raise HTTPException(status_code=404, detail="Icon not found")

        # Detect MIME type from content
        if icon_bytes.startswith(b"\x89PNG"):
            media_type = "image/png"
        elif icon_bytes.startswith(b"\xff\xd8\xff"):
            media_type = "image/jpeg"
        elif icon_bytes.startswith(b"GIF"):
            media_type = "image/gif"
        elif icon_bytes.startswith(b"WEBP"):
            media_type = "image/webp"
        else:
            media_type = "application/octet-stream"

        return StreamingResponse(
            iter([icon_bytes]),
            media_type=media_type,
        )

    except Exception as e:
        logger.error(f"Error fetching raw icon {media_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching icon: {str(e)}")
