"""
Icons router.

Handles icon browsing, searching, and management.
"""

from typing import Optional, List
import base64
from pathlib import Path

from fastapi import APIRouter, Request, Query, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from loguru import logger

from yoto_up_server.dependencies import AuthenticatedApiDep, ContainerDep
from yoto_up_server.models import Icon, IconSource, IconSearchRequest, IconSearchResponse
from yoto_up_server.templates.base import render_page, render_partial
from yoto_up_server.templates.icons import (
    IconsPage,
    IconGridPartial as IconGridComponent,
    IconDetailPartial,
)
from yoto_up_server.templates.icon_components import IconGridPartial as IconGridHtmx


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def icons_page(request: Request, api_service: AuthenticatedApiDep) -> str:
    """Render the icons browser page."""
    return render_page(
        title="Icons - Yoto Up",
        content=IconsPage(),
        request=request,
    )


@router.get("/search", response_class=HTMLResponse)
async def search_icons(
    request: Request,
    container: ContainerDep,
    api_service: AuthenticatedApiDep,
    query: Optional[str] = Query(None, description="Search query"),
    source: Optional[str] = Query(None, description="Source filter: official, yotoicons, local"),
    fuzzy: bool = Query(False, description="Enable fuzzy matching"),
    threshold: float = Query(0.6, ge=0.0, le=1.0, description="Fuzzy match threshold"),
) -> str:
    """
    Search icons.
    
    Returns HTML partial with icon grid.
    """
    try:
        icon_service = container.icon_service()
        
        # Parse source into enum
        icon_source: Optional[IconSource] = None
        if source:
            try:
                icon_source = IconSource(source)
            except ValueError:
                pass
        
        # Create search request
        search_request = IconSearchRequest(
            query=query,
            source=icon_source,
            fuzzy=fuzzy,
            threshold=threshold,
        )
        
        icons = icon_service.search_icons(
            query=search_request.query,
            source=search_request.source,
            fuzzy=search_request.fuzzy,
            threshold=search_request.threshold,
        )
        
        return render_partial(
            IconGridPartial(
                icons=icons,
                query=query,
            )
        )
        
    except Exception as e:
        logger.error(f"Failed to search icons: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/online-search", response_class=HTMLResponse)
