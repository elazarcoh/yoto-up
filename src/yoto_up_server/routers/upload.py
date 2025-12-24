"""
Upload router.

Handles file uploads, processing pipeline, and SSE progress updates.
"""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Optional, List
import tempfile

from fastapi import APIRouter, Request, UploadFile, File, Form, Query, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse
from loguru import logger

from yoto_up_server.dependencies import AuthenticatedApiDep, ContainerDep
from yoto_up_server.models import UploadJob, UploadStatus
from yoto_up_server.templates.base import render_page, render_partial
from yoto_up_server.templates.upload import (
    UploadPage,
    UploadQueuePartial,
    FileRowPartial,
    UploadProgressPartial,
)


router = APIRouter()

# In-memory upload queue (in production, use Redis or database)
upload_queues: dict[str, List[UploadJob]] = {}


@router.get("/", response_class=HTMLResponse)
async def upload_page(request: Request, api_service: AuthenticatedApiDep):
    """Render the upload page."""
    return render_page(
        title="Upload - Yoto Up",
        content=UploadPage(),
        request=request,
    )


@router.get("/queue", response_class=HTMLResponse)
async def get_queue(request: Request, api_service: AuthenticatedApiDep):
    """
    Get current upload queue.
    
    Returns HTML partial with queued files.
    """
    session_id = request.cookies.get("session_id", "default")
    queue = upload_queues.get(session_id, [])
    
    return render_partial(UploadQueuePartial(jobs=queue))


@router.post("/files", response_class=HTMLResponse)
async def upload_files(
    request: Request,
    api_service: AuthenticatedApiDep,
    files: List[UploadFile] = File(...),
):
    """
    Upload files to the queue.
    
    Files are stored temporarily and added to the processing queue.
    Returns HTML partial with updated queue.
    """
    session_id = request.cookies.get("session_id", str(uuid.uuid4()))
    
    if session_id not in upload_queues:
        upload_queues[session_id] = []
    
    queue = upload_queues[session_id]
    
    for file in files:
        # Save file to temp location
        temp_dir = Path(tempfile.gettempdir()) / "yoto_up_uploads" / session_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        temp_path = temp_dir / file.filename
        
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        job = UploadJob(
            id=str(uuid.uuid4()),
            filename=file.filename,
            status=UploadStatus.QUEUED,
            temp_path=str(temp_path),
        )
        
        queue.append(job)
    
    return render_partial(UploadQueuePartial(jobs=queue))


@router.delete("/files/{job_id}", response_class=HTMLResponse)
async def remove_file(
    request: Request,
    job_id: str,
    api_service: AuthenticatedApiDep,
):
    """
    Remove a file from the upload queue.
    
    Returns updated queue partial.
    """
    session_id = request.cookies.get("session_id", "default")
    queue = upload_queues.get(session_id, [])
    
    # Find and remove the job
    for i, job in enumerate(queue):
        if job.id == job_id:
            # Clean up temp file
            if job.temp_path:
                try:
                    Path(job.temp_path).unlink(missing_ok=True)
                except Exception:
                    pass
            queue.pop(i)
            break
    
    return render_partial(UploadQueuePartial(jobs=queue))


@router.post("/start", response_class=HTMLResponse)
async def start_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    container: ContainerDep,
    api_service: AuthenticatedApiDep,
    target: str = Form(..., description="Target: new or existing card ID"),
    title: Optional[str] = Form(None, description="Title for new card"),
    mode: str = Form("chapters", description="Upload mode: chapters or tracks"),
    normalize: bool = Form(False, description="Normalize audio loudness"),
):
    """
    Start the upload process.
    
    Initiates background processing of queued files.
    Returns initial progress partial.
    """
    session_id = request.cookies.get("session_id", "default")
    queue = upload_queues.get(session_id, [])
    
    if not queue:
        raise HTTPException(status_code=400, detail="No files in queue")
    
    # Mark all jobs as processing
    for job in queue:
        job.status = UploadStatus.QUEUED
        job.progress = 0.0
    
    # Start background upload task
    upload_manager = container.upload_manager()
    
    background_tasks.add_task(
        process_uploads,
        session_id=session_id,
        queue=queue,
        upload_manager=upload_manager,
        api_service=api_service,
        target=target,
        title=title,
        mode=mode,
        normalize=normalize,
    )
    
    return render_partial(UploadProgressPartial(jobs=queue, status="started"))


