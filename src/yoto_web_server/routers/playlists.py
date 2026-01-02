"""
Playlists router.

Handles playlist (card library) listing and management.
"""

import base64
import json
import pathlib
import tempfile
from typing import Annotated, Any

import httpx
from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import HTMLResponse, JSONResponse
from loguru import logger
from pydom import Renderable
from pydom import html as d

from yoto_web_server.api.models import (
    Card,
    CardCover,
    CardMetadata,
    Category,
    ChapterDisplay,
    NewCardRequest,
    TrackDisplay,
)
from yoto_web_server.dependencies import (
    ContainerDep,
    IconServiceDep,
    UploadProcessingServiceDep,
    UploadSessionServiceDep,
    YotoApiDep,
)
from yoto_web_server.models import (
    CardFilterRequest,
    DeletePlaylistResponse,
    FileUploadResponse,
    ReorderChaptersRequest,
    ReorderChaptersResponse,
    UploadSessionInitRequest,
    UploadSessionResponse,
    UploadSessionStatusResponse,
)
from yoto_web_server.templates.base import render_page, render_partial
from yoto_web_server.templates.icon_components import (
    IconSidebarPartial,
)
from yoto_web_server.templates.playlist_components import ChapterItem, CoverModalPartial
from yoto_web_server.templates.playlist_detail import (
    EditControlsPartial,
    PlaylistDetail,
)
from yoto_web_server.templates.playlists import (
    PlaylistDetailPartial,
    PlaylistListPartial,
    PlaylistsPage,
)
from yoto_web_server.templates.upload_components import (
    JsonDisplayModalPartial,
    NewPlaylistModalPartial,
    UploadModalPartial,
    UploadSessionsListPartial,
)

router = APIRouter()


@router.get("/modal/new", response_class=HTMLResponse)
async def new_playlist_modal(request: Request, yoto_client: YotoApiDep) -> str:
    """Serve the new playlist creation modal."""
    return render_partial(NewPlaylistModalPartial())


@router.get("/", response_class=HTMLResponse)
async def playlists_page(request: Request, yoto_client: YotoApiDep) -> str:
    """Render the playlists page."""
    return render_page(
        title="Playlists - Yoto Web Server",
        content=PlaylistsPage(),
        request=request,
    )


@router.get("/list", response_class=HTMLResponse)
async def list_playlists(
    request: Request,
    yoto_client: YotoApiDep,
    title_filter: str | None = Query(None, description="Filter by title"),
    category: str | None = Query(None, description="Filter by category"),
    genre: str | None = Query(None, description="Filter by genre (comma separated)"),
) -> str:
    """
    List playlists with optional filtering.

    Returns HTML partial for HTMX updates.
    """
    try:
        # Fetch library from API - get_my_content returns Card objects
        cards: list[Card] = await yoto_client.get_my_content()

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


