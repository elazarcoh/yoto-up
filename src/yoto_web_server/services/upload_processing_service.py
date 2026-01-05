"""
Upload Processing Service.

Handles background processing of uploaded files including normalization,
analysis, and uploading to the Yoto API.
"""

import asyncio
import contextlib
import queue
import threading
import time
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

    Uses a file-level work queue to enable true parallel processing both within
    and across sessions. Multiple workers can process different files from the
    same or different sessions simultaneously.
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

        # File-level work queue: (session_id, file_id, playlist_id)
        # This enables parallel processing within and across sessions
        self._file_queue: queue.Queue[tuple[str, str, str]] = queue.Queue()
        self._stop_event = threading.Event()

        # Multiple worker threads for parallel file processing
        # Each worker processes files independently from the queue
        self._worker_threads: list[threading.Thread] = []
        self._num_workers = 4

        # File processing state tracking (session_id, file_id) -> processing
        self._processing: set[tuple[str, str]] = set()
        self._processing_lock = threading.Lock()

        # Track sessions that should be stopped
        self._sessions_to_stop: set[str] = set()
        self._stop_lock = threading.Lock()

        # Track batch normalization state per session
        self._batch_normalizing: set[str] = set()
        self._batch_norm_lock = threading.Lock()

        # Cache processed tracks for session finalization
        # Key: session_id, Value: list of (file_id, Track) tuples
        self._processed_tracks: dict[str, list[tuple[str, Track]]] = {}
        self._processed_tracks_lock = threading.Lock()

    def start(self) -> None:
        """Start the worker threads."""
        if self._worker_threads and any(t.is_alive() for t in self._worker_threads):
            return

        self._stop_event.clear()
        self._worker_threads = []
        for i in range(self._num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"UploadWorker-{i}",
                daemon=True,
            )
            worker.start()
            self._worker_threads.append(worker)
        logger.info(f"Upload processing service started with {self._num_workers} workers")

    def stop(self) -> None:
        """Stop all worker threads."""
        logger.info("Stopping upload processing service...")
        self._stop_event.set()
        for worker in self._worker_threads:
            if worker.is_alive():
                worker.join(timeout=5.0)
        logger.info("Upload processing service stopped")

    def process_session_async(
        self,
        session_id: str,
        playlist_id: str,
    ) -> None:
        """
        Queue a session's files for processing.

        In non-batch mode: queues individual files as they are ready
        In batch mode: queues all files when finalize is called

        Args:
            session_id: ID of the upload session
            playlist_id: ID of the target playlist
        """
        session = self._upload_session_service.get_session(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found for processing")
            return

        # Only queue files that are in the processing queue
        files_to_queue = session.files_to_process
        if not files_to_queue:
            logger.info(f"Session {session_id} has no files to process")
            return

        # Queue each file individually for parallel processing
        for file_id in files_to_queue:
            self._file_queue.put((session_id, file_id, playlist_id))
            logger.debug(f"Queued file {file_id} from session {session_id} for processing")

        logger.info(
            f"Queued {len(files_to_queue)} files from session {session_id} for parallel processing"
        )

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
        """Main worker loop processing files from the queue.

        Each worker processes files independently, enabling true parallelization
        both within and across sessions.
        """
        while not self._stop_event.is_set():
            try:
                # Get next file to process (timeout prevents blocking shutdown)
                session_id, file_id, playlist_id = self._file_queue.get(timeout=1.0)

                # Check if file is already being processed (shouldn't happen, but defensive)
                with self._processing_lock:
                    if (session_id, file_id) in self._processing:
                        logger.warning(f"File {file_id} already being processed, skipping")
                        self._file_queue.task_done()
                        continue
                    self._processing.add((session_id, file_id))

                try:
                    self._process_file(session_id, file_id, playlist_id)
                except Exception as e:
                    logger.error(f"Error processing file {file_id} in session {session_id}: {e}")
                finally:
                    # Mark as no longer processing
                    with self._processing_lock:
                        self._processing.discard((session_id, file_id))
                    self._file_queue.task_done()

            except queue.Empty:
                # No files to process, check if we should do batch normalization
                # This happens when all files are queued but batch normalization hasn't run yet
                continue
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                time.sleep(1.0)

    def _ensure_batch_normalization(self, session_id: str) -> bool:
        """
        Ensure batch normalization has run for this session (if needed).
        Returns True if normalization completed successfully, False if error.
        Run once per session when first file is processed in batch mode.
        """
        # Check if already normalizing or completed
        if session_id in self._batch_normalizing:
            logger.debug(f"Batch normalization already triggered for {session_id}")
            return True

        session = self._upload_session_service.get_session(session_id)
        if not session or not session.normalize or not session.normalize_batch:
            # No batch normalization needed
            return True

        # Mark that we're handling batch normalization for this session
        with self._batch_norm_lock:
            if session_id in self._batch_normalizing:
                # Another worker already started it
                return True
            self._batch_normalizing.add(session_id)

        try:
            # Collect files that need normalization
            files_to_normalize = [f for f in session.files if f.file_id in session.files_to_process]
            if not files_to_normalize:
                logger.debug(f"No files to normalize in session {session_id}")
                return True

            logger.info(
                f"Starting batch normalization for session {session_id} with {len(files_to_normalize)} files"
            )

            # Perform batch normalization
            paths_to_normalize = []
            for file_status in files_to_normalize:
                if file_status.temp_path:
                    paths_to_normalize.append(str(file_status.temp_path))
                    self._upload_session_service.mark_file_processing(
                        session_id, file_status.file_id, "normalizing"
                    )

            if paths_to_normalize:
                normalized_paths = self._audio_processor.normalize(
                    input_paths=paths_to_normalize,
                    output_dir=str(Path(paths_to_normalize[0]).parent / "normalized"),
                    target_level=session.target_lufs,
                    batch_mode=True,
                )

                # Update temp paths in file status
                for i, file_status in enumerate(files_to_normalize):
                    if i < len(normalized_paths):
                        assert file_status.temp_path is not None
                        input_path = Path(file_status.temp_path)
                        normalized_path = Path(normalized_paths[i])
                        # Remove original temp file if different
                        if normalized_path != input_path:
                            with contextlib.suppress(Exception):
                                input_path.unlink(missing_ok=True)
                        file_status.temp_path = normalized_paths[i]

            logger.info(f"Batch normalization complete for session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Batch normalization failed for session {session_id}: {e}")
            self._mark_session_error(session_id, f"Normalization failed: {e}")
            return False
        finally:
            # Remove from batch normalizing set
            with self._batch_norm_lock:
                self._batch_normalizing.discard(session_id)

    def _process_file(self, session_id: str, file_id: str, playlist_id: str) -> None:
        """
        Process a single file: Normalize (if not batch) -> Analyze -> Upload -> Create Track.
        This runs in a worker thread from the file-level queue.
        Multiple files can be processed in parallel (both within and across sessions).
        """
        try:
            session = self._upload_session_service.get_session(session_id)
            if not session:
                logger.error(f"Session {session_id} not found")
                return

            # Find the file status for this file_id
            file_status = next((f for f in session.files if f.file_id == file_id), None)
            if not file_status:
                logger.error(f"File {file_id} not found in session {session_id}")
                return

            assert file_status.temp_path is not None

            # Step 1: Ensure batch normalization has run (if needed)
            if session.normalize and session.normalize_batch:  # noqa: SIM102
                if not self._ensure_batch_normalization(session_id):
                    return  # Error already logged

            # Step 2: Single-file normalization (if not batch mode)
            if session.normalize and not session.normalize_batch:
                self._upload_session_service.mark_file_processing(
                    session_id, file_id, "normalizing"
                )
                try:
                    normalized_paths = self._audio_processor.normalize(
                        input_paths=[str(file_status.temp_path)],
                        output_dir=str(Path(file_status.temp_path).parent),
                        target_level=session.target_lufs,
                        batch_mode=False,
                    )
                    if normalized_paths:
                        # Remove original temp file if different
                        normalized_path = Path(normalized_paths[0])
                        input_path = Path(file_status.temp_path)
                        if normalized_path != input_path:
                            with contextlib.suppress(Exception):
                                input_path.unlink(missing_ok=True)
                        file_status.temp_path = normalized_paths[0]
                except Exception as e:
                    logger.error(f"Normalization failed for file {file_id}: {e}")
                    self._upload_session_service.mark_file_error(
                        session_id, file_id, f"Normalization failed: {e}"
                    )
                    return

            # Step 3: Analyze and upload
            self._upload_session_service.mark_file_processing(session_id, file_id, "processing")

            track = self._process_file_pipeline(
                session_id=session_id,
                file_status=file_status,
                session=session,
            )

            if not track:
                logger.error(f"Failed to process file {file_id}")
                return

            # Step 4: Cache processed track
            with self._processed_tracks_lock:
                if session_id not in self._processed_tracks:
                    self._processed_tracks[session_id] = []
                self._processed_tracks[session_id].append((file_id, track))

            # Step 5: Remove from processing queue to mark as complete
            if file_id in session.files_to_process:
                session.files_to_process.remove(file_id)

            # Step 6: Check if this is the last file in the session
            # If so, update the playlist with all processed tracks
            if not session.files_to_process:
                # All files done, update playlist
                self._finalize_session_playlist(session_id, playlist_id)

        except Exception as e:
            logger.error(f"Error processing file {file_id} in session {session_id}: {e}")
            self._upload_session_service.mark_file_error(session_id, file_id, str(e))

    def _finalize_session_playlist(self, session_id: str, playlist_id: str) -> None:
        """
        Update the playlist with all processed tracks from the session.
        Called when all files in the session have been processed.
        """
        try:
            # Get processed tracks for this session
            with self._processed_tracks_lock:
                file_track_pairs = self._processed_tracks.pop(session_id, [])

            if not file_track_pairs:
                logger.info(f"No tracks to add to playlist for session {session_id}")
                return

            # Reconstruct tracks in file order
            session = self._upload_session_service.get_session(session_id)
            if not session:
                logger.error(f"Session {session_id} not found for playlist update")
                return

            # Build a dict of file_id -> track for quick lookup
            track_dict = dict(file_track_pairs)

            # Reconstruct in original file order
            ordered_tracks = []
            for file_status in session.files:
                if file_status.file_id in track_dict:
                    ordered_tracks.append(track_dict[file_status.file_id])

            if not ordered_tracks:
                logger.info(f"No tracks to add to playlist for session {session_id}")
                return

            # Update playlist
            new_indices = self._update_playlist(
                playlist_id, ordered_tracks, session.upload_mode, session_id
            )
            new_ids = [str(idx) for idx in new_indices]
            self._upload_session_service.update_new_chapter_ids(session_id, new_ids)

            logger.info(
                f"Successfully updated playlist {playlist_id} with {len(ordered_tracks)} tracks from session {session_id}"
            )
        except Exception as e:
            logger.error(f"Failed to finalize playlist for session {session_id}: {e}")
            self._mark_session_error(session_id, f"Failed to add tracks to playlist: {str(e)}")
        finally:
            # Mark session as done
            self._upload_session_service.mark_session_done(session_id)
            # Clear stop flag if set
            self._clear_stop_flag(session_id)

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
                    output_dir=str(input_path.parent / "normalized"),
                    target_level=session.target_lufs,
                    batch_mode=False,
                )
                if normalized_paths:
                    # remove the original input path if different
                    normalized_path = Path(normalized_paths[0])
                    if normalized_path != input_path:
                        with contextlib.suppress(Exception):
                            input_path.unlink(missing_ok=True)

                    input_path = normalized_path
                    # Update file status with new path just in case
                    file_status.temp_path = str(input_path)

            # 2. Analyze (Intro/Outro)
            if self._is_session_stopped(session_id):
                logger.info(f"Session {session_id} stopped before analysis")
                return None

            # self._upload_session_service.mark_file_processing(
            #     session_id, file_status.file_id, "analyzing"
            # )

            # Placeholder for analysis
            # if session.analyze_intro_outro:
            #     pass

            # 3. Upload
            if self._is_session_stopped(session_id):
                logger.info(f"Session {session_id} stopped before upload")
                return None

            self._upload_session_service.mark_file_yoto_uploading(session_id, file_status.file_id)

            transcoded = self._upload_file_to_yoto(input_path, session_id)

            transcoded_info = transcoded.transcode.transcoded_info

            # Use original title if available (from URL metadata), otherwise extract from filename
            if file_status.original_title:
                title = file_status.original_title
            else:
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
            # We only delete if it's a temp file we created/managed
            # But here input_path IS the temp path (possibly normalized)
            # We should probably delete it.
            with contextlib.suppress(Exception):
                input_path.unlink(missing_ok=True)

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
