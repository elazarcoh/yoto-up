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

from yoto_up_server.dependencies import AuthenticatedSessionApiDep, ContainerDep, YotoClientDep
from yoto_up_server.models import Icon, IconMetadata, IconSource, IconSearchRequest, IconSearchResponse
from yoto_up_server.templates.base import render_page, render_partial
from yoto_up_server.templates.icons import (
    IconsPage,
    IconGridPartial as IconGridComponent,
    IconDetailPartial,
)
from yoto_up_server.templates.icon_components import IconGridPartial as IconGridHtmx


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def icons_page(request: Request, yoto_client: YotoClientDep) -> str:
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
    yoto_client: YotoClientDep,
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
        
        icon_dicts = icon_service.search_icons(
            query=search_request.query,
            source=search_request.source,
            fuzzy=search_request.fuzzy,
            threshold=search_request.threshold,
        )
        
        logger.info(f"Found {len(icon_dicts)} icons to convert")
        
        # Build HTML directly instead of using components
        html_parts = []
        for icon_dict in icon_dicts:
            try:
                # Read icon data from file
                icon_path = Path(icon_dict.get("path", ""))
                if icon_path.exists():
                    with open(icon_path, "rb") as f:
                        icon_data = base64.b64encode(f.read()).decode("utf-8")
                    
                    icon_id = icon_dict.get("id", "")
                    name = icon_dict.get("name", "Untitled")
                    icon_url = f"data:image/png;base64,{icon_data}"
                    
                    html_parts.append(f'''
                    <div class="aspect-square bg-white rounded-lg shadow hover:shadow-md transition-all cursor-pointer p-2 flex flex-col items-center justify-center border border-gray-200 hover:border-indigo-500 group"
                         hx-get="/icons/{icon_id}"
                         hx-target="#icon-detail-container"
                         hx-swap="innerHTML">
                        <div class="w-full h-full flex items-center justify-center overflow-hidden">
                            <img src="{icon_url}" alt="{name}" class="max-w-full max-h-full object-contain rendering-pixelated">
                        </div>
                        <div class="mt-1 text-[10px] text-center text-gray-500 truncate w-full group-hover:text-indigo-600">
                            {name}
                        </div>
                    </div>
                    ''')
            except Exception as e:
                logger.warning(f"Failed to convert icon {icon_dict.get('id', 'unknown')}: {e}")
        
        logger.info(f"Successfully built HTML for {len(html_parts)} icons")
        
        return "\n".join(html_parts) if html_parts else '<div class="col-span-full text-center py-12 text-gray-500">No icons found.</div>'
        
    except Exception as e:
        logger.error(f"Failed to search icons: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/online-search", response_class=HTMLResponse)
async def online_search_icons(
    request: Request,
    container: ContainerDep,
    session_api: AuthenticatedSessionApiDep,
    query: str = Query(..., description="Search query"),
):
    """
    Search YotoIcons online.
    
    Returns HTML partial with icon grid.
    """
    try:
        icon_service = container.icon_service()
        icon_dicts = await icon_service.search_online(query=query, session_api=session_api)
        
        # Build HTML directly
        html_parts = []
        for icon_dict in icon_dicts:
            try:
                # Handle both dict and object responses from API
                if hasattr(icon_dict, '__dict__'):
                    icon_dict = icon_dict.__dict__
                
                # Get icon data from API
                icon_id = icon_dict.get("id") or icon_dict.get("mediaId")
                name = icon_dict.get("name") or icon_dict.get("title", "Untitled")
                
                # Try to get thumbnail from API
                icon_url = None
                if icon_dict.get("mediaId"):
                    icon_field = f"yoto:#{icon_dict.get('mediaId')}"
                    # Note: get_icon_b64_data would need to be called on session_api
                    icon_url = icon_dict.get("url") or icon_dict.get("img_url", "")
                
                if not icon_url:
                    icon_url = icon_dict.get("url") or icon_dict.get("img_url", "")
                
                if icon_url:
                    html_parts.append(f'''
                    <div class="aspect-square bg-white rounded-lg shadow hover:shadow-md transition-all cursor-pointer p-2 flex flex-col items-center justify-center border border-gray-200 hover:border-indigo-500 group"
                         hx-get="/icons/{icon_id}"
                         hx-target="#icon-detail-container"
                         hx-swap="innerHTML">
                        <div class="w-full h-full flex items-center justify-center overflow-hidden">
                            <img src="{icon_url}" alt="{name}" class="max-w-full max-h-full object-contain rendering-pixelated">
                        </div>
                        <div class="mt-1 text-[10px] text-center text-gray-500 truncate w-full group-hover:text-indigo-600">
                            {name}
                        </div>
                    </div>
                    ''')
            except Exception as e:
                logger.warning(f"Failed to process online icon: {e}")
        
        return "\n".join(html_parts) if html_parts else '<div class="col-span-full text-center py-12 text-gray-500">No icons found.</div>'
        
    except Exception as e:
        logger.error(f"Failed to search online icons: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/grid", response_class=HTMLResponse)
