"""
Upload Session Service.

Manages upload sessions, file state, and queue operations for the web interface.
Tracks multiple concurrent upload sessions with their files and processing status.
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from yoto_web_server.models import (
    FileUploadStatus,
    UploadFileStatus,
    UploadSession,
    UploadSessionInitRequest,
)


class UploadSessionService:
    """
    Service for managing upload sessions.

    Maintains in-memory state of active upload sessions including file metadata,
    processing status, and progress tracking.
    """

    def __init__(self) -> None:
        """Initialize the upload session service."""
        # In production, this would use Redis or a database
        # Format: {session_id: UploadSession}
        self._sessions: dict[str, UploadSession] = {}
        # Track sessions by playlist for quick lookup
        # Format: {playlist_id: [session_ids]}
        self._playlist_sessions: dict[str, list[str]] = {}

    def create_session(
        self,
        playlist_id: str,
        user_id: str,
        user_session_id: str | None,
        request: UploadSessionInitRequest,
    ) -> UploadSession:
        """
        Create a new upload session.

        Args:
            playlist_id: ID of the playlist to upload to
            user_id: ID of the authenticated user
            user_session_id: The user's auth session ID for API calls (optional)
            request: Upload configuration request

        Returns:
            UploadSession with generated session_id
        """
        session_id = str(uuid.uuid4())

        session = UploadSession(
            session_id=session_id,
            playlist_id=playlist_id,
            user_id=user_id,
            user_session_id=user_session_id,
            upload_mode=request.upload_mode,
            normalize=request.normalize,
            target_lufs=request.target_lufs,
            normalize_batch=request.normalize_batch,
            analyze_intro_outro=request.analyze_intro_outro,
            segment_seconds=request.segment_seconds,
            similarity_threshold=request.similarity_threshold,
            show_waveform=request.show_waveform,
        )

        self._sessions[session_id] = session

        # Track by playlist
        if playlist_id not in self._playlist_sessions:
            self._playlist_sessions[playlist_id] = []
        self._playlist_sessions[playlist_id].append(session_id)

        logger.info(f"Created upload session {session_id} for playlist {playlist_id}")
        return session

    def register_file(
        self,
        session_id: str,
        filename: str,
        size_bytes: int,
        original_title: str | None = None,
    ) -> UploadFileStatus | None:
        """
        Register a file in an upload session.

        Args:
            session_id: ID of the upload session
            filename: Name of the file
            size_bytes: Size of the file in bytes
            original_title: Original title from metadata provider (for URL uploads)

        Returns:
            UploadFileStatus with generated file_id, or None if session not found
        """
        if session_id not in self._sessions:
            logger.warning(f"Session {session_id} not found")
            return None

        session = self._sessions[session_id]
        file_id = str(uuid.uuid4())

        file_status = UploadFileStatus(
            file_id=file_id,
            filename=filename,
            size_bytes=size_bytes,
            status=FileUploadStatus.PENDING,
            original_title=original_title,
        )

        session.files.append(file_status)
        logger.info(f"Registered file {filename} ({size_bytes} bytes) in session {session_id}")
        return file_status

    def mark_file_uploaded(
        self,
        session_id: str,
        file_id: str,
        temp_path: str,
    ) -> bool:
        """
        Mark a file as successfully uploaded.

        Args:
            session_id: ID of the upload session
            file_id: ID of the file
            temp_path: Path where file was saved temporarily

        Returns:
            True if marked, False if not found
        """
        if session_id not in self._sessions:
            return False

        session = self._sessions[session_id]

        for file_status in session.files:
            if file_status.file_id == file_id:
                file_status.status = FileUploadStatus.QUEUED
                file_status.progress = 100.0
                file_status.temp_path = temp_path
                file_status.uploaded_at = datetime.now(UTC)
                logger.info(f"File {file_id} uploaded successfully to {temp_path}")
                return True

        return False

    def mark_file_processing(
        self,
        session_id: str,
        file_id: str,
        processing_step: str,
    ) -> bool:
        """
        Mark a file as being processed.

        Args:
            session_id: ID of the upload session
            file_id: ID of the file
            processing_step: Current processing step (normalizing, analyzing, etc.)

        Returns:
            True if marked, False if not found
        """
        if session_id not in self._sessions:
            return False

        session = self._sessions[session_id]

        for file_status in session.files:
            if file_status.file_id == file_id:
                file_status.status = FileUploadStatus.PROCESSING
                file_status.current_step = processing_step
                # Update progress based on stage
                self.update_file_progress(session_id, file_id, processing_step, 0)
                return True

        return False

    def mark_file_yoto_uploading(
        self,
        session_id: str,
        file_id: str,
    ) -> bool:
        if session_id not in self._sessions:
            return False

        session = self._sessions[session_id]

        for file_status in session.files:
            if file_status.file_id == file_id:
                file_status.status = FileUploadStatus.YOTO_UPLOADING
                self.update_file_progress(session_id, file_id, "yoto_uploading", 0)
                return True

        return False

    def mark_file_done(
        self,
        session_id: str,
        file_id: str,
    ) -> bool:
        """
        Mark a file as successfully processed and uploaded to Yoto API.

        Args:
            session_id: ID of the upload session
            file_id: ID of the file

        Returns:
            True if marked, False if not found
        """
        if session_id not in self._sessions:
            return False

        session = self._sessions[session_id]

        for file_status in session.files:
            if file_status.file_id == file_id:
                file_status.status = FileUploadStatus.DONE
                file_status.progress = 100.0
                file_status.current_step = "done"
                logger.info(f"File {file_id} processing complete")
                return True

        return False

    def mark_file_error(
        self,
        session_id: str,
        file_id: str,
        error_message: str,
    ) -> bool:
        """
        Mark a file as having an error.

        Args:
            session_id: ID of the upload session
            file_id: ID of the file
            error_message: Error description

        Returns:
            True if marked, False if not found
        """
        if session_id not in self._sessions:
            return False

        session = self._sessions[session_id]

        for file_status in session.files:
            if file_status.file_id == file_id:
                file_status.status = FileUploadStatus.ERROR
                file_status.error = error_message
                logger.error(f"File {file_id} error: {error_message}")
                return True

        return False

    def update_file_filename(
        self,
        session_id: str,
        file_id: str,
        new_filename: str,
    ) -> bool:
        """
        Update the filename for a file in a session.

        Args:
            session_id: ID of the upload session
            file_id: ID of the file
            new_filename: New filename

        Returns:
            True if updated, False if not found
        """
        if session_id not in self._sessions:
            return False

        session = self._sessions[session_id]

        for file_status in session.files:
            if file_status.file_id == file_id:
                old_filename = file_status.filename
                file_status.filename = new_filename
                logger.info(f"Updated filename for {file_id}: {old_filename} -> {new_filename}")
                return True

        return False

    def get_session(self, session_id: str) -> UploadSession | None:
        """
        Get a session by ID.

        Args:
            session_id: ID of the session

        Returns:
            UploadSession or None if not found
        """
        return self._sessions.get(session_id)

    def get_playlist_sessions(
        self, playlist_id: str, include_done: bool = True
    ) -> list[UploadSession]:
        """
        Get all sessions for a playlist.

        Args:
            playlist_id: ID of the playlist
            include_done: If True, include completed sessions. Default True.

        Returns:
            List of UploadSession objects
        """
        session_ids = self._playlist_sessions.get(playlist_id, [])
        sessions = []
        for session_id in session_ids:
            session = self._sessions.get(session_id)
            if session and (include_done or session.overall_status != FileUploadStatus.DONE):
                sessions.append(session)
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and clean up temp files.

        Args:
            session_id: ID of the session

        Returns:
            True if deleted, False if not found
        """
        if session_id not in self._sessions:
            return False

        session = self._sessions[session_id]

        # Clean up temp files
        for file_status in session.files:
            if file_status.temp_path:
                try:
                    Path(file_status.temp_path).unlink(missing_ok=True)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {file_status.temp_path}: {e}")

        # Remove from playlist tracking
        playlist_id = session.playlist_id
        if playlist_id in self._playlist_sessions:
            try:
                self._playlist_sessions[playlist_id].remove(session_id)
            except ValueError:
                pass

        # Remove session
        del self._sessions[session_id]
        logger.info(f"Deleted upload session {session_id}")
        return True

    def update_new_chapter_ids(self, session_id: str, chapter_ids: list[str]) -> None:
        """Update the list of new chapter IDs for a session."""
        session = self.get_session(session_id)
        if session:
            session.new_chapter_ids = chapter_ids

    def mark_session_done(self, session_id: str) -> None:
        """Mark the session as done."""
        session = self.get_session(session_id)
        if session:
            session.session_done = True

    def update_file_progress(
        self, session_id: str, file_id: str, step: str, step_progress: float = 100.0
    ) -> bool:
        """
        Update file progress based on processing stage.

        Processing stages and their progress ranges:
        - Pending/Queued: 0%
        - Uploading (local): 25%
        - Normalizing: 50%
        - Processing: 75%
        - Yoto Uploading: 90%
        - Done: 100%

        Args:
            session_id: ID of the upload session
            file_id: ID of the file
            step: Current processing step
            step_progress: Progress within the current step (0-100)

        Returns:
            True if updated, False if not found
        """
        if session_id not in self._sessions:
            return False

        session = self._sessions[session_id]
        for file_status in session.files:
            if file_status.file_id == file_id:
                # Define stage weights (percentage of total completion)
                stage_progress = {
                    "pending": 0,
                    "queued": 5,
                    "uploading_local": 25,  # Local upload to server
                    "normalizing": 50,  # Audio normalization
                    "processing": 75,  # Analysis and track creation
                    "yoto_uploading": 90,  # Uploading to Yoto API
                    "done": 100,
                }

                base_progress = stage_progress.get(step, 0)
                # Calculate progress as base + partial progress within stage (up to next stage)
                next_stage_progress = stage_progress.get(step, 100)
                stage_range = 10  # Default range between stages

                # Find the next stage progress for better calculation
                sorted_stages = sorted(stage_progress.values())
                try:
                    current_idx = sorted_stages.index(base_progress)
                    if current_idx + 1 < len(sorted_stages):
                        next_stage_progress = sorted_stages[current_idx + 1]
                except (ValueError, IndexError):
                    pass

                stage_range = next_stage_progress - base_progress
                file_status.progress = base_progress + (stage_range * step_progress / 100.0)
                file_status.current_step = step
                return True

        return False

    def update_file_title(self, session_id: str, file_id: str, title: str) -> bool:
        """
        Update the custom title for a file in an upload session.

        Args:
            session_id: ID of the upload session
            file_id: ID of the file to update
            title: New title for the file

        Returns:
            True if updated, False if not found
        """
        if session_id not in self._sessions:
            return False

        session = self._sessions[session_id]
        for file_status in session.files:
            if file_status.file_id == file_id:
                file_status.custom_title = title
                return True

        return False
