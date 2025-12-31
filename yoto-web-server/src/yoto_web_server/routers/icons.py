"""
Icons router - icon media fetching endpoints.

Handles lazy-loading of icon media with HTMX integration.
Downloads icons from Yoto API on demand using the public manifest.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from typing import List, Literal, Optional
from pydom import html as d
from loguru import logger

from yoto_web_server.dependencies import IconServiceDep, YotoApiDep
from yoto_web_server.templates.icon_components import (
    IconImg,
    LoadingIconIndicator,
    IconGridPartial,
)
from yoto_web_server.templates.base import render_partial
from yoto_web_server.services.icon_service import IconRetrieveSource

router = APIRouter(prefix="/icons", tags=["icons"])


@router.get("/grid", response_class=HTMLResponse)
async def get_icons_grid(
    icon_service: IconServiceDep,
    api_dep: YotoApiDep,
    source: List[IconRetrieveSource] = Query(
        ...,
    ),
    query: Optional[str] = Query(None, description="Search query for titles"),
    fuzzy: bool = Query(True, description="Use fuzzy matching for titles"),
    page: int = Query(1, description="Page number (1-indexed)"),
    per_page: int = Query(50, description="Icons per page"),
):
    """
    Get a grid of icons for selection with advanced search and pagination.

    Search parameters:
    - query: Search titles with optional fuzzy matching
    - fuzzy: Enable fuzzy title matching
    - page: Page number (1-indexed)
    - per_page: Icons per page
    """
    icons, total = await icon_service.get_icons(
        api_client=api_dep,
        sources=source,
        query=query,
        fuzzy=fuzzy,
        page=page,
        per_page=per_page,
    )

    # Determine title based on sources
    if len(source) == 1:
        source_str = str(source[0].value if hasattr(source[0], 'value') else source[0])
        if "user" in source_str:
            title = "My Icons"
        elif "yotoicons" in source_str:
            title = "YotoIcons.com Results" if "online" in source_str else "Cached YotoIcons"
        else:
            title = "Yoto Icons"
    else:
        title = "Yoto Icons"
        
    if query:
        title = f"Search Results for '{query}'"

    return render_partial(IconGridPartial(
        icons=icons,
        title=title,
        total=total,
        page=page,
        per_page=per_page,
        source=source,
        query=query,
        fuzzy=fuzzy,
    ))


@router.get("/{media_id}", response_class=HTMLResponse)
async def get_icon_media(
    media_id: str,
    icon_service: IconServiceDep,
    api_dep: YotoApiDep,
):
    """
    Fetch an icon image by its media ID from the Yoto public icons manifest.

    This endpoint:
    1. Looks up the icon in the public manifest
    2. Downloads the icon from the URL if not cached
    3. Returns an <img> element with the icon, or a polling container if still loading

    Used with HTMX polling - HTMX will retry every 2s if icon is still loading.

    Args:
        media_id: The media ID from DisplayIcon.mediaId
        icon_service: Icon service for fetching icons

    Returns:
        HTML string containing an <img> element once loaded, or a polling container
    """
    try:
        # Normalize media_id (remove yoto:# prefix if present)
        clean_media_id = media_id.removeprefix("yoto:#")

        # Try to get the icon (this downloads if not cached)
        icon_as_url = await icon_service.get_icon_by_media_id(clean_media_id, api_dep)

        if icon_as_url is None:
            logger.debug(
                f"Icon {clean_media_id} still loading, returning polling container"
            )
            # Return a polling container - HTMX will keep polling every 2 seconds
            polling_container = d.Div(
                id=f"icon-{clean_media_id}",
                hx_get=f"/icons/{clean_media_id}",
                hx_trigger="load delay:2s",
                hx_swap="outerHTML",
                classes="inline-block",
            )(
                d.Div(
                    classes="w-6 h-6 flex items-center justify-center",
                    title="Loading icon...",
                )(
                    d.Div(
                        classes="animate-spin h-5 w-5 border-2 border-indigo-500 rounded-full border-t-transparent"
                    )
                )
            )
            return polling_container

        # Success - return the icon image component (this replaces the polling container)
        img = IconImg(icon_id=clean_media_id, title="Icon", src=icon_as_url)
        # Cache response for 1 day
        response = HTMLResponse(content=render_partial(img))
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response

    except Exception as e:
        logger.error(f"Error fetching icon {media_id}: {e}")
        # Return polling container on error - HTMX will keep retrying
        clean_media_id = media_id.removeprefix("yoto:#")
        polling_container = d.Div(
            id=f"icon-{clean_media_id}",
            hx_get=f"/icons/{clean_media_id}",
            hx_trigger="every 2s",
            hx_swap="outerHTML",
            classes="inline-block",
        )(
            d.Div(
                classes="w-6 h-6 flex items-center justify-center text-red-500",
                title="Error loading icon, retrying...",
            )("⚠️")
        )
        return polling_container
    """Search icons and return partial results for HTMX."""
    try:
        icons = icon_service.search_icons(q) if q else icon_service.get_public_icons()[:100]
        return render_partial(IconSearchResults(icons=icons, query=q))
    except Exception as e:
        logger.error(f"Error searching icons: {e}")
        return render_partial(IconSearchResults(icons=[], query=q, error=str(e)))
