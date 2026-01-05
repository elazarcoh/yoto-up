"""
Unified Upload Orchestrator Service.

Handles both file uploads and URL-based downloads through a unified pipeline.
Routes URLs to appropriate services based on scheme (e.g., "youtube:VIDEO_ID").
Services provide local file paths via background async operations.
"""

import asyncio
import pathlib
from collections.abc import Callable
from typing import Protocol

from loguru import logger

from yoto_web_server.models import FileUploadStatus, UploadFileStatus
from yoto_web_server.services.upload_processing_service import UploadProcessingService
from yoto_web_server.services.upload_session_service import UploadSessionService


class FileUploadHandler(Protocol):
    """Protocol for handling file uploads within a session."""

    async def handle_file_upload(
        self, session_id: str, playlist_id: str, filename: str, content: bytes
    ) -> str:
        """
        Process an uploaded file and save it locally.

        Args:
            session_id: Upload session ID
            playlist_id: Playlist ID
            filename: Name of the file
            content: File content bytes

        Returns:
            Local file path to the saved file
        """
        ...


class URLProvider(Protocol):
    """Protocol for services that can download/provide files from URLs."""

    async def get_local_path_for_url(self, url_path: str) -> str:
        """
        Download or provide a local file path for the given URL path.

        Args:
            url_path: The path/ID part of the URL (after scheme:)

        Returns:
            Local file path to the downloaded/processed file
        """
        ...


class URLMetadataProvider(Protocol):
    """Protocol for services that can provide metadata for URLs."""

    async def get_url_title(self, url_path: str) -> str | None:
        """
        Get the title/name for the given URL.

        Args:
            url_path: The path/ID part of the URL (after scheme:)

        Returns:
            Title string, or None if not available
        """
        ...


class DefaultFileUploadHandler:
    """Default handler for file uploads - saves to temp directory."""

    async def handle_file_upload(
        self, session_id: str, playlist_id: str, filename: str, content: bytes
    ) -> str:
        """Save uploaded file to temp directory."""
        import tempfile

        temp_base = pathlib.Path(tempfile.gettempdir()) / "yoto_web_uploads" / session_id
        temp_base.mkdir(parents=True, exist_ok=True)

        temp_path = temp_base / filename
        with open(temp_path, "wb") as f:
            f.write(content)

        return str(temp_path)


