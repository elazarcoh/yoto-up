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
    Future as ConcurrentFuture,
)
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from yoto_web_server.api.client import YotoApiClient
from yoto_web_server.api.models import CardContent, Chapter, Track, TranscodedAudioResponse
from yoto_web_server.models import (
    UploadFileStatus,
    UploadMode,
    UploadSession,
)

if TYPE_CHECKING:
    from yoto_web_server.services.audio_processor import AudioProcessorService
    from yoto_web_server.services.session_aware_api_service import SessionAwareApiService
    from yoto_web_server.services.upload_session_service import UploadSessionService


class UploadProcessingService:
    """
    Service for processing uploaded files.

    Uses a worker thread to manage sessions and a thread pool for parallel file processing.
    """

    def __init__(
        self,
        audio_processor: "AudioProcessorService",
        upload_session_service: "UploadSessionService",
        session_aware_api_service: "SessionAwareApiService",
    ) -> None:
        self._audio_processor = audio_processor
        self._upload_session_service = upload_session_service
        self._session_aware_api_service = session_aware_api_service

        self._queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._thread_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="UploadWorker")
        # Track sessions that should be stopped
        self._sessions_to_stop: set[str] = set()
        self._stop_lock = threading.Lock()

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

    def stop_session(self, session_id: str) -> bool:
        """
        Mark a session to be stopped.

        Args:
            session_id: ID of the session to stop

        Returns:
            True if session was marked for stopping
        """
        with self._stop_lock:
            self._sessions_to_stop.add(session_id)
        logger.info(f"Marked session {session_id} for stopping")
        return True

    def _is_session_stopped(self, session_id: str) -> bool:
        """
        Check if a session should be stopped.
        """
        with self._stop_lock:
            return session_id in self._sessions_to_stop

    def _clear_stop_flag(self, session_id: str) -> None:
        """
        Clear the stop flag for a session.
        """
        with self._stop_lock:
            self._sessions_to_stop.discard(session_id)

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
                future = self._thread_pool.submit(self._perform_batch_normalization, session)
                # wait for completion without blocking other tasks
                future.result()
            except Exception as e:
                logger.error(f"Batch normalization failed: {e}")
                self._mark_session_error(session_id, f"Normalization failed: {e}")
                return

        # 2. Parallel Processing (Analysis + Upload)
        futures: dict[ConcurrentFuture[Track | None], str] = {}
        # Map file_id to Track for preserving order later
        processed_tracks: dict[str, Track] = {}

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
                self._upload_session_service.mark_file_error(session_id, file_id, str(e))

        # 3. Update Playlist
        # Reconstruct ordered list of tracks
        ordered_tracks = []
        for file_status in session.files:
            if file_status.file_id in processed_tracks:
                ordered_tracks.append(processed_tracks[file_status.file_id])

        if ordered_tracks:
            try:
                new_indices = self._update_playlist(
                    playlist_id, ordered_tracks, session.upload_mode, session_id
                )
                # Convert indices to strings
                new_ids = [str(idx) for idx in new_indices]
                self._upload_session_service.update_new_chapter_ids(session_id, new_ids)

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
    ) -> Track | None:
        """
        Process a single file: Analyze -> Upload -> Create Track.
        Runs in thread pool.
        """
        try:
            # Check if session should stop before processing this file
            if self._is_session_stopped(session_id):
                logger.info(f"Session {session_id} stopped, skipping file {file_status.filename}")
                return None

            # temp_path is guaranteed to be set by caller check, but assert for type narrowing
            assert file_status.temp_path is not None
            input_path = Path(file_status.temp_path)

            # 1. Normalization (Parallel mode)
            if session.normalize and not session.normalize_batch:
                if self._is_session_stopped(session_id):
                    logger.info(f"Session {session_id} stopped during normalization")
                    return None

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
            if self._is_session_stopped(session_id):
                logger.info(f"Session {session_id} stopped before analysis")
                return None

            self._upload_session_service.mark_file_processing(
                session_id, file_status.file_id, "analyzing"
            )

            # Placeholder for analysis
            # if session.analyze_intro_outro:
            #     pass

            # 3. Upload
            if self._is_session_stopped(session_id):
                logger.info(f"Session {session_id} stopped before upload")
                return None

            self._upload_session_service.mark_file_processing(
                session_id, file_status.file_id, "uploading_to_api"
            )

            transcoded = self._upload_file_to_yoto(input_path, session_id)

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

    def _upload_file_to_yoto(self, file_path: Path, session_id: str) -> TranscodedAudioResponse:
        """
        Upload a file to Yoto and return the track URL and duration.
        Creates a fresh API client in the thread pool worker to avoid event loop conflicts.

        Args:
            file_path: Path to the audio file
            session_id: Current upload session ID

        Returns:
            TranscodedAudioResponse with upload details
        """

        async def _do_upload(access_token: str) -> TranscodedAudioResponse:
            # Create a fresh API client in this thread's event loop
            # This avoids the issue of the client being bound to the main Uvicorn event loop
            from yoto_web_server.api.config import YotoApiConfig
            from yoto_web_server.api.models import TokenData
            from yoto_web_server.core.config import get_settings

            settings = get_settings()
            config = YotoApiConfig(client_id=settings.yoto_client_id)
            api = YotoApiClient(config=config)

            # Set the access token for this client
            import time

            api.auth._token_data = TokenData(
                access_token=access_token,
                refresh_token=None,
                expires_at=time.time() + 600,
            )

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
            transcoded = await api.poll_for_transcoding(upload.upload_id, loudnorm=False)

            return transcoded

        # Get the upload session to get the access token
        upload_session = self._upload_session_service.get_session(session_id)
        if not upload_session:
            raise ValueError(f"Upload session {session_id} not found")

        if not upload_session.user_session_id:
            raise ValueError(f"Upload session {session_id} has no user session ID")

        # Get the access token from the session service
        session_data = self._session_aware_api_service.session_service.get_session(
            upload_session.user_session_id
        )
        if not session_data:
            raise ValueError(f"User session {upload_session.user_session_id} not found")

        # Run async code in a new event loop with a fresh API client
        return asyncio.run(_do_upload(session_data.access_token))

    def _update_playlist(
        self, playlist_id: str, new_tracks: list[Track], upload_mode: UploadMode, session_id: str
    ) -> list[int]:
        """Update playlist with new tracks/chapters.

        Args:
            playlist_id: ID of the playlist (card) to update
            new_tracks: List of Track objects to add
            upload_mode: Mode for upload ('chapters' or 'tracks')
            session_id: Current upload session ID

        Returns:
            List of indices of the newly added chapters
        """

        async def _do_update(access_token: str) -> list[int]:
            # Create a fresh API client in this thread's event loop
            # This avoids the issue of the client being bound to the main Uvicorn event loop
            from yoto_web_server.api.config import YotoApiConfig
            from yoto_web_server.api.models import TokenData
            from yoto_web_server.core.config import get_settings

            settings = get_settings()
            config = YotoApiConfig(client_id=settings.yoto_client_id)
            api = YotoApiClient(config=config)

            # Set the access token for this client
            import time

            api.auth._token_data = TokenData(
                access_token=access_token,
                refresh_token=None,
                expires_at=time.time() + 600,
            )

            card = await api.get_card(playlist_id)
            if not card.content:
                card.content = CardContent(chapters=[])

            if card.content.chapters is None:
                card.content.chapters = []

            original_chapter_count = len(card.content.chapters)
            new_chapter_indices = []

            if upload_mode == "chapters":
                # Create a chapter for each track
                chapter_key = 0
                existing_keys = {chapter.key for chapter in card.content.chapters}
                while str(chapter_key) in existing_keys:
                    chapter_key += 1

                for key, track in enumerate(new_tracks):
                    track.key = str(key)
                    # Find next available chapter key
                    while str(chapter_key) in existing_keys:
                        chapter_key += 1

                    chapter = Chapter(title=track.title, tracks=[track], key=str(chapter_key))
                    card.content.chapters.append(chapter)
                    existing_keys.add(str(chapter_key))

                # All appended chapters are new
                new_chapter_indices = list(
                    range(original_chapter_count, len(card.content.chapters))
                )

            elif upload_mode == "tracks":
                # Add all tracks to a new chapter
                # Or append to the last chapter if it exists?
                # Let's create a new chapter for this batch upload
                key = 0
                current_keys = {chapter.key for chapter in card.content.chapters}
                while str(key) in current_keys:
                    key += 1
                for idx, track in enumerate(new_tracks):
                    track.key = str(idx)
                chapter = Chapter(
                    title="New Uploads",  # TODO: Maybe use date or something?
                    tracks=new_tracks,
                    key=str(key),
                )
                card.content.chapters.append(chapter)
                new_chapter_indices = [len(card.content.chapters) - 1]

            await api.update_card(card)
            return new_chapter_indices

        # Get the upload session to get the access token
        upload_session = self._upload_session_service.get_session(session_id)
        if not upload_session:
            raise ValueError(f"Upload session {session_id} not found")

        if not upload_session.user_session_id:
            raise ValueError(f"Upload session {session_id} has no user session ID")

        # Get the access token from the session service
        session_data = self._session_aware_api_service.session_service.get_session(
            upload_session.user_session_id
        )
        if not session_data:
            raise ValueError(f"User session {upload_session.user_session_id} not found")

        # Run async code in a new event loop with a fresh API client
        return asyncio.run(_do_update(session_data.access_token))

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