async def get_icon_grid(
    request: Request,
    session_api: AuthenticatedSessionApiDep,
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
        icons = []
        
        # Search icons based on query
        if query:
            search_results = await session_api.search_cached_icons(
                query=query,
                fields=["title", "publicTags", "category", "tags", "id", "mediaId"],
                show_in_console=False,
                include_yotoicons=include_yotoicons,
            )
            icons = search_results[:limit]
        else:
            # No query: return icons from specified source
            if source and source.lower() == "user":
                user_icons = await session_api.get_user_icons(show_in_console=False, refresh_cache=False)
                icons = user_icons[:limit] if user_icons else []
            elif source and source.lower() == "yotoicons":
                if include_yotoicons:
                    yotoicons = await session_api.get_public_icons(show_in_console=False, refresh_cache=False)
                    icons = yotoicons[:limit] if yotoicons else []
            else:
                # Default: official Yoto icons
                official = await session_api.get_public_icons(show_in_console=False, refresh_cache=False)
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
                b64_data = await session_api.get_icon_b64_data(icon_field)
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
        
        # Build HTML for icon grid - used for playlist icon selection
        html_parts = []
        if icon_objects:
            html_parts.append('<div class="col-span-4 mb-4"><h4 class="font-semibold text-gray-700">')
            html_parts.append(f'{"Search Results" if query else "Icons"} ({len(icon_objects)})')
            html_parts.append('</h4></div>')
            
            for icon_obj in icon_objects:
                icon_id = icon_obj.get("mediaId") or icon_obj.get("id")
                title = icon_obj.get("title", "Untitled")
                thumbnail = icon_obj.get("thumbnail")
                
                if thumbnail:
                    # Build JavaScript inline (not using f-string for JS to avoid escaping issues)
                    html_parts.append('''
                    <button class="w-16 h-16 rounded border-2 border-gray-200 hover:border-indigo-500 hover:shadow-lg transition-all cursor-pointer flex items-center justify-center"
                            title="''' + title + '''"
                            onclick="updateChapterIcon(this, \'''' + icon_id + '''\')"
                            type="button">
                        <img src="''' + thumbnail + '''" alt="''' + title + '''" class="w-full h-full object-cover rounded">
                    </button>
                    ''')
        
        return "\n".join(html_parts) if html_parts else '<div class="col-span-4 p-4 text-center text-gray-500">No icons found</div>'
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get icon grid: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_icons(
    session_api: AuthenticatedSessionApiDep,
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
        icons = []
        
        # Search icons based on query
        if query:
            # Use API's search_cached_icons method which searches all sources
            search_results = await session_api.search_cached_icons(
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
                user_icons = await session_api.get_user_icons(show_in_console=False, refresh_cache=False)
                icons = user_icons[:limit] if user_icons else []
            elif source and source.lower() == "yotoicons":
                # Get YotoIcons
                if include_yotoicons:
                    yotoicons = await session_api.get_public_icons(show_in_console=False, refresh_cache=False)
                    icons = yotoicons[:limit] if yotoicons else []
            else:
                # Get all from Yoto (official)
                official = await session_api.get_public_icons(show_in_console=False, refresh_cache=False)
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
                b64_data = await session_api.get_icon_b64_data(icon_field)
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
    session_api: AuthenticatedSessionApiDep,
):
    """
    Get icon details.

    Returns HTML partial with icon information.
    """
    try:
        icon_service = container.icon_service()
        
        icon_dict = icon_service.get_icon(icon_id)
        
        if not icon_dict:
            raise HTTPException(status_code=404, detail="Icon not found")
        
        # Convert dictionary to Icon object
        icon_path = Path(icon_dict.get("path", ""))
        if icon_path.exists():
            with open(icon_path, "rb") as f:
                icon_data = base64.b64encode(f.read()).decode("utf-8")
            
            icon = Icon(
                id=icon_dict.get("id", ""),
                name=icon_dict.get("name", "Untitled"),
                data=f"data:image/png;base64,{icon_data}",
                metadata=IconMetadata(
                    source=IconSource(icon_dict.get("source", "local"))
                ),
            )
            
            return render_partial(IconDetailPartial(icon=icon))
        else:
            raise HTTPException(status_code=404, detail="Icon file not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get icon {icon_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{icon_id}/image")
async def get_icon_image(
    request: Request,
    icon_id: str,
    session_api: AuthenticatedSessionApiDep,
    size: int = Query(16, description="Icon size"),
):
    """
    Get icon image as base64 data URI or PNG file.
    
    Returns base64 data URI as JSON, or a placeholder if icon is unavailable.
    """
    try:
        # Try to get icon as base64 from API's icon cache
        # The icon_id is the mediaId, so construct the full icon field
        icon_field = f"yoto:#{icon_id}"
        
        logger.debug(f"Getting icon base64 for field: {icon_field}")
        b64_data = await session_api.get_icon_b64_data(icon_field)
        
        if not b64_data:
            logger.warning(f"Failed to get base64 data for icon {icon_id}, returning placeholder")
            # Return a placeholder data URI instead of 404
            # Create a simple gray placeholder SVG
            import base64
            placeholder_svg = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><rect fill="#d1d5db" width="16" height="16"/><circle cx="8" cy="8" r="2" fill="#9ca3af"/></svg>'
            placeholder_b64 = base64.b64encode(placeholder_svg.encode()).decode()
            return {
                "data": f"data:image/svg+xml;base64,{placeholder_b64}"
            }
        
        # Return as JSON with base64 data
        return {
            "data": f"data:image/png;base64,{b64_data}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get icon image {icon_id}: {e}", exc_info=True)
        # Return placeholder instead of 500 error
        import base64
        placeholder_svg = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><rect fill="#ef4444" width="16" height="16" opacity="0.5"/><text x="8" y="10" font-size="10" fill="white" text-anchor="middle" font-weight="bold">!</text></svg>'
        placeholder_b64 = base64.b64encode(placeholder_svg.encode()).decode()
        return {
            "data": f"data:image/svg+xml;base64,{placeholder_b64}"
        }




@router.post("/upload", response_class=HTMLResponse)
async def upload_icon(
    request: Request,
    container: ContainerDep,
    session_api: AuthenticatedSessionApiDep,
    file: UploadFile = File(...),
):
    """
    Upload a new icon.
    
    Returns HTML partial with the uploaded icon.
    """
    try:
        icon_service = container.icon_service()
        
        # Read and process the uploaded file
        content = await file.read()
        
        icon = await icon_service.upload_icon(
            content=content,
            filename=file.filename,
            session_api=session_api,
        )
        
        return render_partial(IconDetailPartial(icon=icon))
        
    except Exception as e:
        logger.error(f"Failed to upload icon: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/from-pixels", response_class=HTMLResponse)
async def create_icon_from_pixels(
    request: Request,
    container: ContainerDep,
    session_api: AuthenticatedSessionApiDep,
):
    """
    Create an icon from pixel data.
    
    Expects JSON body with 16x16 pixel array.
    Returns HTML partial with the created icon.
    """
    try:
        icon_service = container.icon_service()
        
        body = await request.json()
        pixels = body.get("pixels")  # 16x16 array of hex color strings
        name = body.get("name", "Custom Icon")
        
        if not pixels or len(pixels) != 16 or any(len(row) != 16 for row in pixels):
            raise HTTPException(status_code=400, detail="Invalid pixel data: must be 16x16 array")
        
        icon = await icon_service.create_from_pixels(
            pixels=pixels,
            name=name,
            session_api=session_api,
        )
        
        return render_partial(IconDetailPartial(icon=icon))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create icon from pixels: {e}")
        raise HTTPException(status_code=500, detail=str(e))