class UploadOrchestrator:
    """
    Unified orchestrator for handling file and URL uploads.

    Provides a single interface for registering files and URLs, delegating
    to appropriate services, and managing the complete upload pipeline.
    """

    def __init__(
        self,
        upload_session_service: UploadSessionService,
        upload_processing_service: UploadProcessingService,
    ):
        self._url_providers: dict[str, URLProvider] = {}
        self._metadata_providers: dict[str, URLMetadataProvider] = {}
        self._mark_file_uploaded_fn: Callable[[str, str, str], UploadFileStatus | None] | None = (
            None
        )
        self._file_upload_handler = DefaultFileUploadHandler()

        self._upload_session_service = upload_session_service
        self._upload_processing_service = upload_processing_service

    def register_url_provider(self, scheme: str, provider: URLProvider) -> None:
        """
        Register a service provider for a URL scheme.

        Args:
            scheme: The URL scheme (e.g., "youtube")
            provider: Service that implements URLProvider protocol
        """
        logger.info(f"Registering URL provider for scheme '{scheme}'")
        self._url_providers[scheme] = provider

    def register_metadata_provider(self, scheme: str, provider: URLMetadataProvider) -> None:
        """
        Register a metadata provider for a URL scheme.

        Args:
            scheme: The URL scheme (e.g., "youtube")
            provider: Service that implements URLMetadataProvider protocol
        """
        logger.info(f"Registering metadata provider for scheme '{scheme}'")
        self._metadata_providers[scheme] = provider

    def register_file_only(
        self,
        session_id: str,
        filename: str,
        size_bytes: int,
    ) -> UploadFileStatus | None:
        """
        Register a file without processing.

        Just creates the registration in the session. Actual upload and processing
        will happen later via update_and_process_file.

        Args:
            session_id: Upload session ID
            filename: Name of the file
            size_bytes: Size of the file in bytes

        Returns:
            UploadFileStatus if successful, None otherwise
        """
        try:
            file_status = self._upload_session_service.register_file(
                session_id=session_id,
                filename=filename,
                size_bytes=size_bytes,
            )

            if not file_status:
                logger.error(f"Failed to register file {filename} in session {session_id}")
                return None

            # Mark as uploading_local status
            self._upload_session_service.update_file_progress(
                session_id=session_id,
                file_id=file_status.file_id,
                progress=0.0,
                status=FileUploadStatus.UPLOADING_LOCAL,
            )

            logger.info(
                f"Registered file {filename} in session {session_id}, file_id: {file_status.file_id}"
            )
            return file_status

        except Exception as e:
            logger.error(f"Error registering file {filename}: {e}")
            return None

    async def register_url_only(
        self,
        session_id: str,
        url_with_scheme: str,
    ) -> UploadFileStatus | None:
        """
        Register a URL without immediately processing.

        The URL format is "scheme:path", e.g., "youtube:jNQXAC9IVRw"

        Args:
            session_id: Upload session ID
            url_with_scheme: Full URL with scheme (e.g., "youtube:jNQXAC9IVRw")

        Returns:
            UploadFileStatus if successful, None otherwise
        """
        try:
            # Parse scheme and URL path
            if ":" not in url_with_scheme:
                logger.error(f"Invalid URL format (missing scheme): {url_with_scheme}")
                return None

            scheme, url_path = url_with_scheme.split(":", 1)

            if scheme not in self._url_providers:
                logger.error(f"No provider registered for scheme: {scheme}")
                return None

            # Try to get title from metadata provider if available
            filename = f"{scheme}-{url_path}"
            original_title = None
            if scheme in self._metadata_providers:
                try:
                    metadata_provider = self._metadata_providers[scheme]
                    title = await metadata_provider.get_url_title(url_path)
                    if title:
                        filename = f"{title}.mp3"
                        original_title = title
                        logger.info(f"Fetched title for {scheme}:{url_path} -> {filename}")
                except Exception as e:
                    logger.warning(f"Failed to fetch metadata for {scheme}:{url_path}: {e}")

            # Register file in session
            file_status = self._upload_session_service.register_file(
                session_id=session_id,
                filename=filename,
                size_bytes=0,
                original_title=original_title,
            )

            if not file_status:
                logger.error(f"Failed to register URL {url_with_scheme} in session {session_id}")
                return None

            # Mark as downloading_youtube status
            self._upload_session_service.update_file_progress(
                session_id=session_id,
                file_id=file_status.file_id,
                progress=0.0,
                status=FileUploadStatus.DOWNLOADING_YOUTUBE,
            )

            logger.info(
                f"Registered URL {url_with_scheme} in session {session_id}, file_id: {file_status.file_id}"
            )
            return file_status

        except Exception as e:
            logger.error(f"Error registering URL {url_with_scheme}: {e}")
            return None

    async def update_and_process_file(
        self,
        session_id: str,
        playlist_id: str,
        file_id: str,
        filename: str,
        file_content: bytes,
    ) -> bool:
        """
        Update a registered file with content and start processing.

        This is called after register_file_only when the actual file content is ready.

        Args:
            session_id: Upload session ID
            playlist_id: Playlist ID
            file_id: File ID from registration
            filename: Name of the file
            file_content: File content bytes

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Starting background save for file {filename} (id: {file_id})")

            # Save file using handler
            local_path = await self._file_upload_handler.handle_file_upload(
                session_id=session_id,
                playlist_id=playlist_id,
                filename=filename,
                content=file_content,
            )

            # Verify file exists
            file_path = pathlib.Path(local_path)
            if not file_path.exists():
                raise FileNotFoundError(f"Saved file not found: {local_path}")

            logger.info(f"File saved for {file_id}: {local_path}")

            # Mark file as uploaded (this queues it for processing)
            self._upload_session_service.mark_file_uploaded(
                session_id=session_id,
                file_id=file_id,
                temp_path=local_path,
            )

            # Trigger processing if batch normalization not enabled
            session = self._upload_session_service.get_session(session_id)
            if session and not session.normalize_batch:
                session.files_to_process.append(file_id)
                self._upload_processing_service.process_session_async(
                    session_id=session_id,
                    playlist_id=playlist_id,
                )

            logger.info(f"File {file_id} ({filename}) queued for processing after save")
            return True

        except Exception as e:
            logger.error(f"Error processing file {filename}: {e}")
            # Mark as failed in session
            self._upload_session_service.mark_file_error(
                session_id=session_id,
                file_id=file_id,
                error_message=str(e),
            )
            return False

    async def update_and_process_url(
        self,
        session_id: str,
        playlist_id: str,
        file_id: str,
        url_with_scheme: str,
    ) -> bool:
        """
        Update a registered URL with content (download) and start processing.

        This is called after register_url_only to start the actual download.

        Args:
            session_id: Upload session ID
            playlist_id: Playlist ID
            file_id: File ID from registration
            url_with_scheme: Full URL with scheme (e.g., "youtube:jNQXAC9IVRw")

        Returns:
            True if successful, False otherwise
        """
        try:
            # Parse scheme and URL path
            if ":" not in url_with_scheme:
                logger.error(f"Invalid URL format (missing scheme): {url_with_scheme}")
                return False

            scheme, url_path = url_with_scheme.split(":", 1)

            if scheme not in self._url_providers:
                logger.error(f"No provider registered for scheme: {scheme}")
                return False

            provider = self._url_providers[scheme]

            logger.info(
                f"Starting background download for {scheme}:{url_path} (file_id: {file_id})"
            )

            # Start background task to download and process
            asyncio.create_task(
                self._process_url_in_background(
                    session_id=session_id,
                    playlist_id=playlist_id,
                    file_id=file_id,
                    scheme=scheme,
                    url_path=url_path,
                    provider=provider,
                )
            )

            return True

        except Exception as e:
            logger.error(f"Error updating URL {url_with_scheme}: {e}")
            self._upload_session_service.mark_file_error(
                session_id=session_id,
                file_id=file_id,
                error_message=str(e),
            )
            return False

    async def register_and_process_url(
        self,
        session_id: str,
        playlist_id: str,
        url_with_scheme: str,
    ) -> UploadFileStatus | None:
        """
        Register a URL for download and process it through the upload pipeline.

        The URL format is "scheme:path", e.g., "youtube:jNQXAC9IVRw"

        Args:
            session_id: Upload session ID
            playlist_id: Playlist ID
            url_with_scheme: Full URL with scheme (e.g., "youtube:jNQXAC9IVRw")
            upload_session_service: Service for managing upload sessions
            upload_processing_service: Service for processing uploaded files

        Returns:
            UploadFileStatus if successful, None otherwise
        """
        try:
            # Parse scheme and URL path
            if ":" not in url_with_scheme:
                logger.error(f"Invalid URL format (missing scheme): {url_with_scheme}")
                return None

            scheme, url_path = url_with_scheme.split(":", 1)

            if scheme not in self._url_providers:
                logger.error(f"No provider registered for scheme: {scheme}")
                return None

            provider = self._url_providers[scheme]

            # Try to get title from metadata provider if available
            filename = f"{scheme}-{url_path}"
            original_title = None
            if scheme in self._metadata_providers:
                try:
                    metadata_provider = self._metadata_providers[scheme]
                    title = await metadata_provider.get_url_title(url_path)
                    if title:
                        filename = f"{title}.mp3"
                        original_title = title  # Store the original title
                        logger.info(f"Fetched title for {scheme}:{url_path} -> {filename}")
                except Exception as e:
                    logger.warning(f"Failed to fetch metadata for {scheme}:{url_path}: {e}")

            # Register file in session first
            file_status = self._upload_session_service.register_file(
                session_id=session_id,
                filename=filename,
                size_bytes=0,  # Size unknown until downloaded
                original_title=original_title,  # Pass the original title from metadata
            )

            if not file_status:
                logger.error(f"Failed to register file in session {session_id}")
                return None

            # Start background task to download and process
            asyncio.create_task(
                self._process_url_in_background(
                    session_id=session_id,
                    playlist_id=playlist_id,
                    file_id=file_status.file_id,
                    scheme=scheme,
                    url_path=url_path,
                    provider=provider,
                )
            )

            logger.info(
                f"Registered URL {scheme}:{url_path} in session {session_id}, "
                f"file_id: {file_status.file_id}"
            )

            return file_status

        except Exception as e:
            logger.error(f"Error registering URL {url_with_scheme}: {e}")
            return None

    async def _process_url_in_background(
        self,
        session_id: str,
        playlist_id: str,
        file_id: str,
        scheme: str,
        url_path: str,
        provider: URLProvider,
    ) -> None:
        """
        Background task to download file from URL and mark it as uploaded.

        Args:
            session_id: Upload session ID
            playlist_id: Playlist ID
            file_id: File ID in the session
            scheme: URL scheme
            url_path: URL path/ID
            provider: Service provider for the scheme
            upload_session_service: Service for managing sessions
            upload_processing_service: Service for processing files
        """
        try:
            logger.info(f"Starting background download for {scheme}:{url_path}")

            # Get local path from provider
            local_path = await provider.get_local_path_for_url(url_path)

            # Verify file exists
            file_path = pathlib.Path(local_path)
            if not file_path.exists():
                raise FileNotFoundError(f"Downloaded file not found: {local_path}")

            logger.info(f"Download complete for {file_id}: {local_path}")

            # Mark file as uploaded (this queues it for processing)
            self._upload_session_service.mark_file_uploaded(
                session_id=session_id,
                file_id=file_id,
                temp_path=local_path,
            )

            # Trigger processing if batch normalization not enabled
            session = self._upload_session_service.get_session(session_id)
            if session and not session.normalize_batch:
                session.files_to_process.append(file_id)
                self._upload_processing_service.process_session_async(
                    session_id=session_id,
                    playlist_id=playlist_id,
                )

            logger.info(f"File {file_id} queued for processing after URL download")

        except Exception as e:
            logger.error(f"Error processing URL {scheme}:{url_path}: {e}")
            # Mark as failed in session
            self._upload_session_service.mark_file_error(
                session_id=session_id,
                file_id=file_id,
                error_message=str(e),
            )

    async def register_and_process_file(
        self,
        session_id: str,
        playlist_id: str,
        filename: str,
        file_content: bytes,
    ) -> UploadFileStatus | None:
        """
        Register a file for upload and process it through the pipeline.

        Handles file saving, session registration, and processing queue.

        Args:
            session_id: Upload session ID
            playlist_id: Playlist ID
            filename: Name of the file
            file_content: File content bytes
            upload_session_service: Service for managing upload sessions
            upload_processing_service: Service for processing uploaded files

        Returns:
            UploadFileStatus if successful, None otherwise
        """
        try:
            # Register file in session first
            file_status = self._upload_session_service.register_file(
                session_id=session_id,
                filename=filename,
                size_bytes=len(file_content),
            )

            if not file_status:
                logger.error(f"Failed to register file {filename} in session {session_id}")
                return None

            # Start background task to save and process file
            asyncio.create_task(
                self._process_file_in_background(
                    session_id=session_id,
                    playlist_id=playlist_id,
                    file_id=file_status.file_id,
                    filename=filename,
                    file_content=file_content,
                )
            )

            logger.info(
                f"Registered file {filename} in session {session_id}, file_id: {file_status.file_id}"
            )

            return file_status

        except Exception as e:
            logger.error(f"Error registering file {filename}: {e}")
            return None

    async def _process_file_in_background(
        self,
        session_id: str,
        playlist_id: str,
        file_id: str,
        filename: str,
        file_content: bytes,
    ) -> None:
        """
        Background task to save file and mark it as uploaded.

        Args:
            session_id: Upload session ID
            playlist_id: Playlist ID
            file_id: File ID in the session
            filename: Name of the file
            file_content: File content bytes
            upload_session_service: Service for managing sessions
            upload_processing_service: Service for processing files
        """
        try:
            logger.info(f"Starting background save for file {filename} (id: {file_id})")

            # Save file using handler
            local_path = await self._file_upload_handler.handle_file_upload(
                session_id=session_id,
                playlist_id=playlist_id,
                filename=filename,
                content=file_content,
            )

            # Verify file exists
            file_path = pathlib.Path(local_path)
            if not file_path.exists():
                raise FileNotFoundError(f"Saved file not found: {local_path}")

            logger.info(f"File saved for {file_id}: {local_path}")

            # Mark file as uploaded (this queues it for processing)
            self._upload_session_service.mark_file_uploaded(
                session_id=session_id,
                file_id=file_id,
                temp_path=local_path,
            )

            # Trigger processing if batch normalization not enabled
            session = self._upload_session_service.get_session(session_id)
            if session and not session.normalize_batch:
                session.files_to_process.append(file_id)
                self._upload_processing_service.process_session_async(
                    session_id=session_id,
                    playlist_id=playlist_id,
                )

            logger.info(f"File {file_id} ({filename}) queued for processing after save")

        except Exception as e:
            logger.error(f"Error processing file {filename}: {e}")
            # Mark as failed in session
            self._upload_session_service.mark_file_error(
                session_id=session_id,
                file_id=file_id,
                error_message=str(e),
            )