@router.get("/{playlist_id}", response_class=HTMLResponse)
async def get_playlist_detail(
    request: Request,
    playlist_id: Annotated[str, Path()],
    yoto_client: YotoApiDep,
    new_chapters: str | None = Query(
        None, description="Comma-separated list of new chapter indices"
    ),
) -> str:
    """
    Get playlist (card) details.

    Returns full page if direct navigation, HTML partial if HTMX request.
    """
    try:
        card: Card | None = await yoto_client.get_card(playlist_id)

        if not card:
            raise HTTPException(status_code=404, detail="Card not found")

        # Parse new chapters
        new_chapters_list = []
        if new_chapters:
            new_chapters_list = [idx.strip() for idx in new_chapters.split(",") if idx.strip()]

        # Check if this is an HTMX request (HX-Request header)
        is_htmx_request = request.headers.get("HX-Request") == "true"

        if is_htmx_request:
            # Return just the partial for HTMX swaps
            return render_partial(
                PlaylistDetail(card=card, playlist_id=playlist_id, new_chapters=new_chapters_list)
            )
        else:
            # Return full page for direct navigation
            return render_page(
                title=f"{card.title or 'Playlist'} - Yoto Web Server",
                content=PlaylistDetail(
                    card=card, playlist_id=playlist_id, new_chapters=new_chapters_list
                ),
                request=request,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get playlist {playlist_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{playlist_id}/json", response_class=JSONResponse)
async def get_playlist_json(
    request: Request,
    playlist_id: Annotated[str, Path()],
    yoto_client: YotoApiDep,
) -> dict[str, Any]:
    """
    Get playlist (card) data as JSON.

    Returns the card data in JSON format.
    """
    try:
        card: Card | None = await yoto_client.get_card(playlist_id)

        if not card:
            raise HTTPException(status_code=404, detail="Card not found")

        # Convert Card object to dict for JSON serialization
        # Use the model_dump() method if available (Pydantic v2) or dict() for v1
        card_data = card.model_dump(mode="json")

        return card_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get playlist JSON {playlist_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create", response_class=HTMLResponse)
async def create_playlist(
    request: Request,
    yoto_client: YotoApiDep,
    title: Annotated[str, Form(..., description="Playlist title")],
) -> str:
    """
    Create a new empty playlist (card).

    Expects form data with title and optional category.
    """
    try:
        # Create a new card via API
        card: Card = await yoto_client.create_card(NewCardRequest(title=title))

        return render_partial(PlaylistDetailPartial(card=card, playlist_id=card.card_id))

    except Exception as e:
        logger.error(f"Failed to create playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-with-cover", response_class=HTMLResponse)
async def create_playlist_with_cover(
    request: Request,
    yoto_client: YotoApiDep,
    title: Annotated[str, Form(..., description="Playlist title")],
    cover: Annotated[UploadFile | None, File(description="Cover image file")] = None,
    category: Annotated[Category | None, Form(description="Category")] = None,
) -> str:
    """
    Create a new playlist with optional cover image.

    Expects form data with:
    - title: Playlist title
    - cover (optional): Cover image file
    - category (optional): Playlist category

    Returns updated page with new playlist detail.
    """
    try:
        # Create a new card via API
        card: Card = await yoto_client.create_card(
            NewCardRequest(
                title=title,
                metadata=CardMetadata(category=category) if category else None,
            )
        )

        # If cover image provided, upload it
        if cover:
            cover_content = await cover.read()
            # Upload cover image via API
            # This would require an API method to upload cover images
            # For now, just create the card without cover
            logger.info(f"Cover upload for playlist {card.card_id} not yet implemented")

        return render_partial(PlaylistDetailPartial(card=card, playlist_id=card.card_id))

    except Exception as e:
        logger.error(f"Failed to create playlist with cover: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{playlist_id}/icon-sidebar", response_class=HTMLResponse)
async def get_icon_selection_sidebar(
    playlist_id: str,
    request: Request,
    chapter_ids: list[int] = Query(default=[]),
    track_ids: list[str] = Query(default=[]),
) -> str:
    """Serve the icon selection sidebar for batch selection."""
    parsed_track_ids: list[tuple[int, int]] = []
    for tr in track_ids:
        try:
            ch_idx_str, tr_idx_str = tr.split(":")
            ch_idx = int(ch_idx_str)
            tr_idx = int(tr_idx_str)
            parsed_track_ids.append((ch_idx, tr_idx))
        except (ValueError, IndexError):
            continue
    return render_partial(
        IconSidebarPartial(
            playlist_id=playlist_id,
            chapter_ids=chapter_ids,
            track_ids=parsed_track_ids,
        )
    )


@router.post("/{playlist_id}/update-items-icon", response_class=HTMLResponse)
async def update_playlist_items_icon(
    playlist_id: str,
    request: Request,
    yoto_client: YotoApiDep,
    icon_service: IconServiceDep,
    icon_id: str = Form(...),
    chapter_ids: list[int] = Form(default=[]),
    track_ids: list[tuple[int, int]] = Form(default=[]),
) -> str:
    """
    Update icons for multiple chapters/tracks.
    """
    if not icon_id:
        raise HTTPException(status_code=400, detail="icon_id is required")

    # Resolve icon ID (handles yotoicons provisioning)
    try:
        resolved_icon_id = await icon_service.resolve_media_id(icon_id, yoto_client)
    except ValueError as e:
        logger.error(f"Failed to resolve icon ID: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    # Fetch the card
    card: Card | None = await yoto_client.get_card(playlist_id)
    if not card:
        raise HTTPException(status_code=404, detail="Playlist not found")

    chapters = card.content.chapters if card.content and card.content.chapters else []

    icon_val = resolved_icon_id
    if not icon_val.startswith("yoto:#"):
        icon_val = f"yoto:#{icon_val}"

    logger.debug(f"Resolved icon value: {icon_val!r} (length: {len(icon_val)})")

    tracks_by_chapter: dict[int, list[int]] = {}
    for ch_id, tr_id in track_ids:
        tracks_by_chapter.setdefault(ch_id, []).append(tr_id)

    updated = False
    # Update chapters
    for ch_idx in chapter_ids:
        if 0 <= ch_idx < len(chapters):
            chapter = chapters[ch_idx]
            display = chapter.display
            if not display:
                display = ChapterDisplay()
            if display.icon_16x16 != icon_val:
                display.icon_16x16 = icon_val
                chapter.display = display
                updated = True

            # Update tracks
            if ch_idx in tracks_by_chapter:
                for tr_idx in tracks_by_chapter[ch_idx]:
                    if 0 <= tr_idx < len(chapter.tracks):
                        track = chapter.tracks[tr_idx]
                        display = track.display
                        if not display:
                            display = TrackDisplay()
                        if display.icon_16x16 != icon_val:
                            display.icon_16x16 = icon_val
                            track.display = display
                            updated = True

    if updated:
        # Save the card
        await yoto_client.update_card(card)

    # Return updated detail view
    return render_partial(PlaylistDetail(card=card, playlist_id=card.card_id))


@router.post("/reorder-chapters", response_class=JSONResponse)
async def reorder_chapters(
    request: Request,
    yoto_client: YotoApiDep,
    payload: ReorderChaptersRequest,
) -> ReorderChaptersResponse:
    """
    Reorder chapters in a playlist.

    Expects JSON body with:
    - playlist_id: ID of the playlist
    - new_order: List of chapter indices in new order

    Returns success status.
    """
    try:
        playlist_id = payload.playlist_id
        new_order = payload.new_order

        logger.info(f"Reordering chapters in playlist {playlist_id}: {new_order}")

        # Fetch the card
        card: Card | None = await yoto_client.get_card(playlist_id)
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
                raise HTTPException(status_code=400, detail=f"Invalid chapter index: {idx}")
            reordered_chapters.append(chapters[idx])

        # Update card with new order
        card.content.chapters = reordered_chapters

        # Save the updated card
        updated_card = await yoto_client.update_card(card)

        logger.info(f"Successfully reordered chapters in playlist {playlist_id}")

        return ReorderChaptersResponse(status="reordered", playlist_id=playlist_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reorder chapters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{playlist_id}/delete-selected", response_class=HTMLResponse)
async def delete_selected_chapters(
    request: Request,
    playlist_id: Annotated[str, Path()],
    chapter_ids: Annotated[list[int], Form()],
    yoto_client: YotoApiDep,
) -> str:
    """
    Delete selected chapters from a playlist.

    Expects form data with chapter IDs as form values (e.g., checkbox values).
    The HTMX request will include checked checkbox values like: data_chapter_id=0&data_chapter_id=2

    Returns updated chapters list partial.
    """
    try:
        if not chapter_ids:
            raise HTTPException(status_code=400, detail="No chapters selected")

        logger.info(f"Deleting chapters {chapter_ids} from playlist {playlist_id}")

        # Fetch the card
        card: Card | None = await yoto_client.get_card(playlist_id)
        if not card:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Validate and delete chapters
        if not hasattr(card, "content") or not card.content:
            raise HTTPException(status_code=400, detail="Card has no content")

        if not hasattr(card.content, "chapters") or not card.content.chapters:
            raise HTTPException(status_code=400, detail="Card has no chapters")

        chapters = card.content.chapters

        # Validate all indices
        for idx in chapter_ids:
            if not isinstance(idx, int) or idx < 0 or idx >= len(chapters):
                raise HTTPException(status_code=400, detail=f"Invalid chapter index: {idx}")

        # Sort indices in descending order to avoid shifting issues
        chapter_ids_sorted = sorted(chapter_ids, reverse=True)

        # Delete chapters starting from the highest index
        for idx in chapter_ids_sorted:
            chapters.pop(idx)

        # Save the updated card
        await yoto_client.update_card(card)

        logger.info(f"Successfully deleted {len(chapter_ids)} chapters from playlist {playlist_id}")

        # Return updated chapters list - just the <ul> element for HTMX to swap
        chapters_list = []
        if (
            hasattr(card, "content")
            and card.content
            and hasattr(card.content, "chapters")
            and card.content.chapters
        ):
            chapters_list = [
                ChapterItem(chapter=chapter, index=i, card_id=card.card_id)
                for i, chapter in enumerate(card.content.chapters)
            ]

        chapters_ul = (
            d.Ul(id="chapters-list", classes="divide-y divide-gray-100")(*chapters_list)
            if chapters_list
            else d.Div(classes="px-6 py-8 sm:px-8 text-center text-gray-500")("No items found.")
        )

        return render_partial(chapters_ul)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete chapters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{playlist_id}/change-cover", response_class=HTMLResponse)
async def change_cover(
    request: Request,
    playlist_id: Annotated[str, Path()],
    yoto_client: YotoApiDep,
    cover: Annotated[UploadFile | None, File()] = None,
) -> str:
    """
    Change cover image for a playlist.

    Expects file upload with 'cover' field containing image file.

    Returns updated playlist detail partial.
    """
    try:
        if not cover:
            raise HTTPException(status_code=400, detail="No cover image provided")

        # Fetch the card
        card: Card | None = await yoto_client.get_card(playlist_id)
        if not card:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Read cover image content
        cover_content = await cover.read()

        # Update card metadata with cover image
        # Store cover as base64 or URL in metadata
        cover_base64 = base64.b64encode(cover_content).decode("utf-8")

        if not hasattr(card, "metadata") or card.metadata is None:
            card.metadata = CardMetadata()

        card.metadata.cover = CardCover(
            image_l=f"data:image/{cover.content_type};base64,{cover_base64}"
        )

        # Save the updated card
        await yoto_client.update_card(card)

        logger.info(f"Updated cover for playlist {playlist_id}")

        # Return updated detail
        return render_partial(PlaylistDetail(card=card, playlist_id=playlist_id))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to change cover: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{playlist_id}", response_class=JSONResponse)
async def delete_playlist(
    request: Request,
    playlist_id: Annotated[str, Path()],
    yoto_client: YotoApiDep,
) -> DeletePlaylistResponse:
    """Delete a playlist (card)."""
    try:
        await yoto_client.delete_card(playlist_id)

        return DeletePlaylistResponse(status="deleted", playlist_id=playlist_id)

    except Exception as e:
        logger.error(f"Failed to delete playlist {playlist_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{playlist_id}/upload-session", response_class=JSONResponse)
async def create_upload_session(
    playlist_id: Annotated[str, Path()],
    request: Request,
    container: ContainerDep,
    yoto_client: YotoApiDep,
    upload_request: UploadSessionInitRequest,
) -> UploadSessionResponse:
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

        # Verify the playlist exists
        card = await yoto_client.get_card(playlist_id)
        if not card:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Get upload session service
        upload_session_service = container.upload_session_service()

        # Get user ID from session or use default
        user_id = request.cookies.get("user_id", "unknown")
        user_session_id = getattr(request.state, "session_id", None)

        # Create session
        session = upload_session_service.create_session(
            playlist_id=playlist_id,
            user_id=user_id,
            user_session_id=user_session_id,
            request=upload_request,
        )

        logger.info(f"Created upload session {session.session_id} for playlist {playlist_id}")

        return UploadSessionResponse(
            session_id=session.session_id,
            playlist_id=playlist_id,
            message="Upload session created successfully",
            session=session,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create upload session for {playlist_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{playlist_id}/upload-session/{session_id}/files", response_class=JSONResponse)
async def upload_file_to_session(
    playlist_id: Annotated[str, Path()],
    session_id: Annotated[str, Path()],
    request: Request,
    file: UploadFile = File(...),
    *,
    upload_session_service: UploadSessionServiceDep,
    upload_processing_service: UploadProcessingServiceDep,
    yoto_client: YotoApiDep,
) -> FileUploadResponse:
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
        # Verify session exists
        session = upload_session_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Upload session not found")

        if session.playlist_id != playlist_id:
            raise HTTPException(status_code=403, detail="Session playlist mismatch")

        if file.filename is None:
            raise HTTPException(status_code=400, detail="No file uploaded")

        # Create temp directory for this session
        temp_base = pathlib.Path(tempfile.gettempdir()) / "yoto_web_uploads" / session_id
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

        if updated_session:
            all_files_required = updated_session.normalize_batch
            if not all_files_required:
                updated_session.files_to_process.append(file_status.file_id)
                upload_processing_service.process_session_async(
                    session_id=session_id,
                    playlist_id=playlist_id,
                )
            logger.info(
                f"Queued file {file.filename} (id: {file_status.file_id}) for parallel processing in session {session_id}"
            )

        logger.info(
            f"File {file.filename} uploaded to session {session_id}, temp path: {temp_path}"
        )

        return FileUploadResponse(
            status="file_uploaded",
            file_id=file_status.file_id,
            filename=file.filename,
            session_id=session_id,
            session=updated_session,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload file to session {session_id}: {e}")
        # Clean up uploaded file on error
        if file:
            try:
                await file.close()
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{playlist_id}/upload-session/{session_id}/register-files", response_class=JSONResponse
)
async def register_files_for_session(
    playlist_id: Annotated[str, Path()],
    session_id: Annotated[str, Path()],
    request: Request,
    container: ContainerDep,
    yoto_client: YotoApiDep,
    file_count: Annotated[int, Form(description="Number of files that will be uploaded")],
) -> dict[str, Any]:
    """
    Pre-register files for an upload session.

    This should be called BEFORE uploading files to tell the server how many files
    will be uploaded. This allows proper handling of batch normalization which needs
    to wait for all files before processing.

    Args:
        playlist_id: ID of the playlist
        session_id: ID of the upload session
        file_count: Number of files that will be uploaded

    Returns:
        JSON confirmation
    """
    try:
        upload_session_service = container.upload_session_service()

        # Verify session exists
        session = upload_session_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Upload session not found")

        if session.playlist_id != playlist_id:
            raise HTTPException(status_code=403, detail="Session playlist mismatch")

        # Store the expected file count in session
        session.expected_file_count = file_count
        session.files_registered = True

        logger.info(f"Registered {file_count} files for session {session_id}")

        return {
            "status": "ok",
            "message": f"Registered {file_count} files",
            "session_id": session_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to register files for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{playlist_id}/upload-session/{session_id}/finalize", response_class=JSONResponse)
async def finalize_upload_session(
    playlist_id: Annotated[str, Path()],
    session_id: Annotated[str, Path()],
    request: Request,
    container: ContainerDep,
    upload_processing_service: UploadProcessingServiceDep,
    yoto_client: YotoApiDep,
) -> dict[str, Any]:
    """
    Finalize an upload session and start processing (in batch mode only).

    This should be called AFTER all files have been uploaded.
    - In batch mode: starts the background processing with batch normalization
    - In non-batch mode: just marks session as complete (processing already started per-file)

    Args:
        playlist_id: ID of the playlist
        session_id: ID of the upload session

    Returns:
        JSON confirmation
    """
    try:
        upload_session_service = container.upload_session_service()

        # Verify session exists
        session = upload_session_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Upload session not found")

        if session.playlist_id != playlist_id:
            raise HTTPException(status_code=403, detail="Session playlist mismatch")

        # Mark session as all files uploaded
        session.all_files_uploaded = True

        # Only start processing in batch mode
        # In non-batch mode, files were already queued as they were uploaded
        if session.normalize_batch:
            # In batch mode, add all files to the processing queue now
            session.files_to_process = [f.file_id for f in session.files]
            upload_processing_service.process_session_async(session_id, playlist_id)

            logger.info(f"Finalized batch mode upload session {session_id}, starting processing")
        else:
            logger.info(
                f"Finalized non-batch mode upload session {session_id}, processing already started per-file"
            )

        return {
            "status": "ok",
            "message": "Upload session finalized"
            if session.normalize_batch
            else "Upload session complete (processing per-file)",
            "session_id": session_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to finalize upload session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def get_upload_session_status(
    playlist_id: Annotated[str, Path()],
    session_id: Annotated[str, Path()],
    request: Request,
    container: ContainerDep,
    yoto_client: YotoApiDep,
) -> UploadSessionStatusResponse:
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
        # Get upload session service
        upload_session_service = container.upload_session_service()

        # Verify session exists
        session = upload_session_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Upload session not found")

        if session.playlist_id != playlist_id:
            raise HTTPException(status_code=403, detail="Session playlist mismatch")

        return UploadSessionStatusResponse(
            status="ok",
            session_id=session_id,
            session=session,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get upload session status: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{playlist_id}/upload-sessions", response_class=HTMLResponse)
async def get_playlist_upload_sessions(
    playlist_id: Annotated[str, Path()],
    request: Request,
    container: ContainerDep,
    yoto_client: YotoApiDep,
) -> str:
    """
    Get all active upload sessions for a playlist as HTML.

    Useful for HTMX polling to display upload progress.

    Args:
        playlist_id: ID of the playlist

    Returns:
        HTML rendering of active sessions
    """
    try:
        # Get upload session service
        upload_session_service = container.upload_session_service()

        # Get active sessions for this playlist
        sessions = upload_session_service.get_playlist_sessions(playlist_id)

        # Render as HTML component
        component = UploadSessionsListPartial(
            playlist_id=playlist_id,
            sessions=sessions,
        )
        return render_partial(component)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get playlist upload sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{playlist_id}/upload-session/{session_id}", response_class=HTMLResponse)
async def delete_upload_session(
    playlist_id: Annotated[str, Path()],
    session_id: Annotated[str, Path()],
    request: Request,
    container: ContainerDep,
    yoto_client: YotoApiDep,
) -> str:
    """
    Delete an upload session and clean up temp files.
    Returns HTML for HTMX swap.

    Args:
        playlist_id: ID of the playlist
        session_id: ID of the upload session

    Returns:
        HTML of updated upload sessions list
    """
    try:
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

        # Get all active sessions and render updated list
        sessions = upload_session_service.get_playlist_sessions(playlist_id)
        return render_partial(UploadSessionsListPartial(playlist_id=playlist_id, sessions=sessions))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete upload session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{playlist_id}/upload-session/{session_id}/stop", response_class=HTMLResponse)
async def stop_upload_session(
    playlist_id: Annotated[str, Path()],
    session_id: Annotated[str, Path()],
    request: Request,
    container: ContainerDep,
    yoto_client: YotoApiDep,
) -> str:
    """
    Stop an upload session that is currently processing.

    This will cancel further processing and mark the session as stopped.
    Returns HTML for HTMX swap.

    Args:
        playlist_id: ID of the playlist
        session_id: ID of the upload session

    Returns:
        HTML of updated upload sessions list
    """
    try:
        # Get upload session service
        upload_session_service = container.upload_session_service()
        upload_processing_service = container.upload_processing_service()

        # Verify session exists
        session = upload_session_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Upload session not found")

        if session.playlist_id != playlist_id:
            raise HTTPException(status_code=403, detail="Session playlist mismatch")

        # Mark session to stop
        upload_processing_service.stop_session(session_id)

        # Mark all files as errored to update session status
        for file_status in session.files:
            upload_session_service.mark_file_error(
                session_id, file_status.file_id, "User stopped upload"
            )

        logger.info(f"Stopped upload session {session_id}")

        # Get all active sessions and render updated list
        sessions = upload_session_service.get_playlist_sessions(playlist_id)
        return render_partial(UploadSessionsListPartial(playlist_id=playlist_id, sessions=sessions))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop upload session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{playlist_id}/toggle-edit-mode", response_class=HTMLResponse)
async def toggle_edit_mode(
    request: Request,
    playlist_id: Annotated[str, Path()],
    yoto_client: YotoApiDep,
    enable: Annotated[bool, Query(description="Enable or disable edit mode")] = True,
) -> str:
    """
    Toggle edit mode for a playlist.

    Returns edit controls partial for HTMX swap.
    """
    try:
        return render_partial(EditControlsPartial(playlist_id=playlist_id, edit_mode_active=enable))
    except Exception as e:
        logger.error(f"Failed to toggle edit mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{playlist_id}/upload-modal", response_class=HTMLResponse)
async def get_upload_modal(
    request: Request,
    playlist_id: Annotated[str, Path()],
    yoto_client: YotoApiDep,
) -> str:
    """
    Get upload modal HTML.

    Returns upload modal partial for HTMX.
    """
    try:
        return render_partial(UploadModalPartial(playlist_id=playlist_id))
    except Exception as e:
        logger.error(f"Failed to get upload modal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{playlist_id}/json-modal", response_class=HTMLResponse)
async def get_json_modal(
    request: Request,
    playlist_id: Annotated[str, Path()],
    yoto_client: YotoApiDep,
) -> str:
    """
    Get JSON display modal with playlist data.

    Returns JSON modal partial for HTMX.
    """
    try:
        card: Card | None = await yoto_client.get_card(playlist_id)
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")

        card_data = card.model_dump(mode="json")
        json_string = json.dumps(card_data, indent=2)

        return render_partial(JsonDisplayModalPartial(json_data=json_string))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get JSON modal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{playlist_id}/cover-modal", response_class=HTMLResponse)
async def get_cover_modal(
    request: Request,
    playlist_id: Annotated[str, Path()],
) -> str:
    """Serve the cover upload modal."""
    return render_partial(CoverModalPartial(playlist_id=playlist_id))


@router.post("/{playlist_id}/cover", response_class=HTMLResponse)
async def update_playlist_cover(
    request: Request,
    playlist_id: Annotated[str, Path()],
    yoto_client: YotoApiDep,
    cover: Annotated[UploadFile, File(description="Cover image file")],
) -> str:
    """
    Update playlist cover image.
    """
    try:
        # Fetch the card
        card: Card | None = await yoto_client.get_card(playlist_id)
        if not card:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Upload cover image
        cover_content = await cover.read()

        response = await yoto_client.upload_cover_image(
            image_data=cover_content,
        )

        # Update card metadata with new cover URL
        from yoto_web_server.api.models import CardCover, CardMetadata

        if not card.metadata:
            card.metadata = CardMetadata()

        if not card.metadata.cover:
            card.metadata.cover = CardCover()

        card.metadata.cover.image_l = response.cover_image.media_url

        # Save the card
        await yoto_client.update_card(card)

        # Refresh card to get new cover URL
        card = await yoto_client.get_card(playlist_id)

        # Return updated detail view
        return render_partial(PlaylistDetail(card=card, playlist_id=playlist_id))

    except Exception as e:
        logger.error(f"Failed to update playlist cover: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{playlist_id}/cover", response_class=HTMLResponse)
async def remove_playlist_cover(
    request: Request,
    playlist_id: Annotated[str, Path()],
    yoto_client: YotoApiDep,
) -> str:
    """
    Remove playlist cover image.
    """
    try:
        # Fetch the card
        card: Card | None = await yoto_client.get_card(playlist_id)
        if not card:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Remove cover from metadata
        if card.metadata and card.metadata.cover:
            card.metadata.cover = None

            # Save the card
            await yoto_client.update_card(card)

        # Refresh card
        card = await yoto_client.get_card(playlist_id)

        # Return updated detail view
        return render_partial(PlaylistDetail(card=card, playlist_id=playlist_id))

    except Exception as e:
        logger.error(f"Failed to remove playlist cover: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{playlist_id}/edit-overlay-label/{chapter_index}", response_class=HTMLResponse)
async def edit_overlay_label(
    request: Request,
    playlist_id: Annotated[str, Path()],
    chapter_index: Annotated[int, Path()],
    yoto_client: YotoApiDep,
) -> Renderable:
    """
    Render the edit overlay label input form for a chapter.
    Replaces the overlay label display with an editable text input.
    """
    try:
        # Fetch the card
        card: Card | None = await yoto_client.get_card(playlist_id)
        if not card:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Get chapters
        chapters = []
        if card.content:
            chapters = card.content.chapters

        if not chapters:
            raise HTTPException(status_code=400, detail="No chapters found in playlist")

        if chapter_index < 0 or chapter_index >= len(chapters):
            raise HTTPException(status_code=400, detail="Invalid chapter index")

        chapter = chapters[chapter_index]
        current_label = chapter.overlay_label or ""

        return d.Input(
            type="text",
            id=f"overlay-label-input-{chapter_index}",
            name="overlay_label",
            maxlength="3",
            value=current_label,
            classes="w-6 h-8 text-xs text-center font-bold p-0 rounded border border-indigo-500 bg-white text-gray-900",
            hx_post=f"/playlists/{playlist_id}/update-overlay-label/{chapter_index}",
            hx_trigger="blur",
            hx_swap="outerHTML",
            autofocus=True,
        )()
    except Exception as e:
        logger.error(f"Failed to render edit overlay label: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{playlist_id}/update-overlay-label/{chapter_index}", response_class=HTMLResponse)
async def update_overlay_label(
    request: Request,
    playlist_id: Annotated[str, Path()],
    chapter_index: Annotated[int, Path()],
    yoto_client: YotoApiDep,
    overlay_label: Annotated[str, Form()] = "",
) -> Renderable:
    """
    Update the overlay label for a chapter and return the updated label display.
    """
    try:
        # Fetch the card
        card: Card | None = await yoto_client.get_card(playlist_id)
        if not card:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Get chapters
        chapters = []
        if card.content:
            chapters = card.content.chapters

        if not chapters:
            raise HTTPException(status_code=400, detail="No chapters found in playlist")

        if chapter_index < 0 or chapter_index >= len(chapters):
            raise HTTPException(status_code=400, detail="Invalid chapter index")

        # Limit to 3 characters
        overlay_label = overlay_label[:3].strip() if overlay_label else ""

        # Update the chapter
        chapter = chapters[chapter_index]
        chapter.overlay_label = overlay_label if overlay_label else None

        # Save the card
        await yoto_client.update_card(card)

        # Return the updated overlay label display
        if overlay_label:
            return d.Div(
                id=f"overlay-label-{chapter_index}",
                classes="w-6 h-8 bg-black bg-opacity-70 rounded flex items-center justify-center text-xs font-bold text-white cursor-pointer hover:bg-opacity-90 transition-all",
                hx_get=f"/playlists/{playlist_id}/edit-overlay-label/{chapter_index}",
                hx_target=f"#overlay-label-{chapter_index}",
                hx_swap="outerHTML",
                title="Click to add or edit label (max 3 characters)",
            )(overlay_label)
        else:
            return d.Div(
                id=f"overlay-label-{chapter_index}",
                classes="w-6 h-8 bg-gray-300 hover:bg-gray-400 rounded flex items-center justify-center text-xs font-bold text-gray-600 cursor-pointer transition-all",
                hx_get=f"/playlists/{playlist_id}/edit-overlay-label/{chapter_index}",
                hx_target=f"#overlay-label-{chapter_index}",
                hx_swap="outerHTML",
                title="Click to add or edit label (max 3 characters)",
            )("+")

    except Exception as e:
        logger.error(f"Failed to update overlay label: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{playlist_id}/renumber-chapters", response_class=HTMLResponse)
async def renumber_chapters(
    request: Request,
    playlist_id: Annotated[str, Path()],
    yoto_client: YotoApiDep,
) -> Renderable:
    """
    Re-number chapters by their order with sequential numbers as overlay labels.
    """
    try:
        # Fetch the card
        card: Card | None = await yoto_client.get_card(playlist_id)
        if not card:
            raise HTTPException(status_code=404, detail="Playlist not found")

        # Get chapters
        chapters = []
        if card.content:
            chapters = card.content.chapters

        if not chapters:
            raise HTTPException(status_code=400, detail="No chapters found in playlist")

        # Add sequential numbers as overlay labels
        for i, chapter in enumerate(chapters, start=1):
            chapter.overlay_label = str(i)

        # Save the card
        await yoto_client.update_card(card)

        # Return the updated chapters list
        return d.Ul(
            id="chapters-list",
            classes="divide-y divide-gray-100",
        )(
            *[
                ChapterItem(
                    chapter=chapter,
                    index=i,
                    card_id=card.card_id,
                    playlist_id=playlist_id,
                    is_new=False,
                )
                for i, chapter in enumerate(chapters)
            ]
        )

    except Exception as e:
        logger.error(f"Failed to renumber chapters: {e}")
        raise HTTPException(status_code=500, detail=str(e))
