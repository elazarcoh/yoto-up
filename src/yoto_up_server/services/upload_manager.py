"""
Upload Manager Service.

Handles the upload workflow including processing, transcoding, and card creation.
"""

import asyncio
import os
import re
from pathlib import Path
from typing import List, Optional, Callable, TYPE_CHECKING

from loguru import logger

from yoto_up.models import Chapter, ChapterDisplay, Track, TrackDisplay
if TYPE_CHECKING:
    from yoto_up_server.services.api_service import ApiService
    from yoto_up_server.services.audio_processor import AudioProcessorService


class UploadJob:
    """Represents a file in the upload queue."""
    
    def __init__(self, id: str, filename: str, temp_path: str) -> None:
        self.id = id
        self.filename = filename
        self.temp_path = temp_path
        self.status = "queued"
        self.progress = 0.0
        self.error: Optional[str] = None
        self.result: Optional[dict] = None


class UploadManager:
    """
    Service for managing the upload workflow.
    
    Handles file processing, transcoding, and card creation/update.
    """
    
    def __init__(self, api_service: "ApiService", audio_processor: "AudioProcessorService") -> None:
        self._api_service = api_service
        self._audio_processor = audio_processor
    
    def clean_title_from_filename(self, filepath: str, strip_leading_nums: bool = True) -> str:
        """
        Extract a clean title from a filename.
        
        Removes common track number patterns and file extension.
        """
        base = os.path.splitext(os.path.basename(filepath))[0]
        
        if strip_leading_nums:
            # Remove common leading track number patterns
            # e.g., '01 - ', '1. ', '01) ', '01_', etc.
            cleaned = re.sub(r'^\s*\d{1,3}[\s\-\._:\)\]]*', '', base)
        else:
            cleaned = base
        
        return cleaned.strip()
    
    async def process_queue(
        self,
        queue: List,  # List of UploadJob-like objects
        api: object,
        target: str,
        title: Optional[str] = None,
        mode: str = "chapters",
        normalize: bool = False,
    ) -> None:
        """
        Process the upload queue.
        
        Args:
            queue: List of upload jobs.
            api: YotoAPI instance.
            target: "new" for new card, or existing card ID.
            title: Title for new card.
            mode: "chapters" or "tracks".
            normalize: Whether to normalize audio.
        """
        if not queue:
            return
        
        # Step 1: Normalize if requested
        file_paths = [job.temp_path for job in queue if job.temp_path]
        processed_paths = file_paths
        
        if normalize:
            logger.info("Normalizing audio files...")
            for job in queue:
                job.status = "normalizing"
            
            try:
                processed_paths = self._audio_processor.normalize(
                    input_paths=file_paths,
                    progress_callback=lambda msg, frac: self._update_progress(queue, "normalizing", frac),
                )
            except Exception as e:
                logger.error(f"Normalization failed: {e}")
                for job in queue:
                    job.status = "error"
                    job.error = f"Normalization failed: {e}"
                return
        
        # Step 2: Upload and transcode each file
        transcoded_results = []
        
        for i, (job, path) in enumerate(zip(queue, processed_paths)):
            job.status = "uploading"
            job.progress = 0.0
            
            try:
                filename = os.path.basename(job.temp_path)
                
                def progress_callback(msg, frac):
                    job.status = msg or "uploading"
                    job.progress = frac or 0.0
                
                result = await api.upload_and_transcode_audio_async(
                    audio_path=path,
                    filename=filename,
                    loudnorm=False,  # Already normalized if requested
                    show_progress=True,
                    poll_interval=2,
                    max_attempts=60,
                    progress_callback=progress_callback,
                )
                
                job.progress = 1.0
                job.status = "transcoded"
                job.result = result
                transcoded_results.append(result)
                
            except Exception as e:
                logger.error(f"Upload failed for {job.filename}: {e}")
                job.status = "error"
                job.error = str(e)
                transcoded_results.append(None)
        
        # Step 3: Build chapters/tracks from transcoded results
        chapters = self._build_chapters(
            transcoded_results=transcoded_results,
            queue=queue,
            api=api,
            mode=mode,
        )
        
        if not chapters:
            logger.error("No chapters created from transcoded results")
            return
        
        # Step 4: Create or update card
        try:
            if target == "new":
                # Create new card
                card_title = title or "New Card"
                
                for job in queue:
                    job.status = "creating_card"
                
                card = api.create_card(
                    title=card_title,
                    chapters=chapters,
                )
                
                logger.info(f"Created new card: {card.get('cardId', 'unknown')}")
                
            else:
                # Update existing card
                card_id = target
                
                for job in queue:
                    job.status = "updating_card"
                
                # Get existing card content
                existing_card = api.get_card(card_id)
                existing_chapters = existing_card.get("content", {}).get("chapters", [])
                
                # Append new chapters
                all_chapters = existing_chapters + chapters
                
                api.update_card_content(
                    card_id=card_id,
                    chapters=all_chapters,
                )
                
                logger.info(f"Updated card: {card_id}")
            
            # Mark all jobs as done
            for job in queue:
                if job.status != "error":
                    job.status = "done"
                    job.progress = 1.0
                    
        except Exception as e:
            logger.error(f"Card creation/update failed: {e}")
            for job in queue:
                if job.status != "error":
                    job.status = "error"
                    job.error = str(e)
    
    def _build_chapters(
        self,
        transcoded_results: List,
        queue: List,
        api,
        mode: str = "chapters",
    ) -> List[dict]:
        """
        Build chapter/track structures from transcoded results.
        
        Args:
            transcoded_results: List of transcode results from API.
            queue: Original upload queue for metadata.
            api: YotoAPI instance.
            mode: "chapters" or "tracks".
        
        Returns:
            List of Chapter dictionaries.
        """
        chapters = []
        
        if mode == "tracks":
            # All files as tracks in a single chapter
            tracks = []
            
            for i, (result, job) in enumerate(zip(transcoded_results, queue)):
                if result is None:
                    continue
                
                title = self.clean_title_from_filename(job.filename)
                
                track = api.get_track_from_transcoded_audio(
                    result,
                    track_details={"title": title},
                )
                track.key = f"{i+1:02}"
                track.overlayLabel = str(i + 1)
                tracks.append(track)
            
            if tracks:
                chapter = Chapter(
                    key="01",
                    title="Tracks",
                    overlayLabel="1",
                    tracks=tracks,
                    display=ChapterDisplay(icon16x16="yoto:#aUm9i3ex3qqAMYBv-i-O-pYMKuMJGICtR3Vhf289u2Q"),
                )
                chapters.append(chapter.model_dump())
        
        else:
            # Each file as a separate chapter
            for i, (result, job) in enumerate(zip(transcoded_results, queue)):
                if result is None:
                    continue
                
                title = self.clean_title_from_filename(job.filename)
                
                chapter = api.get_chapter_from_transcoded_audio(
                    result,
                    chapter_details={"title": title},
                )
                chapter.key = f"{i+1:02}"
                chapter.overlayLabel = str(i + 1)
                
                # Set track keys
                if hasattr(chapter, "tracks") and chapter.tracks:
                    for j, track in enumerate(chapter.tracks):
                        track.key = f"{j+1:02}"
                        track.overlayLabel = str(j + 1)
                
                chapters.append(chapter.model_dump() if hasattr(chapter, "model_dump") else chapter)
        
        return chapters
    
    def _update_progress(self, queue: List, status: str, progress: float):
        """Update progress for all jobs in queue."""
        for job in queue:
            job.status = status
            job.progress = progress
