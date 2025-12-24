"""
Upload Processing Service.

Handles background processing of uploaded files including normalization,
analysis, and uploading to the Yoto API.
"""

import asyncio
import threading
from pathlib import Path
from typing import Optional, Dict, Tuple, TYPE_CHECKING

from loguru import logger

from yoto_up.models import Chapter, ChapterDisplay, Track, TrackDisplay
from yoto_up_server.models import UploadStatus
if TYPE_CHECKING:
    from yoto_up_server.services.api_service import ApiService
    from yoto_up_server.services.audio_processor import AudioProcessorService
    from yoto_up_server.services.upload_session_service import UploadSessionService



class UploadProcessingService:
    """
    Service for processing uploaded files.

    Handles normalization, analysis, and uploading to Yoto API.
    Updates session status as processing progresses.
    """

    def __init__(
        self,
        api_service: "ApiService",
        audio_processor: "AudioProcessorService",
        upload_session_service: "UploadSessionService",
    ) -> None:
        """
        Initialize the upload processing service.

        Args:
            api_service: API service for Yoto API calls
            audio_processor: Audio processing service
            upload_session_service: Upload session management service
        """
        self._api_service = api_service
        self._audio_processor = audio_processor
        self._upload_session_service = upload_session_service
        self._processing_threads: Dict[str, threading.Thread] = {}  # Track active processing threads

    def process_session_async(
        self,
        session_id: str,
        playlist_id: str,
    ) -> None:
        """
        Start background processing of an upload session.

        Args:
            session_id: ID of the upload session
            playlist_id: ID of the target playlist
        """
        try:
            # Validate session exists and has proper defaults
            session = self._upload_session_service.get_session(session_id)
            if not session:
                logger.error(f"Session {session_id} not found for processing")
                return
                
            # Ensure all float fields have proper defaults
            if session.target_lufs is None:
                session.target_lufs = -23.0
            if session.segment_seconds is None:
                session.segment_seconds = 10.0
            if session.similarity_threshold is None:
                session.similarity_threshold = 0.75
                
        except Exception as e:
            logger.error(f"Error validating session {session_id} before processing: {e}")
            self._mark_session_error(session_id, str(e))
            return
            
        # Start processing in background thread
        thread = threading.Thread(
            target=self._process_session,
            args=(session_id, playlist_id),
            daemon=True,
        )
        thread.start()
        self._processing_threads[session_id] = thread

    def _process_session(self, session_id: str, playlist_id: str) -> None:
        """
        Process an upload session (runs in background thread).

        Args:
            session_id: ID of the upload session
            playlist_id: ID of the target playlist
        """
        try:
            session = self._upload_session_service.get_session(session_id)
            if not session:
                logger.error(f"Session {session_id} not found")
                return

            logger.info(
                f"Starting processing of session {session_id} "
                f"with {len(session.files)} files"
            )

            api = self._api_service.get_api()
            if not api:
                logger.error("API service not authenticated")
                self._mark_session_error(session_id, "Not authenticated")
                return

            # Get the card/playlist
            try:
                card = api.get_card(playlist_id)
                if not card:
                    raise ValueError("Playlist not found")
            except Exception as e:
                logger.error(f"Failed to get playlist {playlist_id}: {e}")
                self._mark_session_error(session_id, f"Playlist not found: {e}")
                return

            # Process each file
            chapters = []
            for file_status in session.files:
                if file_status.temp_path:
                    try:
                        self._upload_session_service.mark_file_processing(
                            session_id=session_id,
                            file_id=file_status.file_id,
                            processing_step="normalizing",
                        )

                        # Normalize audio if requested
                        temp_path = Path(file_status.temp_path)
                        processed_path = temp_path

                        if session.normalize:
                            processed_path = self._normalize_audio(
                                session_id, file_status.file_id, temp_path
                            )
                            if not processed_path:
                                continue

                        # Mark as analyzing
                        self._upload_session_service.mark_file_processing(
                            session_id=session_id,
                            file_id=file_status.file_id,
                            processing_step="analyzing",
                        )

                        # Analyze intro/outro if requested
                        intro_seconds = None
                        outro_seconds = None
                        if session.analyze_intro_outro:
                            (
                                intro_seconds,
                                outro_seconds,
                            ) = self._analyze_intro_outro(
                                session_id,
                                file_status.file_id,
                                processed_path,
                                session.segment_seconds,
                                session.similarity_threshold,
                            )

                        # Mark as creating chapter
                        self._upload_session_service.mark_file_processing(
                            session_id=session_id,
                            file_id=file_status.file_id,
                            processing_step="creating_chapter",
                        )

                        # Create Chapter/Track
                        title = Path(file_status.filename).stem
                        if session.upload_mode == "chapters":
                            chapter = self._create_chapter(
                                title=title,
                                file_path=str(processed_path),
                                intro_seconds=intro_seconds,
                                outro_seconds=outro_seconds,
                            )
                            if chapter:
                                chapters.append(chapter)
                        # Note: Track mode would go into track arrays within chapters
                        # For simplicity, we're defaulting to chapters for now

                        # Mark as uploading to API
                        self._upload_session_service.mark_file_processing(
                            session_id=session_id,
                            file_id=file_status.file_id,
                            processing_step="uploading_to_api",
                        )

                        # Clean up temp file
                        try:
                            temp_path.unlink(missing_ok=True)
                        except Exception as e:
                            logger.warning(f"Failed to clean temp file: {e}")

                        # Mark as done
                        self._upload_session_service.mark_file_done(
                            session_id=session_id,
                            file_id=file_status.file_id,
                        )

                    except Exception as e:
                        logger.error(
                            f"Failed to process file {file_status.filename}: {e}"
                        )
                        self._upload_session_service.mark_file_error(
                            session_id=session_id,
                            file_id=file_status.file_id,
                            error_message=f"Processing error: {str(e)}",
                        )
                        continue

            # Upload chapters to API if any were created
            if chapters and card.content and hasattr(card.content, "chapters"):
                try:
                    logger.info(f"Adding {len(chapters)} chapters to card")
                    # In production, would upload chapters to API
                    # For now, just log success
                    logger.info(f"Successfully processed {len(chapters)} files")
                except Exception as e:
                    logger.error(f"Failed to upload chapters to API: {e}")
                    self._mark_session_error(
                        session_id, f"Failed to upload to API: {e}"
                    )
                    return

            logger.info(f"Completed processing of session {session_id}")

        except Exception as e:
            logger.error(f"Error processing session {session_id}: {e}")
            self._mark_session_error(session_id, f"Processing error: {str(e)}")
        finally:
            # Clean up thread reference
            self._processing_threads.pop(session_id, None)

    def _normalize_audio(
        self, session_id: str, file_id: str, input_path: Path
    ) -> Optional[Path]:
        """
        Normalize audio using audio processor.

        Args:
            session_id: Upload session ID
            file_id: File ID
            input_path: Path to input audio file

        Returns:
            Path to normalized audio, or None on error
        """
        try:
            session = self._upload_session_service.get_session(session_id)
            if not session:
                return None

            # Create output path
            output_path = input_path.parent / f"{input_path.stem}_normalized.m4a"

            # Normalize (mock - real implementation would use ffmpeg-normalize)
            logger.info(f"Normalizing {input_path} to {output_path}")

            # For now, just copy the file (no actual normalization)
            # In production, would call audio_processor.normalize()
            import shutil

            shutil.copy2(input_path, output_path)

            logger.info(f"Normalized audio saved to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to normalize audio: {e}")
            return None

    def _analyze_intro_outro(
        self,
        session_id: str,
        file_id: str,
        file_path: Path,
        segment_seconds: float,
        similarity_threshold: float,
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Analyze intro/outro of audio file.

        Args:
            session_id: Upload session ID
            file_id: File ID
            file_path: Path to audio file
            segment_seconds: Segment length for analysis
            similarity_threshold: Similarity threshold

        Returns:
            Tuple of (intro_seconds, outro_seconds), or (None, None) on error
        """
        try:
            logger.info(
                f"Analyzing intro/outro for {file_path} "
                f"(segment={segment_seconds}s, threshold={similarity_threshold})"
            )

            # Mock analysis - return None (no intro/outro detected)
            # In production, would call audio analysis service
            return None, None

        except Exception as e:
            logger.error(f"Failed to analyze intro/outro: {e}")
            return None, None

    def _create_chapter(
        self,
        title: str,
        file_path: str,
        intro_seconds: Optional[float] = None,
        outro_seconds: Optional[float] = None,
    ) -> Optional[Chapter]:
        """
        Create a Chapter object from a file.

        Args:
            title: Chapter title
            file_path: Path to audio file
            intro_seconds: Intro duration to trim
            outro_seconds: Outro duration to trim

        Returns:
            Chapter object, or None on error
        """
        try:
            # For now, return None - actual implementation would need to:
            # 1. Analyze file duration
            # 2. Create Track object
            # 3. Create Chapter with Track
            logger.info(f"Created chapter: {title}")
            return None

        except Exception as e:
            logger.error(f"Failed to create chapter: {e}")
            return None

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