async def process_uploads(
    session_id: str,
    queue: List[UploadJob],
    upload_manager,
    api_service,
    target: str,
    title: Optional[str],
    mode: str,
    normalize: bool,
):
    """Background task to process uploads."""
    try:
        await upload_manager.process_queue(
            queue=queue,
            api_service=api_service,
            target=target,
            title=title,
            mode=mode,
            normalize=normalize,
        )
    except Exception as e:
        logger.error(f"Upload processing failed: {e}")
        for job in queue:
            if job.status not in (UploadStatus.DONE, UploadStatus.ERROR):
                job.status = UploadStatus.ERROR
                job.error = str(e)


@router.get("/progress")
async def upload_progress_sse(
    request: Request,
    api_service: AuthenticatedApiDep,
):
    """
    Server-Sent Events endpoint for upload progress.
    
    Returns SSE stream with progress updates.
    """
    session_id = request.cookies.get("session_id", "default")
    
    async def event_generator():
        while True:
            queue = upload_queues.get(session_id, [])
            
            if not queue:
                yield f"data: {json.dumps({'status': 'empty'})}\n\n"
                await asyncio.sleep(1)
                continue
            
            # Check if all done
            all_done = all(job.status in (UploadStatus.DONE, UploadStatus.ERROR) for job in queue)
            
            jobs_data = [
                {
                    "id": job.id,
                    "filename": job.filename,
                    "status": job.status.value,
                    "progress": job.progress,
                    "error": job.error,
                }
                for job in queue
            ]
            
            # Calculate overall progress
            total_progress = sum(job.progress for job in queue) / len(queue) if queue else 0
            
            data = {
                "status": "complete" if all_done else "processing",
                "overall_progress": total_progress,
                "jobs": jobs_data,
            }
            
            yield f"data: {json.dumps(data)}\n\n"
            
            if all_done:
                break
            
            await asyncio.sleep(0.5)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/progress-html", response_class=HTMLResponse)
async def upload_progress_html(
    request: Request,
    api_service: AuthenticatedApiDep,
):
    """
    Get current upload progress as HTML partial.
    
    Used for HTMX polling as alternative to SSE.
    """
    session_id = request.cookies.get("session_id", "default")
    queue = upload_queues.get(session_id, [])
    
    all_done = all(job.status in (UploadStatus.DONE, UploadStatus.ERROR) for job in queue) if queue else True
    
    return render_partial(
        UploadProgressPartial(
            jobs=queue,
            status="complete" if all_done else "processing",
        )
    )


@router.post("/clear", response_class=HTMLResponse)
async def clear_queue(
    request: Request,
    api_service: AuthenticatedApiDep,
):
    """
    Clear the upload queue.
    
    Removes all completed/errored jobs and their temp files.
    """
    session_id = request.cookies.get("session_id", "default")
    queue = upload_queues.get(session_id, [])
    
    # Clean up temp files
    for job in queue:
        if job.temp_path:
            try:
                Path(job.temp_path).unlink(missing_ok=True)
            except Exception:
                pass
    
    upload_queues[session_id] = []
    
    return render_partial(UploadQueuePartial(jobs=[]))


@router.post("/analyze-intro-outro", response_class=HTMLResponse)
async def analyze_intro_outro(
    request: Request,
    container: ContainerDep,
    api_service: AuthenticatedApiDep,
    side: str = Form("intro", description="Which side to analyze: intro or outro"),
    max_seconds: float = Form(10.0, description="Maximum seconds to analyze"),
):
    """
    Analyze files in queue for common intro/outro.
    
    Returns analysis results as HTML partial.
    """
    session_id = request.cookies.get("session_id", "default")
    queue = upload_queues.get(session_id, [])
    
    if not queue:
        raise HTTPException(status_code=400, detail="No files in queue")
    
    file_paths = [job.temp_path for job in queue if job.temp_path]
    
    if not file_paths:
        raise HTTPException(status_code=400, detail="No valid files in queue")
    
    try:
        # Use the intro_outro analysis from yoto_up
        from yoto_up.yoto_app.intro_outro import per_window_common_prefix
        
        result = per_window_common_prefix(
            paths=file_paths,
            side=side,
            max_seconds=max_seconds,
        )
        
        return render_partial(
            f"""
            <div class="analysis-result">
                <h4>Analysis Result</h4>
                <p>Common {side} detected: {result.get('seconds_matched', 0):.2f} seconds</p>
                <p>Matches found in {result.get('windows_matched', 0)} windows</p>
            </div>
            """
        )
        
    except Exception as e:
        logger.error(f"Intro/outro analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
