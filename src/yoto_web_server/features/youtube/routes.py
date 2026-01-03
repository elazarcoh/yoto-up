"""Routes for YouTube feature."""

from typing import Annotated

import pydom as d
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from loguru import logger

from yoto_web_server.dependencies import YouTubeFeatureDep
from yoto_web_server.features.youtube.components import (
    YouTubePendingURLEntry,
    YouTubeUploadModal,
)

router = APIRouter(prefix="/youtube", tags=["youtube"])


@router.get("/upload-modal/", response_class=HTMLResponse, response_model=None)
async def get_upload_modal(
    request: Request,
):
    """Return the YouTube upload modal.

    This route is called via HTMX hx-get and returns the modal component.
    If the feature is not available, returns empty component.
    """

    return YouTubeUploadModal(show=True)


@router.post("/upload-modal/close/", response_class=HTMLResponse, response_model=None)
async def close_upload_modal(request: Request) -> d.Renderable:
    """Close the YouTube upload modal.

    Returns empty div to replace the modal.
    """
    return d.Div(id="youtube-upload-modal", classes="hidden")()


@router.post("/use-url/", response_class=HTMLResponse, response_model=None)
async def upload_youtube(
    request: Request,
    youtube_feature: YouTubeFeatureDep,
    youtube_url: Annotated[str, Form(..., description="YouTube video URL")],
):
    """Queue a YouTube URL for metadata fetching.

    Returns pending URL entry to the pending URLs list with loading indicator.
    HTMX will poll this entry to check for metadata completion.
    """
    logger.info(f"Queueing metadata fetch for: {youtube_url}")

    # Queue the task
    task_id = youtube_feature.worker_service.queue_metadata_fetch(youtube_url)

    # Return pending URL entry with loading state and HTMX polling
    entry = YouTubePendingURLEntry(
        task_id=task_id,
        youtube_url=youtube_url,
        is_loading=True,
    )
    return d.Fragment()(
        entry,
        # Also close the upload modal using oob swap
        d.Div(id="youtube-upload-modal", hx_swap_oob="outerHTML")(),
    )


@router.get("/pending/{task_id}/", response_class=HTMLResponse, response_model=None)
async def get_pending_status(task_id: str, youtube_feature: YouTubeFeatureDep):
    """Poll the status of a metadata fetch task.

    Returns the updated entry component. If still loading, returns entry with
    continuing HTMX polling. If complete, returns entry with metadata.
    """
    task = youtube_feature.worker_service.get_task_status(task_id)

    if not task:
        # Task not found - return error entry
        return YouTubePendingURLEntry(
            task_id=task_id,
            youtube_url="",
            is_loading=False,
            title=None,
            duration_seconds=None,
        )

    if task.status == "pending" or task.status == "processing":
        # Still processing, return loading entry with continued polling
        return YouTubePendingURLEntry(
            task_id=task_id,
            youtube_url=task.youtube_url or "",
            is_loading=True,
        )

    if task.status == "error":
        # Error occurred - return error entry
        return YouTubePendingURLEntry(
            task_id=task_id,
            youtube_url=task.youtube_url or "",
            is_loading=False,
            title=None,
            duration_seconds=None,
        )

    # Complete - return entry with metadata
    if task.metadata:
        return YouTubePendingURLEntry(
            task_id=task_id,
            youtube_url=task.youtube_url or "",
            is_loading=False,
            title=task.metadata.title,
            duration_seconds=task.metadata.duration_seconds,
        )

    # No metadata - return error entry
    return YouTubePendingURLEntry(
        task_id=task_id,
        youtube_url=task.youtube_url or "",
        is_loading=False,
        title=None,
        duration_seconds=None,
    )


@router.delete("/pending/{task_id}/", response_class=HTMLResponse, response_model=None)
async def delete_pending(task_id: str, youtube: YouTubeFeatureDep):
    """Delete a pending task entry.

    Returns empty string to remove the entry from the DOM.
    """
    logger.info(f"Deleting pending task: {task_id}")
    youtube.worker_service.cancel_task(task_id)
    return ""
