"""
Upload Processing Service.

Handles background processing of uploaded files including normalization,
analysis, and uploading to the Yoto API.
"""

import asyncio
import queue
import threading
import time
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
    Future as ConcurrentFuture,
)
from pathlib import Path
from typing import Literal, Optional, Dict, List, Tuple, TYPE_CHECKING

import concurrent
from loguru import logger

from yoto_up.models import Chapter, Track, CardContent
from yoto_up_server.models import (
    UploadFileStatus,
    UploadMode,
    UploadSession,
    UploadStatus,
)
from yoto_up.yoto_api_client import (
    TranscodedAudioResponse,
    YotoApiClient,
    YotoApiConfig,
)
from yoto_up.yoto_app import config as yoto_config
from yoto_up import paths

if TYPE_CHECKING:
    from yoto_up_server.services.api_service import ApiService
    from yoto_up_server.services.audio_processor import AudioProcessorService
    from yoto_up_server.services.upload_session_service import UploadSessionService


class UploadProcessingService:
    """
    Service for processing uploaded files.

    Uses a worker thread to manage sessions and a thread pool for parallel file processing.
    """

    def __init__(
        self,
        api_service: "ApiService",
        audio_processor: "AudioProcessorService",
        upload_session_service: "UploadSessionService",
    ) -> None:
        self._api_service = api_service
        self._audio_processor = audio_processor
        self._upload_session_service = upload_session_service

        self._queue: queue.Queue[Tuple[str, str]] = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._thread_pool = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="UploadWorker"
        )

    def start(self) -> None:
        """Start the worker thread."""
        if self._worker_thread and self._worker_thread.is_alive():
            return

        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop, name="UploadProcessingWorker", daemon=True
        )
        self._worker_thread.start()
        logger.info("Upload processing worker started")

    def stop(self) -> None:
        """Stop the worker thread and thread pool."""
        logger.info("Stopping upload processing worker...")
        self._stop_event.set()
        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)
        self._thread_pool.shutdown(wait=True)
        logger.info("Upload processing worker stopped")

    def process_session_async(
        self,
        session_id: str,
        playlist_id: str,
    ) -> None:
        """
        Queue an upload session for processing.

        Args:
            session_id: ID of the upload session
            playlist_id: ID of the target playlist
        """
        self._queue.put((session_id, playlist_id))
        logger.info(f"Queued session {session_id} for processing")

    def _worker_loop(self) -> None:
        """Main worker loop processing sessions from the queue."""
        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=1.0)
                session_id, playlist_id = item

                try:
                    self._process_session(session_id, playlist_id)
                except Exception as e:
                    logger.error(f"Error processing session {session_id}: {e}")
                    self._mark_session_error(session_id, str(e))
                finally:
                    self._queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                time.sleep(1.0)

    def _process_session(self, session_id: str, playlist_id: str) -> None:
        """Process a single session."""
        session = self._upload_session_service.get_session(session_id)
        if not session:
            logger.error(f"Session {session_id} not found")
            return

        logger.info(f"Processing session {session_id} with {len(session.files)} files")

        # 1. Batch Normalization (if enabled)
        if session.normalize and session.normalize_batch:
            try:
                # run in pool
                future = self._thread_pool.submit(
                    self._perform_batch_normalization, session
                )
                future.result()
            except Exception as e:
                logger.error(f"Batch normalization failed: {e}")
                self._mark_session_error(session_id, f"Normalization failed: {e}")
                return

        # 2. Parallel Processing (Analysis + Upload)
        futures: Dict[ConcurrentFuture[Optional[Track]], str] = {}
        # Map file_id to Track for preserving order later
        processed_tracks: Dict[str, Track] = {}

        for file_status in session.files:
            if file_status.temp_path:
                future = self._thread_pool.submit(
                    self._process_file_pipeline,
                    session_id=session_id,
                    file_status=file_status,
                    session=session,
                )
                futures[future] = file_status.file_id

        # Collect results
        for future in as_completed(futures):
            file_id = futures[future]
            try:
                track = future.result()
                if track:
                    processed_tracks[file_id] = track
            except Exception as e:
                logger.error(f"File processing failed for {file_id}: {e}")
                self._upload_session_service.mark_file_error(
                    session_id, file_id, str(e)
                )

        # 3. Update Playlist
        # Reconstruct ordered list of tracks
        ordered_tracks = []
        for file_status in session.files:
            if file_status.file_id in processed_tracks:
                ordered_tracks.append(processed_tracks[file_status.file_id])

        if ordered_tracks:
            try:
                self._update_playlist(playlist_id, ordered_tracks, session.upload_mode)
                logger.info(
                    f"Successfully updated playlist {playlist_id} with {len(ordered_tracks)} tracks"
                )
            except Exception as e:
                logger.error(f"Failed to update playlist: {e}")
                # We don't mark session as error here because files were processed successfully

        logger.info(f"Session {session_id} processing complete")

    def _perform_batch_normalization(self, session: UploadSession) -> None:
        """Perform normalization on all files in the session."""
        files_to_normalize = []
        paths_to_normalize = []

        for file_status in session.files:
            if file_status.temp_path:
                files_to_normalize.append(file_status)
                paths_to_normalize.append(str(file_status.temp_path))

                self._upload_session_service.mark_file_processing(
                    session.session_id, file_status.file_id, "normalizing"
                )

        if not paths_to_normalize:
            return

        logger.info(
            f"Normalizing {len(paths_to_normalize)} files (batch={session.normalize_batch})"
        )

        # Call audio processor
        # Note: We assume audio_processor.normalize is thread-safe or we are the only one calling it
        # Since we are in the worker thread, it's fine.
        normalized_paths = self._audio_processor.normalize(
            input_paths=paths_to_normalize,
            output_dir=str(Path(paths_to_normalize[0]).parent),  # Same dir
            target_level=session.target_lufs,
            batch_mode=session.normalize_batch,
        )

        # Update temp paths
        for i, file_status in enumerate(files_to_normalize):
            if i < len(normalized_paths):
                file_status.temp_path = normalized_paths[i]

    def _process_file_pipeline(
        self, session_id: str, file_status: UploadFileStatus, session: UploadSession
    ) -> Optional[Track]:
        """
        Process a single file: Analyze -> Upload -> Create Track.
        Runs in thread pool.
        """
        try:
            input_path = Path(file_status.temp_path)

            # 1. Normalization (Parallel mode)
            if session.normalize and not session.normalize_batch:
                self._upload_session_service.mark_file_processing(
                    session_id, file_status.file_id, "normalizing"
                )
                logger.info(f"Normalizing file {input_path.name} (parallel mode)")
                normalized_paths = self._audio_processor.normalize(
                    input_paths=[str(input_path)],
                    output_dir=str(input_path.parent),
                    target_level=session.target_lufs,
                    batch_mode=False,
                )
                if normalized_paths:
                    input_path = Path(normalized_paths[0])
                    # Update file status with new path just in case
                    file_status.temp_path = str(input_path)

            # 2. Analyze (Intro/Outro)
            self._upload_session_service.mark_file_processing(
                session_id, file_status.file_id, "analyzing"
            )

            # Placeholder for analysis
            # if session.analyze_intro_outro:
            #     pass

            # 3. Upload
            self._upload_session_service.mark_file_processing(
                session_id, file_status.file_id, "uploading_to_api"
            )

            transcoded = self._upload_file_to_yoto(input_path)

            # 4. Create Track
            self._upload_session_service.mark_file_processing(
                session_id, file_status.file_id, "creating_track"
            )

            transcoded_info = transcoded.transcode.transcoded_info

            title = Path(file_status.filename).stem
            track = Track(
                title=title,
                key="0",  # Will be set later
                trackUrl=f"yoto:#{transcoded.transcode.transcoded_sha256}",
                type="audio",
                format=transcoded_info.format if transcoded_info else None,
                duration=transcoded_info.duration
                if transcoded_info and transcoded_info.duration
                else None,
            )

            # Cleanup
            try:
                # We only delete if it's a temp file we created/managed
                # But here input_path IS the temp path (possibly normalized)
                # We should probably delete it.
                input_path.unlink(missing_ok=True)
            except Exception:
                pass

            self._upload_session_service.mark_file_done(session_id, file_status.file_id)
            return track

        except Exception as e:
            logger.error(f"Pipeline failed for {file_status.filename}: {e}")
            raise

    def _upload_file_to_yoto(self, file_path: Path) -> TranscodedAudioResponse:
        """
        Upload a file to Yoto and return the track URL and duration.
        Uses a fresh API client instance to avoid event loop issues in threads.
        """

        async def _do_upload():
            config = YotoApiConfig(client_id=yoto_config.CLIENT_ID)
            async with YotoApiClient(
                config=config, token_file=paths.TOKENS_FILE
            ) as api:
                # 1. Calculate SHA256
                sha256, file_bytes = api.calculate_sha256(file_path)

                # 2. Get Upload URL
                resp = await api.get_audio_upload_url(sha256, filename=file_path.name)
                upload = resp.upload

                # 3. Upload if needed
                if upload.upload_url:
                    await api.upload_audio_file(upload.upload_url, file_bytes)

                # 4. Poll for transcoding
                # We disable API-side loudnorm because we handle it locally if requested
                transcoded = await api.poll_for_transcoding(
                    upload.upload_id, loudnorm=False
                )

                return transcoded

        return asyncio.run(_do_upload())

    def _update_playlist(
        self, playlist_id: str, new_tracks: List[Track], upload_mode: UploadMode
    ):
        """Update playlist with new tracks/chapters."""
        config = YotoApiConfig(client_id=yoto_config.CLIENT_ID)
        api = YotoApiClient(config=config, token_file=paths.TOKENS_FILE)

        async def _do_update():
            await api.initialize()
            try:
                card = await api.get_card(playlist_id)
                if not card.content:
                    card.content = CardContent(chapters=[])

                if card.content.chapters is None:
                    card.content.chapters = []

                if upload_mode == "chapters":
                    # Create a chapter for each track
                    chapter_key = 0
                    existing_keys = {chapter.key for chapter in card.content.chapters}
                    while str(chapter_key) in existing_keys:
                        chapter_key += 1
                    for key, track in enumerate(new_tracks):
                        track.key = str(key)
                        chapter = Chapter(
                            title=track.title, tracks=[track], key=str(chapter_key)
                        )
                        card.content.chapters.append(chapter)

                elif upload_mode == "tracks":
                    # Add all tracks to a new chapter
                    # Or append to the last chapter if it exists?
                    # Let's create a new chapter for this batch upload
                    key = 0
                    current_keys = {chapter.key for chapter in card.content.chapters}
                    while str(key) in current_keys:
                        key += 1
                    chapter = Chapter(
                        title="New Uploads",  # TODO: Maybe use date or something?
                        tracks=new_tracks,
                        key=str(key),
                    )
                    card.content.chapters.append(chapter)

                await api.update_card(card)
            finally:
                await api.close()

        asyncio.run(_do_update())

    def _mark_session_error(self, session_id: str, error_message: str) -> None:
        """
        Mark all files in session as errored.

        Args:
            session_id: Session ID
            error_message: Error description
        """
        session = self._upload_session_service.get_session(session_id)
        if session:
            for file_status in session.files:
                self._upload_session_service.mark_file_error(
                    session_id=session_id,
                    file_id=file_status.file_id,
                    error_message=error_message,
                )
