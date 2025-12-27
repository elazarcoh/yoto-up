"""
Icons router - icon media fetching endpoints.

Handles lazy-loading of icon media with HTMX integration.
Downloads icons from Yoto API on demand using the public manifest.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from typing import Optional
from pydom import html as d
from loguru import logger

from yoto_up_server.dependencies import IconServiceDep, YotoClientDep
from yoto_up_server.templates.icon_components import (
    IconImg,
    LoadingIconIndicator,
    IconGridPartial,
)
from yoto_up_server.templates.base import render_partial

router = APIRouter(prefix="/icons", tags=["icons"])


@router.get("/grid", response_class=HTMLResponse)
async def get_icons_grid(
    icon_service: IconServiceDep,
    api_dep: YotoClientDep,
    source: str = Query("user", description="Icon source: user, yotoicons, or all"),
    query: Optional[str] = Query(None, description="Search query"),
    limit: int = Query(100, description="Max number of icons"),
) -> str:
    """
    Get a grid of icons for selection.
    """
    icons = await icon_service.get_icons(
        api_client=api_dep,
        source=source,
        query=query,
        limit=limit,
    )

    title = "My Icons" if source == "user" else "Yoto Icons"
    if query:
        title = f"Search Results for '{query}'"

    return render_partial(IconGridPartial(icons=icons, title=title))


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
            logger.debug(f"Icon {clean_media_id} still loading, returning polling container")
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
            return render_partial(polling_container)

        # Success - return the icon image component (this replaces the polling container)
        return render_partial(IconImg(icon_id=clean_media_id, title="Icon", src=icon_as_url))

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
        return render_partial(polling_container)
