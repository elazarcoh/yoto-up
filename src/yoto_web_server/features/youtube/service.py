"""Service for YouTube metadata handling using yt-dlp."""

import asyncio
import json
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import ClassVar, Literal

from loguru import logger

from yoto_web_server.optional_feature_base import (
    OptionalFeatureBase,
    OptionalFeatureVerification,
)


@dataclass
class YouTubeMetadata:
    """Metadata for a YouTube video."""

    video_id: str
    title: str
    duration_seconds: int
    uploader: str
    upload_date: str
    description: str
    thumbnail_url: str


@dataclass
class MetadataTask:
    """A task to fetch metadata for a YouTube URL."""

    task_id: str
    youtube_url: str
    status: Literal["pending", "processing", "complete", "error", "cancelled"] = "pending"
    metadata: YouTubeMetadata | None = None
    error: str | None = None


class YouTubeMetadataService:
    """Service for fetching and processing YouTube metadata using yt-dlp.

    Includes in-memory caching with TTL to avoid redundant metadata fetches.
    """

    # Metadata cache: {video_id: (metadata, timestamp)}
    # TTL is 1 hour (3600 seconds)
    _metadata_cache: ClassVar[dict[str, tuple[YouTubeMetadata, float]]] = {}
    _cache_ttl: ClassVar[int] = 3600  # 1 hour in seconds
    _cache_lock: ClassVar[threading.Lock] = threading.Lock()

    async def get_metadata(self, youtube_url: str) -> YouTubeMetadata | None:
        """Fetch metadata for a YouTube URL using yt-dlp with caching.

        Caches results in-memory for 1 hour to avoid redundant metadata fetches
        during the same session.

        Args:
            youtube_url: YouTube URL or video ID.

        Returns:
            YouTubeMetadata if available, None otherwise.
        """
        logger.info(f"Fetching metadata for: {youtube_url}")

        # Extract video ID from URL or use as-is
        video_id = self._extract_video_id(youtube_url)
        if not video_id:
            logger.warning(f"Could not extract video ID from: {youtube_url}")
            return None

        # Check cache first (thread-safe with lock)
        with self._cache_lock:
            if video_id in self._metadata_cache:
                metadata, timestamp = self._metadata_cache[video_id]
                age = time.time() - timestamp
                if age < self._cache_ttl:
                    logger.info(f"Cache hit for: {video_id} (age: {age:.1f}s)")
                    return metadata
                else:
                    logger.info(f"Cache expired for: {video_id} (age: {age:.1f}s)")
                    del self._metadata_cache[video_id]

        # Fetch real metadata using yt-dlp
        try:
            # Run yt-dlp in async context
            loop = asyncio.get_event_loop()
            metadata = await loop.run_in_executor(
                None,
                self._fetch_metadata_with_yt_dlp,
                youtube_url,
            )
            if metadata:
                logger.info(f"Fetched real metadata for: {video_id}")
                # Cache the result
                with self._cache_lock:
                    self._metadata_cache[video_id] = (metadata, time.time())
                return metadata
            else:
                logger.warning(f"Failed to fetch metadata for: {video_id}")
                return None
        except Exception as e:
            logger.error(f"Failed to fetch metadata with yt-dlp for {video_id}: {e}")
            return None

    @staticmethod
    def _extract_video_id(youtube_url: str) -> str | None:
        """Extract video ID from various YouTube URL formats.

        Supports:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - VIDEO_ID (raw ID)
        """
        # Remove whitespace
        youtube_url = youtube_url.strip()

        # If it looks like a raw video ID (11 chars, alphanumeric with - and _)
        if len(youtube_url) == 11 and all(c.isalnum() or c in "-_" for c in youtube_url):
            return youtube_url

        # Parse standard URLs
        if "youtube.com/watch" in youtube_url:
            try:
                # Extract v parameter
                parts = youtube_url.split("v=")
                if len(parts) > 1:
                    video_id = parts[1].split("&")[0]
                    return video_id if video_id else None
            except Exception:
                pass

        if "youtu.be/" in youtube_url:
            try:
                # Extract from short URL
                video_id = youtube_url.split("youtu.be/")[1].split("?")[0]
                return video_id if video_id else None
            except Exception:
                pass

        return None

    async def download_audio(self, video_id: str, output_dir: Path) -> Path | None:
        """Download audio for a YouTube video using yt-dlp.

        Args:
            video_id: YouTube URL or video ID
            output_dir: Directory to save the audio file

        Returns:
            Path to the downloaded audio file, or None if failed
        """
        logger.info(f"Downloading audio for: {video_id}")

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Run yt-dlp in async context
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._download_audio_with_yt_dlp,
                video_id,
                str(output_dir),
            )
            if result:
                logger.info(f"Downloaded audio to: {result}")
                return Path(result)
        except Exception as e:
            logger.error(f"Failed to download audio with yt-dlp: {e}")

        logger.warning(f"Could not download audio for: {video_id}")
        return None

    @staticmethod
    def _fetch_metadata_with_yt_dlp(youtube_url: str) -> YouTubeMetadata | None:
        """Fetch metadata from YouTube using yt-dlp.

        Args:
            youtube_url: YouTube URL or video ID

        Returns:
            YouTubeMetadata object with fetched data, or None if failed
        """
        try:
            # Try using yt-dlp library first
            try:
                import yt_dlp
            except ImportError:
                logger.warning("yt-dlp library not available, trying command-line tool")
                return YouTubeMetadataService._fetch_metadata_with_yt_dlp_cli(youtube_url)

            # Use yt-dlp to extract metadata
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)

                return YouTubeMetadata(
                    video_id=info.get("id", "unknown"),
                    title=info.get("title", "Unknown Title"),
                    duration_seconds=info.get("duration", 0),
                    uploader=info.get("uploader", "Unknown"),
                    upload_date=info.get("upload_date", "1970-01-01"),
                    description=info.get("description", ""),
                    thumbnail_url=info.get("thumbnail", ""),
                )

        except Exception as e:
            logger.warning(f"Failed to fetch metadata with yt-dlp library: {e}")
            return None

    @staticmethod
    def _fetch_metadata_with_yt_dlp_cli(youtube_url: str) -> YouTubeMetadata | None:
        """Fetch metadata from YouTube using yt-dlp CLI tool.

        Args:
            youtube_url: YouTube URL or video ID

        Returns:
            YouTubeMetadata object with fetched data, or None if failed
        """
        try:
            # Use yt-dlp command-line tool
            cmd = [
                "yt-dlp",
                "--dump-json",
                "--no-warnings",
                "--quiet",
                youtube_url,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                logger.warning(f"yt-dlp CLI returned error: {result.stderr}")
                return None

            # Parse JSON output
            info = json.loads(result.stdout)

            return YouTubeMetadata(
                video_id=info.get("id", "unknown"),
                title=info.get("title", "Unknown Title"),
                duration_seconds=info.get("duration", 0),
                uploader=info.get("uploader", "Unknown"),
                upload_date=info.get("upload_date", "1970-01-01"),
                description=info.get("description", ""),
                thumbnail_url=info.get("thumbnail", ""),
            )

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse yt-dlp JSON output: {e}")
            return None
        except subprocess.TimeoutExpired:
            logger.warning("yt-dlp CLI timed out")
            return None
        except FileNotFoundError:
            logger.warning("yt-dlp CLI tool not found in PATH")
            return None
        except Exception as e:
            logger.warning(f"Failed to fetch metadata with yt-dlp CLI: {e}")
            return None

    @staticmethod
    def _download_audio_with_yt_dlp(
        youtube_url: str,
        output_dir: str,
    ) -> str | None:
        """Download audio from YouTube using yt-dlp.

        Args:
            youtube_url: YouTube URL or video ID
            output_dir: Directory to save the audio file

        Returns:
            Path to the downloaded audio file, or None if failed
        """
        try:
            # Try using yt-dlp library first
            try:
                import yt_dlp
            except ImportError:
                logger.warning("yt-dlp library not available, trying command-line tool")
                return YouTubeMetadataService._download_audio_with_yt_dlp_cli(
                    youtube_url,
                    output_dir,
                )

            output_template = str(Path(output_dir) / "%(title)s.%(ext)s")

            ydl_opts = {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
                "outtmpl": output_template,
                "quiet": True,
                "no_warnings": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=True)
                filename = ydl.prepare_filename(info)
                # Replace extension with .mp3
                audio_file = Path(filename).with_suffix(".mp3")

                if audio_file.exists():
                    logger.info(f"Successfully downloaded audio to: {audio_file}")
                    return str(audio_file)
                else:
                    logger.warning(f"Audio file not found after download: {audio_file}")
                    return None

        except Exception as e:
            logger.warning(f"Failed to download with yt-dlp library: {e}")
            return None

    @staticmethod
    def _download_audio_with_yt_dlp_cli(
        youtube_url: str,
        output_dir: str,
    ) -> str | None:
        """Download audio from YouTube using yt-dlp CLI tool.

        Args:
            youtube_url: YouTube URL or video ID
            output_dir: Directory to save the audio file

        Returns:
            Path to the downloaded audio file, or None if failed
        """
        try:
            output_template = str(Path(output_dir) / "%(title)s.%(ext)s")

            cmd = [
                "yt-dlp",
                "-f",
                "bestaudio/best",
                "-x",
                "--audio-format",
                "mp3",
                "--audio-quality",
                "192",
                "-o",
                output_template,
                "--no-warnings",
                "--quiet",
                youtube_url,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes for download
            )

            if result.returncode != 0:
                logger.warning(f"yt-dlp CLI download failed: {result.stderr}")
                return None

            # Find the downloaded file
            output_path = Path(output_dir)
            mp3_files = list(output_path.glob("*.mp3"))

            if mp3_files:
                latest_file = max(mp3_files, key=lambda p: p.stat().st_mtime)
                logger.info(f"Successfully downloaded audio to: {latest_file}")
                return str(latest_file)
            else:
                logger.warning(f"No MP3 files found in {output_dir}")
                return None

        except subprocess.TimeoutExpired:
            logger.warning("yt-dlp CLI download timed out")
            return None
        except FileNotFoundError:
            logger.warning("yt-dlp CLI tool not found in PATH")
            return None
        except Exception as e:
            logger.warning(f"Failed to download with yt-dlp CLI: {e}")
            return None

    def format_duration(self, seconds: int) -> str:
        """Format duration in seconds to HH:MM:SS."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"


class YouTubeWorkerService:
    """Background worker service for fetching YouTube metadata."""

    def __init__(self) -> None:
        """Initialize the worker service."""
        self.tasks: dict[str, MetadataTask] = {}
        self._lock = threading.Lock()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info("YouTube worker service initialized")

    def queue_metadata_fetch(self, youtube_url: str) -> str:
        """Queue a metadata fetch task.

        Args:
            youtube_url: YouTube URL or video ID to fetch metadata for

        Returns:
            Task ID that can be used to poll for results
        """
        task_id = str(uuid.uuid4())
        task = MetadataTask(
            task_id=task_id,
            youtube_url=youtube_url,
            status="pending",
        )

        with self._lock:
            self.tasks[task_id] = task

        logger.info(f"Queued metadata fetch task {task_id} for {youtube_url}")
        return task_id

    def get_task_status(self, task_id: str) -> MetadataTask | None:
        """Get the status of a metadata fetch task.

        Args:
            task_id: The task ID to check

        Returns:
            MetadataTask with current status, or None if not found
        """
        with self._lock:
            return self.tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending metadata fetch task.

        Args:
            task_id: The task ID to cancel

        Returns:
            True if task was cancelled, False if not found or already complete
        """
        with self._lock:
            task = self.tasks.get(task_id)
            if task and task.status == "pending":
                task.status = "cancelled"
                logger.info(f"Cancelled task {task_id}")
                return True
            elif task and task.status == "processing":
                # Can't cancel processing tasks, but mark for cleanup
                logger.warning(f"Cannot cancel processing task {task_id}")
                return False
            return False

    def _worker_loop(self) -> None:
        """Main worker loop that processes metadata fetch tasks."""
        logger.info("YouTube worker thread started")
        service = YouTubeMetadataService()

        while True:
            try:
                # Find next pending task
                pending_task = None
                with self._lock:
                    for task in self.tasks.values():
                        if task.status == "pending":
                            pending_task = task
                            break

                if pending_task:
                    # Process the task
                    with self._lock:
                        pending_task.status = "processing"
                    logger.info(f"Processing metadata task {pending_task.task_id}")

                    try:
                        # Run async metadata fetch synchronously
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        metadata = loop.run_until_complete(
                            service.get_metadata(pending_task.youtube_url)
                        )
                        loop.close()

                        with self._lock:
                            pending_task.metadata = metadata
                            pending_task.status = "complete"
                            logger.info(
                                f"Completed metadata task {pending_task.task_id}: "
                                f"{metadata.title if metadata else 'not found'}"
                            )
                    except Exception as e:
                        with self._lock:
                            pending_task.error = str(e)
                            pending_task.status = "error"
                            logger.error(f"Error processing task {pending_task.task_id}: {e}")
                else:
                    # No pending tasks, sleep briefly
                    threading.Event().wait(0.1)

            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                threading.Event().wait(1)  # Backoff on error


class YouTubeService:
    def __init__(self) -> None:
        self.metadata_service = YouTubeMetadataService()
        self.worker_service = YouTubeWorkerService()


class YouTubeFeature(OptionalFeatureBase):
    """Feature for uploading audio from YouTube URLs.

    This feature requires either yt-dlp or youtube-dl to be installed.
    """

    identifier: ClassVar[str] = "youtube_upload"

    def __init__(self, enabled: bool = True) -> None:
        """Initialize YouTube feature.

        Args:
            enabled: Whether to enable this feature (for testing).
        """
        self._enabled = enabled
        self._download_method: str | None = None
        self._version: str | None = None

        self._services = YouTubeService()

    def verify(self) -> OptionalFeatureVerification:
        """Verify if YouTube download tool is available.

        Checks for yt-dlp or youtube-dl executables in PATH.

        Returns:
            OptionalFeatureVerification: Valid if a downloader is found.
        """
        if not self._enabled:
            return OptionalFeatureVerification(
                valid=False,
                invalid_reasons=["Feature disabled for testing"],
            )

        # Try yt-dlp first (preferred)
        self._download_method, self._version = self._check_yt_dlp()
        if self._download_method:
            return OptionalFeatureVerification(valid=True)

        # Fall back to youtube-dl
        self._download_method, self._version = self._check_youtube_dl()
        if self._download_method:
            return OptionalFeatureVerification(valid=True)

        return OptionalFeatureVerification(
            valid=False,
            invalid_reasons=[
                "Neither yt-dlp nor youtube-dl found in PATH",
                "Install with: uv sync --group youtube (yt-dlp) or pip install youtube-dl",
            ],
        )

    def get_download_method(self) -> str | None:
        """Get the detected download method."""
        return self._download_method

    def get_version(self) -> str | None:
        """Get the version of the download tool."""
        return self._version

    @staticmethod
    def _check_yt_dlp() -> tuple[str | None, str | None]:
        """Check if yt-dlp is available and get version."""
        yt_dlp_path = shutil.which("yt-dlp")
        if not yt_dlp_path:
            # Try to import yt_dlp directly (works with uv)
            try:
                import yt_dlp.version

                return "yt-dlp", yt_dlp.version.__version__
            except ImportError:
                return None, None

        try:
            result = subprocess.run(
                ["yt-dlp", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                return "yt-dlp", version
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return None, None

    @staticmethod
    def _check_youtube_dl() -> tuple[str | None, str | None]:
        """Check if youtube-dl is available and get version."""
        youtube_dl_path = shutil.which("youtube-dl")
        if not youtube_dl_path:
            return None, None

        try:
            result = subprocess.run(
                ["youtube-dl", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                return "youtube-dl", version
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return None, None

    @property
    def metadata_service(self) -> YouTubeMetadataService:
        """Get the YouTube metadata service."""
        return self._services.metadata_service

    @property
    def worker_service(self) -> YouTubeWorkerService:
        """Get the YouTube worker service."""
        return self._services.worker_service

    async def get_local_path_for_url(self, url_path: str) -> str:
        """
        Implement URLProvider protocol for unified upload orchestrator.

        Downloads audio for the given YouTube URL/ID and returns local path.

        Args:
            url_path: YouTube URL or video ID

        Returns:
            Local file path to the downloaded audio

        Raises:
            FileNotFoundError: If download fails or file cannot be accessed
        """
        # Create temp directory for this download
        output_dir = Path(tempfile.gettempdir()) / "yoto_youtube_downloads"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Download the audio
        result_path = await self.metadata_service.download_audio(url_path, output_dir)
        if not result_path:
            raise FileNotFoundError(f"Failed to download audio for YouTube URL: {url_path}")

        return str(result_path)

    async def get_url_title(self, url_path: str) -> str | None:
        """
        Implement URLMetadataProvider protocol to get YouTube video title.

        Args:
            url_path: YouTube URL or video ID

        Returns:
            Video title, or None if not found
        """
        try:
            metadata = await self.metadata_service.get_metadata(url_path)
            if metadata:
                return metadata.title
            return None
        except Exception as e:
            logger.warning(f"Failed to get YouTube title for {url_path}: {e}")
            return None
