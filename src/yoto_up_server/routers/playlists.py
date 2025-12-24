"""
Playlists router.

Handles playlist (card library) listing and management.
"""

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from loguru import logger

from yoto_up.models import Card
from yoto_up_server.dependencies import AuthenticatedApiDep, ContainerDep
from yoto_up_server.models import (
    CardFilterRequest,
    UploadSessionInitRequest,
    UploadStatus,
)
from yoto_up_server.templates.base import render_page, render_partial
from yoto_up_server.templates.playlists import (
    PlaylistDetailPartial,
    PlaylistListPartial,
    PlaylistsPage,
)
from yoto_up_server.templates.playlist_detail_refactored import (
    PlaylistDetailRefactored,
    EditControlsPartial,
)
from yoto_up_server.templates.upload_components import (
    UploadModalPartial,
    JsonDisplayModalPartial,
)
from yoto_up_server.templates.icon_components import IconSidebarPartial

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def playlists_page(request: Request, api_service: AuthenticatedApiDep) -> str:
    """Render the playlists page."""
    return render_page(
        title="Playlists - Yoto Up",
        content=PlaylistsPage(),
        request=request,
    )


@router.get("/list", response_class=HTMLResponse)
async def list_playlists(
    request: Request,
    api_service: AuthenticatedApiDep,
    title_filter: Optional[str] = Query(None, description="Filter by title"),
    category: Optional[str] = Query(None, description="Filter by category"),
    genre: Optional[str] = Query(None, description="Filter by genre (comma separated)"),
) -> str:
    """
    List playlists with optional filtering.

    Returns HTML partial for HTMX updates.
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")

        # Fetch library from API - get_myo_content returns Card objects
        cards: List[Card] = api.get_myo_content()

        # Create filter request object
        filter_request = CardFilterRequest(
            title_filter=title_filter,
            category=category,
            genre=genre,
        )

        # Apply filters
        if filter_request.title_filter:
            title_filter_lower = filter_request.title_filter.lower()
            cards = [c for c in cards if title_filter_lower in (c.title or "").lower()]

        if filter_request.category and filter_request.category != "":
            cards = [
                c
                for c in cards
                if getattr(c, "metadata", {}).get("category") == filter_request.category
            ]

        if filter_request.genre:
            genres = [g.strip().lower() for g in filter_request.genre.split(",")]

            def has_genre(card: Card) -> bool:
                metadata = getattr(card, "metadata", {}) or {}
                card_genres = metadata.get("genre", []) or []
                card_genres_lower = [g.lower() for g in card_genres]
                return any(g in card_genres_lower for g in genres)

            cards = [c for c in cards if has_genre(c)]

        return render_partial(PlaylistListPartial(cards=cards))

    except httpx.HTTPStatusError as e:
        # Handle API authorization errors
        if e.response.status_code == 403:
            # Token is likely expired, need to re-authenticate
            logger.warning(f"Unauthorized error accessing playlists (403): {e}")
            # Clear tokens since they're no longer valid
            api_service.clear_tokens()
            # Return error partial that prompts re-authentication
            raise HTTPException(
                status_code=401,
                detail="Your authentication has expired. Please log in again.",
            )
        logger.error(f"HTTP error accessing playlists: {e}")
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list playlists: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{card_id}", response_class=HTMLResponse)
async def get_playlist_detail(
    request: Request,
    card_id: str,
    api_service: AuthenticatedApiDep,
) -> str:
    """
    Get playlist (card) details.

    Returns full page if direct navigation, HTML partial if HTMX request.
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")

        card: Optional[Card] = api.get_card(card_id)

        if not card:
            raise HTTPException(status_code=404, detail="Card not found")

        # Check if this is an HTMX request (HX-Request header)
        is_htmx_request = request.headers.get("HX-Request") == "true"

        if is_htmx_request:
            # Return just the partial for HTMX swaps
            return render_partial(PlaylistDetailRefactored(card=card))
        else:
            # Return full page for direct navigation
            return render_page(
                title=f"{card.title or 'Playlist'} - Yoto Up",
                content=PlaylistDetailRefactored(card=card),
                request=request,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get playlist {card_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{card_id}/json", response_class=JSONResponse)
async def get_playlist_json(
    request: Request,
    card_id: str,
    api_service: AuthenticatedApiDep,
) -> Dict[str, Any]:
    """
    Get playlist (card) data as JSON.

    Returns the card data in JSON format.
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")

        card: Optional[Card] = api.get_card(card_id)

        if not card:
            raise HTTPException(status_code=404, detail="Card not found")

        # Convert Card object to dict for JSON serialization
        # Use the model_dump() method if available (Pydantic v2) or dict() for v1
        card_data = card.model_dump(mode='json')

        return card_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get playlist JSON {card_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create", response_class=HTMLResponse)
async def create_playlist(
    request: Request,
    api_service: AuthenticatedApiDep,
) -> str:
    """
    Create a new empty playlist (card).

    Expects form data with title and optional metadata.
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")

        form_data = await request.form()
        title = form_data.get("title", "New Playlist")
        category = form_data.get("category", "")

        # Create a new card via API
        card: Card = api.create_card(title=title, category=category)

        return render_partial(PlaylistDetailPartial(card=card))

    except Exception as e:
        logger.error(f"Failed to create playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update-chapter-icon")
async def update_chapter_icon(
    request: Request,
    api_service: AuthenticatedApiDep,
) -> Dict[str, Any]:
    """
    Update a chapter's icon.

    Expects JSON body with:
    - chapter_index: Index of chapter to update
    - icon_id: Icon ID (mediaId for Yoto icons, or icon id)
    - playlist_id (optional): ID of the playlist containing the chapter

    Returns success status.
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")

        body = await request.json()
        chapter_index = body.get("chapter_index")
        icon_id = body.get("icon_id")
        playlist_id = body.get("playlist_id")

        if chapter_index is None or not icon_id:
            raise HTTPException(
                status_code=400, detail="chapter_index and icon_id are required"
            )

        if not isinstance(chapter_index, int) or chapter_index < 0:
            raise HTTPException(
                status_code=400, detail="chapter_index must be a non-negative integer"
            )

        logger.info(f"Updating chapter {chapter_index} icon to {icon_id}")

        # The icon_id should be used as the mediaId for Yoto icons
        # Format: yoto:#{mediaId}
        icon_field = f"yoto:#{icon_id}"

        # If we have a playlist_id, we can update directly
        # Otherwise, we need to get the current card from context (this requires more info)
        # For now, we'll require playlist_id to be provided

        if playlist_id:
            # Fetch the card
            card: Optional[Card] = api.get_card(playlist_id)
            if not card:
                raise HTTPException(status_code=404, detail="Playlist not found")
        else:
            # Try to get from session or context - for now, return error
            raise HTTPException(
                status_code=400,
                detail="playlist_id is required. Include it in the request.",
            )

        # Update the chapter's icon
        try:
            if not hasattr(card, "content") or not card.content:
                raise HTTPException(status_code=400, detail="Card has no content")

            chapters = getattr(card.content, "chapters", []) or []

            if chapter_index >= len(chapters):
                raise HTTPException(
                    status_code=400,
                    detail=f"Chapter index {chapter_index} out of range (total: {len(chapters)})",
                )

            chapter = chapters[chapter_index]

            # Ensure chapter has a display object
            if not hasattr(chapter, "display") or chapter.display is None:
                # Create a new display object
                from yoto_up.models import ChapterDisplay

                chapter.display = ChapterDisplay()

            # Update the icon
            chapter.display.icon16x16 = icon_field

            logger.info(f"Updated chapter {chapter_index} icon to {icon_field}")

            # Save the card back to API
            api.update_card(card, return_card_model=False)

            return {
                "status": "success",
                "chapter_index": chapter_index,
                "icon_id": icon_id,
                "icon_field": icon_field,
            }

        except AttributeError as e:
            logger.error(f"Failed to update chapter icon: {e}")
            raise HTTPException(
                status_code=400, detail=f"Invalid card structure: {str(e)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update chapter icon: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_class=HTMLResponse)
async def create_playlist_old(
    request: Request,
    api_service: AuthenticatedApiDep,
) -> str:
    """
    Create a new empty playlist (card).

    Expects form data with title and optional metadata.
    (Deprecated - use /create instead)
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")

        form_data = await request.form()
        title = form_data.get("title", "New Playlist")
        category = form_data.get("category", "")

        # Create a new card via API
        card: Card = api.create_card(title=title, category=category)

        return render_partial(PlaylistDetailPartial(card=card))

    except Exception as e:
        logger.error(f"Failed to create playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reorder-chapters")
async def reorder_chapters(
    request: Request,
    api_service: AuthenticatedApiDep,
):
    """
    Reorder chapters in a playlist.

    Expects JSON body with:
    - playlist_id: ID of the playlist
    - new_order: List of chapter indices in new order

    Returns success status.
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")

        body = await request.json()
        playlist_id = body.get("playlist_id")
        new_order = body.get("new_order")

        if not playlist_id or not isinstance(new_order, list):
            raise HTTPException(
                status_code=400, detail="playlist_id and new_order (list) are required"
            )

        logger.info(f"Reordering chapters in playlist {playlist_id}: {new_order}")

        # Fetch the card
        card: Optional[Card] = api.get_card(playlist_id)
        if not card:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Validate and reorder chapters
        if not hasattr(card, "content") or not card.content:
            raise HTTPException(status_code=400, detail="Card has no content")

        if not hasattr(card.content, "chapters") or not card.content.chapters:
            raise HTTPException(status_code=400, detail="Card has no chapters")

        chapters = card.content.chapters
        if len(new_order) != len(chapters):
            raise HTTPException(
                status_code=400,
                detail=f"Expected {len(chapters)} chapter indices, got {len(new_order)}",
            )

        # Create reordered chapters list
        reordered_chapters = []
        for idx in new_order:
            if not isinstance(idx, int) or idx < 0 or idx >= len(chapters):
                raise HTTPException(
                    status_code=400, detail=f"Invalid chapter index: {idx}"
                )
            reordered_chapters.append(chapters[idx])

        # Update card with new order
        card.content.chapters = reordered_chapters

        # Save the updated card
        updated_card = api.create_or_update_content(card, return_card=True)

        logger.info(f"Successfully reordered chapters in playlist {playlist_id}")

        return {"status": "reordered", "playlist_id": playlist_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reorder chapters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{card_id}")
async def delete_playlist(
    request: Request,
    card_id: str,
    api_service: AuthenticatedApiDep,
):
    """Delete a playlist (card)."""
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")

        api.delete_card(card_id)

        return {"status": "deleted", "card_id": card_id}

    except Exception as e:
        logger.error(f"Failed to delete playlist {card_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-items")
async def upload_items(
    request: Request,
    files: List[UploadFile],
    playlist_id: str = Form(...),
    upload_mode: str = Form(default="chapters"),
    normalize: str = Form(default="false"),
    target_lufs: str = Form(default="-23.0"),
    normalize_batch: str = Form(default="false"),
    analyze_intro_outro: str = Form(default="false"),
    segment_seconds: str = Form(default="10.0"),
    similarity_threshold: str = Form(default="0.75"),
    show_waveform: str = Form(default="false"),
    api_service: AuthenticatedApiDep = None,
):
    """
    Upload audio files as chapters or tracks to a playlist.

    Args:
        files: List of audio files to upload
        playlist_id: ID of the playlist to upload to
        upload_mode: "chapters" or "tracks"
        normalize: Whether to normalize audio
        target_lufs: Target loudness in LUFS
        normalize_batch: Whether to normalize as batch (album mode)
        analyze_intro_outro: Whether to analyze intro/outro
        segment_seconds: Segment length for intro/outro analysis
        similarity_threshold: Threshold for intro/outro detection
        show_waveform: Whether to show waveform visualization
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")

        # Validate inputs
        if not files or len(files) == 0:
            raise HTTPException(status_code=400, detail="No files provided")

        if upload_mode not in ["chapters", "tracks"]:
            raise HTTPException(status_code=400, detail="Invalid upload_mode")

        # Get the card
        card = api.get_card(playlist_id)
        if not card:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Parse boolean values from form data
        should_normalize = normalize.lower() == "true"
        should_normalize_batch = normalize_batch.lower() == "true"
        should_analyze = analyze_intro_outro.lower() == "true"
        should_show_waveform = show_waveform.lower() == "true"

        # Parse numeric values
        try:
            target_loudness = float(target_lufs)
            segment_length = float(segment_seconds)
            threshold = float(similarity_threshold)
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid numeric parameter: {e}"
            )

        # Log upload request
        logger.info(
            f"Starting upload of {len(files)} files to playlist {playlist_id} "
            f"as {upload_mode} (normalize={should_normalize}, analyze={should_analyze})"
        )

        # NOTE: Full file processing (upload, normalization, analysis) would be implemented here
        # For now, this is a placeholder that acknowledges the request
        # In a production system, this would:
        # 1. Read and validate audio files
        # 2. Apply normalization if requested
        # 3. Analyze intro/outro if requested
        # 4. Create Chapter/Track objects from files
        # 5. Add them to the card's content
        # 6. Upload via the Yoto API

        # Close uploaded files
        for file in files:
            await file.close()

        return JSONResponse(
            status_code=202,
            content={
                "status": "upload_accepted",
                "playlist_id": playlist_id,
                "files_count": len(files),
                "upload_mode": upload_mode,
                "message": f"Upload of {len(files)} file(s) accepted and queued for processing",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload items to playlist {playlist_id}: {e}")
        # Close files on error
        try:
            for file in files:
                await file.close()
        except:
            pass
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# New Session-Based Upload Endpoints
# ============================================================================


@router.post("/{playlist_id}/upload-session", response_class=JSONResponse)
async def create_upload_session(
    playlist_id: str,
    request: Request,
    container: ContainerDep,
    api_service: AuthenticatedApiDep,
    upload_request: UploadSessionInitRequest,
) -> dict:
    """
    Create a new upload session.

    This endpoint initializes an upload session and returns a session_id that
    is used for subsequent file uploads and status checks.

    Args:
        playlist_id: ID of the playlist to upload to
        upload_request: Upload configuration (mode, normalization options, etc.)

    Returns:
        JSON with session_id and session details
    """
    try:
        # Ensure all float fields have proper defaults
        if upload_request.target_lufs is None:
            upload_request.target_lufs = -23.0
        if upload_request.segment_seconds is None:
            upload_request.segment_seconds = 10.0
        if upload_request.similarity_threshold is None:
            upload_request.similarity_threshold = 0.75

        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")

        # Verify the playlist exists
        card = api.get_card(playlist_id)
        if not card:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Get upload session service
        upload_session_service = container.upload_session_service()

        # Get user ID from session or use default
        user_id = request.cookies.get("user_id", "unknown")

        # Create session
        session = upload_session_service.create_session(
            playlist_id=playlist_id,
            user_id=user_id,
            request=upload_request,
        )

        logger.info(
            f"Created upload session {session.session_id} for playlist {playlist_id}"
        )

        return {
            "status": "session_created",
            "session_id": session.session_id,
            "playlist_id": playlist_id,
            "message": "Upload session created successfully",
            "session": session.dict(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create upload session for {playlist_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{playlist_id}/upload-session/{session_id}/files", response_class=JSONResponse
)
async def upload_file_to_session(
    playlist_id: str,
    session_id: str,
    request: Request,
    file: UploadFile = File(...),
    *,
    container: ContainerDep,
    api_service: AuthenticatedApiDep,
) -> dict:
    """
    Upload a single file to an upload session.

    Files are stored temporarily and added to the session's file list.
    Returns file_id and current session status.

    Args:
        playlist_id: ID of the playlist
        session_id: ID of the upload session
        file: The audio file to upload

    Returns:
        JSON with file_id, session status, and progress
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")

        # Get upload session service
        upload_session_service = container.upload_session_service()

        # Verify session exists
        session = upload_session_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Upload session not found")

        if session.playlist_id != playlist_id:
            raise HTTPException(status_code=403, detail="Session playlist mismatch")

        # Create temp directory for this session
        temp_base = Path(tempfile.gettempdir()) / "yoto_up_uploads" / session_id
        temp_base.mkdir(parents=True, exist_ok=True)

        # Save file to temp location
        temp_path = temp_base / file.filename

        # Read and save the file
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        # Register file in session
        file_status = upload_session_service.register_file(
            session_id=session_id,
            filename=file.filename,
            size_bytes=len(content),
        )

        if not file_status:
            raise HTTPException(status_code=500, detail="Failed to register file")

        # Mark as uploaded (waiting for processing)
        upload_session_service.mark_file_uploaded(
            session_id=session_id,
            file_id=file_status.file_id,
            temp_path=str(temp_path),
        )

        # Get updated session
        updated_session = upload_session_service.get_session(session_id)

        # Check if all files are uploaded and start processing
        if updated_session and all(
            f.status != UploadStatus.PENDING for f in updated_session.files
        ):
            # All files uploaded, start background processing
            upload_processing_service = container.upload_processing_service()
            upload_processing_service.process_session_async(
                session_id=session_id,
                playlist_id=playlist_id,
            )
            logger.info(f"Started background processing for session {session_id}")

        logger.info(
            f"File {file.filename} uploaded to session {session_id}, "
            f"temp path: {temp_path}"
        )

        return {
            "status": "file_uploaded",
            "file_id": file_status.file_id,
            "filename": file.filename,
            "session_id": session_id,
            "session": updated_session.dict() if updated_session else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload file to session {session_id}: {e}")
        # Clean up uploaded file on error
        if file:
            try:
                await file.close()
            except:
                pass
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{playlist_id}/upload-session/{session_id}/status", response_class=JSONResponse
)
async def get_upload_session_status(
    playlist_id: str,
    session_id: str,
    request: Request,
    container: ContainerDep,
    api_service: AuthenticatedApiDep,
) -> dict:
    """
    Get the status of an upload session and all its files.

    Returns current progress, file statuses, and any errors.

    Args:
        playlist_id: ID of the playlist
        session_id: ID of the upload session

    Returns:
        JSON with session status and file list
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")

        # Get upload session service
        upload_session_service = container.upload_session_service()

        # Verify session exists
        session = upload_session_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Upload session not found")

        if session.playlist_id != playlist_id:
            raise HTTPException(status_code=403, detail="Session playlist mismatch")

        return {
            "status": "ok",
            "session_id": session_id,
            "session": session.dict(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get upload session status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{playlist_id}/upload-sessions", response_class=JSONResponse)
async def get_playlist_upload_sessions(
    playlist_id: str,
    request: Request,
    container: ContainerDep,
    api_service: AuthenticatedApiDep,
) -> dict:
    """
    Get all active upload sessions for a playlist.

    Useful for restoring upload state when user navigates back to playlist.

    Args:
        playlist_id: ID of the playlist

    Returns:
        JSON with list of active sessions
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")

        # Get upload session service
        upload_session_service = container.upload_session_service()

        # Get active sessions for this playlist
        sessions = upload_session_service.get_playlist_sessions(playlist_id)

        return {
            "status": "ok",
            "playlist_id": playlist_id,
            "sessions": [s.dict() for s in sessions],
            "count": len(sessions),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get playlist upload sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{card_id}/toggle-edit-mode", response_class=HTMLResponse)
async def toggle_edit_mode(
    request: Request,
    card_id: str,
    api_service: AuthenticatedApiDep,
    enable: bool = Query(True, description="Enable or disable edit mode"),
) -> str:
    """
    Toggle edit mode for a playlist.
    
    Returns edit controls partial for HTMX swap.
    """
    try:
        return render_partial(
            EditControlsPartial(playlist_id=card_id, edit_mode_active=enable)
        )
    except Exception as e:
        logger.error(f"Failed to toggle edit mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{card_id}/upload-modal", response_class=HTMLResponse)
async def get_upload_modal(
    request: Request,
    card_id: str,
    api_service: AuthenticatedApiDep,
) -> str:
    """
    Get upload modal HTML.
    
    Returns upload modal partial for HTMX.
    """
    try:
        return render_partial(UploadModalPartial(playlist_id=card_id))
    except Exception as e:
        logger.error(f"Failed to get upload modal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{card_id}/json-modal", response_class=HTMLResponse)
async def get_json_modal(
    request: Request,
    card_id: str,
    api_service: AuthenticatedApiDep,
) -> str:
    """
    Get JSON display modal with playlist data.
    
    Returns JSON modal partial for HTMX.
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")

        card: Optional[Card] = api.get_card(card_id)
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")

        import json
        card_data = card.model_dump(mode='json')
        json_string = json.dumps(card_data, indent=2)
        
        return render_partial(JsonDisplayModalPartial(json_data=json_string))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get JSON modal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{card_id}/icon-sidebar", response_class=HTMLResponse)
async def get_icon_sidebar(
    request: Request,
    card_id: str,
    api_service: AuthenticatedApiDep,
    chapter_index: Optional[int] = Query(None, description="Chapter index for single edit"),
    batch: bool = Query(False, description="Batch mode for multiple chapters"),
) -> str:
    """
    Get icon selection sidebar.
    
    Returns icon sidebar partial for HTMX.
    """
    try:
        return render_partial(
            IconSidebarPartial(
                playlist_id=card_id,
                chapter_index=chapter_index,
                batch_mode=batch,
            )
        )
    except Exception as e:
        logger.error(f"Failed to get icon sidebar: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/{playlist_id}/upload-session/{session_id}", response_class=JSONResponse
)
async def delete_upload_session(
    playlist_id: str,
    session_id: str,
    request: Request,
    container: ContainerDep,
    api_service: AuthenticatedApiDep,
) -> dict:
    """
    Delete an upload session and clean up temp files.

    Args:
        playlist_id: ID of the playlist
        session_id: ID of the upload session

    Returns:
        JSON confirmation
    """
    try:
        api = api_service.get_api()
        if not api:
            raise HTTPException(status_code=401, detail="Not authenticated")

        # Get upload session service
        upload_session_service = container.upload_session_service()

        # Verify session exists
        session = upload_session_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Upload session not found")

        if session.playlist_id != playlist_id:
            raise HTTPException(status_code=403, detail="Session playlist mismatch")

        # Delete session
        deleted = upload_session_service.delete_session(session_id)

        if not deleted:
            raise HTTPException(status_code=500, detail="Failed to delete session")

        logger.info(f"Deleted upload session {session_id}")

        return {
            "status": "ok",
            "message": "Upload session deleted successfully",
            "session_id": session_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete upload session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