async def online_search_icons(
    request: Request,
    container: ContainerDep,
    api_service: AuthenticatedApiDep,
    query: str = Query(..., description="Search query"),
):
    """
    Search YotoIcons online.
    
    Returns HTML partial with icon grid.
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        icon_service = container.icon_service()
        
        icons = icon_service.search_online(query=query, api=api)
        
        return render_partial(
            IconGridPartial(
                icons=icons,
                query=query,
                source="yotoicons",
            )
        )
        
    except Exception as e:
        logger.error(f"Failed to search icons online: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/grid", response_class=HTMLResponse)
async def get_icon_grid(
    request: Request,
    api_service: AuthenticatedApiDep,
    query: Optional[str] = Query(None, description="Search query"),
    source: Optional[str] = Query(None, description="Filter by source: yoto, yotoicons, user"),
    include_yotoicons: bool = Query(True, description="Include YotoIcons in results"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of icons to return"),
) -> str:
    """
    Get icon grid as HTML.
    
    Used by HTMX to populate icon sidebars and grids.
    Returns HTML partial with icon grid.
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        icons = []
        
        # Search icons based on query
        if query:
            search_results = api.search_cached_icons(
                query=query,
                fields=["title", "publicTags", "category", "tags", "id", "mediaId"],
                show_in_console=False,
                include_yotoicons=include_yotoicons,
            )
            icons = search_results[:limit]
        else:
            # No query: return icons from specified source
            if source and source.lower() == "user":
                user_icons = api.get_user_icons(show_in_console=False, refresh_cache=False)
                icons = user_icons[:limit] if user_icons else []
            elif source and source.lower() == "yotoicons":
                if include_yotoicons:
                    yotoicons = api.get_public_icons(show_in_console=False, refresh_cache=False)
                    icons = yotoicons[:limit] if yotoicons else []
            else:
                # Default: official Yoto icons
                official = api.get_public_icons(show_in_console=False, refresh_cache=False)
                icons = official[:limit] if official else []
        
        # Build icon objects with thumbnail URLs
        icon_objects = []
        for icon in icons:
            icon_obj = {
                "id": icon.get("id") or icon.get("displayIconId") or icon.get("mediaId", "unknown"),
                "mediaId": icon.get("mediaId") or icon.get("id"),
                "title": icon.get("title") or icon.get("id") or "Untitled",
            }
            
            # Get thumbnail
            if icon.get("mediaId"):
                icon_field = f"yoto:#{icon.get('mediaId')}"
                b64_data = api.get_icon_b64_data(icon_field)
                if b64_data:
                    icon_obj["thumbnail"] = f"data:image/png;base64,{b64_data}"
            
            if "thumbnail" not in icon_obj and (icon.get("cache_path") or icon.get("cachePath")):
                from pathlib import Path
                import base64
                cache_path = Path(icon.get("cache_path") or icon.get("cachePath"))
                if cache_path.exists():
                    try:
                        img_bytes = cache_path.read_bytes()
                        b64_data = base64.b64encode(img_bytes).decode()
                        icon_obj["thumbnail"] = f"data:image/png;base64,{b64_data}"
                    except Exception:
                        pass
            
            if "thumbnail" not in icon_obj and (icon.get("url") or icon.get("img_url")):
                icon_obj["thumbnail"] = icon.get("url") or icon.get("img_url")
            
            icon_objects.append(icon_obj)
        
        from yoto_up_server.templates.icon_components import IconGridPartial
        return render_partial(
            IconGridHtmx(
                icons=icon_objects,
                title=f"Icons ({len(icon_objects)})" if not query else f"Search Results ({len(icon_objects)})",
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get icon grid: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_icons(
    api_service: AuthenticatedApiDep,
    query: Optional[str] = Query(None, description="Search query"),
    source: Optional[str] = Query(None, description="Filter by source: yoto, yotoicons, user"),
    include_yotoicons: bool = Query(True, description="Include YotoIcons in results"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of icons to return"),
):
    """
    List available icons with optional search and source filtering.
    
    Returns JSON list of icons with thumbnails as base64 data URIs.
    
    Query parameters:
    - query: Search term to filter icons by title, tags, category
    - source: Filter by source (yoto, yotoicons, user)
    - include_yotoicons: Whether to include YotoIcons results (default: true)
    - limit: Maximum number of results (default: 50, max: 200)
    
    Returns:
    - List of icon objects with:
      - id: Icon identifier
      - mediaId: Yoto media ID (for official icons)
      - title: Icon title/name
      - thumbnail: Base64 data URI for thumbnail image
      - source: Source of the icon (yoto, yotoicons, user)
      - tags: List of tags (if available)
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        icons = []
        
        # Search icons based on query
        if query:
            # Use API's search_cached_icons method which searches all sources
            search_results = api.search_cached_icons(
                query=query,
                fields=["title", "publicTags", "category", "tags", "id"],
                show_in_console=False,
                include_yotoicons=include_yotoicons,
            )
            icons = search_results[:limit]
        else:
            # No query: return all cached icons from specified source
            if source and source.lower() == "user":
                # Get user icons
                user_icons = api.get_user_icons(show_in_console=False, refresh_cache=False)
                icons = user_icons[:limit] if user_icons else []
            elif source and source.lower() == "yotoicons":
                # Get YotoIcons
                if include_yotoicons:
                    yotoicons = api.get_public_icons(show_in_console=False, refresh_cache=False)
                    icons = yotoicons[:limit] if yotoicons else []
            else:
                # Get all from Yoto (official)
                official = api.get_public_icons(show_in_console=False, refresh_cache=False)
                icons = official[:limit] if official else []
        
        # Build response with base64 thumbnails
        response_icons = []
        for icon in icons:
            icon_data = {
                "id": icon.get("id") or icon.get("displayIconId") or icon.get("mediaId", "unknown"),
                "mediaId": icon.get("mediaId") or icon.get("id"),
                "title": icon.get("title") or icon.get("id") or "Untitled",
                "tags": icon.get("tags", []) or icon.get("publicTags", []),
                "category": icon.get("category", ""),
            }
            
            # Try to get base64 thumbnail
            # First try mediaId (for official Yoto icons)
            if icon.get("mediaId"):
                icon_field = f"yoto:#{icon.get('mediaId')}"
                b64_data = api.get_icon_b64_data(icon_field)
                if b64_data:
                    icon_data["thumbnail"] = f"data:image/png;base64,{b64_data}"
                    icon_data["source"] = "yoto"
                    response_icons.append(icon_data)
                    continue
            
            # Try cache_path (for YotoIcons)
            if icon.get("cache_path") or icon.get("cachePath"):
                cache_path = Path(icon.get("cache_path") or icon.get("cachePath"))
                if cache_path.exists():
                    try:
                        mime_type = "image/png"
                        ext = cache_path.suffix.lower()
                        if ext in [".jpg", ".jpeg"]:
                            mime_type = "image/jpeg"
                        elif ext == ".svg":
                            mime_type = "image/svg+xml"
                        elif ext == ".gif":
                            mime_type = "image/gif"
                        
                        img_bytes = cache_path.read_bytes()
                        b64_data = base64.b64encode(img_bytes).decode()
                        icon_data["thumbnail"] = f"data:{mime_type};base64,{b64_data}"
                        icon_data["source"] = "yotoicons" if "yotoicons" in str(cache_path).lower() else "user"
                        response_icons.append(icon_data)
                        continue
                    except Exception as e:
                        logger.debug(f"Failed to load cache_path {cache_path}: {e}")
            
            # Try URL (for YotoIcons online)
            if icon.get("url") or icon.get("img_url"):
                icon_data["thumbnail"] = icon.get("url") or icon.get("img_url")
                icon_data["source"] = "yotoicons"
                response_icons.append(icon_data)
                continue
            
            # If no thumbnail available, skip this icon
            logger.debug(f"Icon {icon.get('id')} has no available thumbnail")
        
        return {
            "icons": response_icons,
            "count": len(response_icons),
            "total_requested": len(icons),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list icons: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{icon_id}", response_class=HTMLResponse)
async def get_icon_detail(
    request: Request,
    icon_id: str,
    container: ContainerDep,
    api_service: AuthenticatedApiDep,
):
    """
    Get icon details.
    
    Returns HTML partial with icon information.
    """
    try:
        icon_service = container.icon_service()
        
        icon = icon_service.get_icon(icon_id)
        
        if not icon:
            raise HTTPException(status_code=404, detail="Icon not found")
        
        return render_partial(IconDetailPartial(icon=icon))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get icon {icon_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{icon_id}/image")
async def get_icon_image(
    request: Request,
    icon_id: str,
    api_service: AuthenticatedApiDep,
    size: int = Query(16, description="Icon size"),
):
    """
    Get icon image as base64 data URI or PNG file.
    
    Returns base64 data URI as JSON.
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Try to get icon as base64 from API's icon cache
        # The icon_id is the mediaId, so construct the full icon field
        icon_field = f"yoto:#{icon_id}"
        
        logger.debug(f"Getting icon base64 for field: {icon_field}")
        b64_data = api.get_icon_b64_data(icon_field)
        
        if not b64_data:
            logger.error(f"Failed to get base64 data for icon {icon_id}")
            raise HTTPException(status_code=404, detail="Icon image not found or cannot be cached")
        
        # Return as JSON with base64 data
        return {
            "data": f"data:image/png;base64,{b64_data}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get icon image {icon_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))




@router.post("/upload", response_class=HTMLResponse)
async def upload_icon(
    request: Request,
    container: ContainerDep,
    api_service: AuthenticatedApiDep,
    file: UploadFile = File(...),
):
    """
    Upload a new icon.
    
    Returns HTML partial with the uploaded icon.
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        icon_service = container.icon_service()
        
        # Read and process the uploaded file
        content = await file.read()
        
        icon = icon_service.upload_icon(
            content=content,
            filename=file.filename,
            api=api,
        )
        
        return render_partial(IconDetailPartial(icon=icon))
        
    except Exception as e:
        logger.error(f"Failed to upload icon: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/from-pixels", response_class=HTMLResponse)
async def create_icon_from_pixels(
    request: Request,
    container: ContainerDep,
    api_service: AuthenticatedApiDep,
):
    """
    Create an icon from pixel data.
    
    Expects JSON body with 16x16 pixel array.
    Returns HTML partial with the created icon.
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        icon_service = container.icon_service()
        
        body = await request.json()
        pixels = body.get("pixels")  # 16x16 array of hex color strings
        name = body.get("name", "Custom Icon")
        
        if not pixels or len(pixels) != 16 or any(len(row) != 16 for row in pixels):
            raise HTTPException(status_code=400, detail="Invalid pixel data: must be 16x16 array")
        
        icon = icon_service.create_from_pixels(
            pixels=pixels,
            name=name,
            api=api,
        )
        
        return render_partial(IconDetailPartial(icon=icon))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create icon from pixels: {e}")
        raise HTTPException(status_code=500, detail=str(e))
