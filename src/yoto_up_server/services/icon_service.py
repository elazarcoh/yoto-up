"""
Icon Service.

Handles icon browsing, searching, and management.
Fetches public icons from Yoto API manifest and downloads them on demand.
"""

from __future__ import annotations

from asyncio import Future, Lock
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import httpx
from loguru import logger
from pydantic import BaseModel

from yoto_up import paths
from yoto_up.yoto_api_client import YotoApiClient


if TYPE_CHECKING:
    from yoto_up_server.models import DisplayIcon, DisplayIconManifest
    from yoto_up_server.services.session_aware_api_service import SessionAwareApiService


class IconEntry(BaseModel):
    id: str
    path: str
    source: str
    name: str
    data: bytes
    tags: List[str] = []
    keywords: List[str] = []


class IconIndex:
    def __init__(self) -> None:
        self._items: Dict[str, IconEntry] = {}

    @property
    def built(self) -> bool:
        return bool(self._items)

    def clear(self) -> None:
        self._items = {}

    def add_entry(self, entry: IconEntry) -> None:
        self._items[entry.id] = entry

    def add_from_path(self, path: Path, source: str) -> None:
        with path.open("r") as f:
            entry = IconEntry.model_validate_json(f.read(), extra="ignore")
        self.add_entry(entry)

    def build_from_dir(self, directory: Path, source: str) -> None:
        if not directory.exists():
            return
        for path in directory.glob("*.json"):
            self.add_from_path(path, source)

    def get(self, icon_id: str) -> Optional[IconEntry]:
        entry = self._items.get(icon_id)
        return entry

    def all_entries(self) -> List[IconEntry]:
        return list(self._items.values())


class IconIndices:
    def __init__(self) -> None:
        self.official = IconIndex()
        self.yotoicons = IconIndex()
        self.local = IconIndex()

    @property
    def built(self) -> bool:
        return self.official.built or self.yotoicons.built or self.local.built

    def build_all(
        self, official_dir: Path, yotoicons_dir: Path, local_dir: Path
    ) -> None:
        self.official.clear()
        self.yotoicons.clear()
        self.local.clear()
        self.official.build_from_dir(official_dir, "official")
        self.yotoicons.build_from_dir(yotoicons_dir, "yotoicons")
        self.local.build_from_dir(local_dir, "local")

    def clear(self) -> None:
        self.official.clear()
        self.yotoicons.clear()
        self.local.clear()

    def all_entries(self) -> List[IconEntry]:
        return (
            self.official.all_entries()
            + self.yotoicons.all_entries()
            + self.local.all_entries()
        )

    def get(self, icon_id: str) -> Optional[IconEntry]:
        for idx in (self.local, self.official, self.yotoicons):
            v = idx.get(icon_id)
            if v:
                return v
        return None


class IconService:
    """
    Service for icon management.

    - Lazily fetches public icon manifest from authenticated API on first request
    - Provides icon searching and retrieval by media ID
    - Downloads icons on demand (no caching for now, see TODO below)
    - Manages local icon caching for CLI/TUI usage
    """

    def __init__(self) -> None:
        self._cache_dir = paths.OFFICIAL_ICON_CACHE_DIR
        self._yotoicons_dir = paths.YOTOICONS_CACHE_DIR
        self._user_icons_dir = paths.USER_ICONS_DIR

        # Ensure directories exist
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._yotoicons_dir.mkdir(parents=True, exist_ok=True)
        self._user_icons_dir.mkdir(parents=True, exist_ok=True)

        # In-memory indices (official, yotoicons, local)
        self._indices = IconIndices()

        # In-memory manifest of public icons
        self._public_manifest: Optional[DisplayIconManifest] = None
        self._public_manifest_by_media_id: Dict[str, DisplayIcon] = {}
        # In-memory manifest of user icons
        self._user_manifest: Optional[DisplayIconManifest] = None
        self._user_manifest_by_media_id: Dict[str, DisplayIcon] = {}

        # In-memory tracking of ongoing download requests
        self._running_requests: Dict[str, Future] = {}
        self._running_requests_lock = Lock()

        # In-memory cache for downloaded icons (bytes)
        self._icon_bytes_cache: Dict[str, bytes] = {}

    async def initialize(self) -> None:
        """Initialize the service (public manifest will be fetched on demand with auth)."""
        # Don't fetch public manifest here - it requires authentication
        # Will be lazily loaded when first accessed
        from yoto_up_server.models import DisplayIconManifest

        self._public_manifest = DisplayIconManifest(displayIcons=[])
        self._public_manifest_by_media_id = {}

        # Always build indices
        self._build_indices()

        logger.info(
            f"IconService initialized: public icons will be fetched on demand (requires auth), "
            f"{len(self._indices.all_entries())} local icons"
        )

    async def _ensure_public_icons_manifest(self, api_client: YotoApiClient) -> bool:
        """Ensure public manifest is loaded (fetches from authenticated API if needed).

        Args:
            api_client: YotoApiClient instance for authenticated requests

        Returns:
            True if manifest was loaded successfully, False otherwise
        """
        # Check if already loaded
        if self._public_manifest_by_media_id:
            return True

        # Fetch using authenticated API
        try:
            logger.info("Fetching public icons manifest from authenticated API")

            # Fetch public icons - returns a list of DisplayIcon objects
            icons = await api_client.get_public_icons()

            self._public_manifest = icons

            self._public_manifest_by_media_id = {
                icon.mediaId: icon for icon in self._public_manifest.displayIcons
            }

            logger.info(
                f"Loaded public manifest: {len(self._public_manifest.displayIcons)} icons"
            )
            return True

        except Exception as e:
            logger.error(f"Error fetching public manifest from API: {e}")
            return False

    async def _ensure_user_icon_manifest(self, api_client: YotoApiClient) -> bool:
        """Ensure public manifest is loaded (fetches from authenticated API if needed).

        Args:
            api_client: YotoApiClient instance for authenticated requests

        Returns:
            True if manifest was loaded successfully, False otherwise
        """
        # Check if already loaded
        if self._user_manifest_by_media_id:
            return True

        # Fetch using authenticated API
        try:
            logger.info("Fetching user icons manifest from authenticated API")

            # Fetch user icons - returns a list of DisplayIcon objects
            icons = await api_client.get_user_icons()

            self._user_manifest = icons

            self._user_manifest_by_media_id = {
                icon.mediaId: icon for icon in self._user_manifest.displayIcons
            }

            logger.info(
                f"Loaded user manifest: {len(self._user_manifest.displayIcons)} icons"
            )
            return True

        except Exception as e:
            logger.error(f"Error fetching user manifest from API: {e}")
            return False

    def _build_indices(self) -> None:
        """Build the in-memory icon indices from cache directories."""
        if self._indices.built:
            return

        self._indices.build_all(
            self._cache_dir, self._yotoicons_dir, self._user_icons_dir
        )

        logger.info(f"Local icon index built: {len(self._indices.all_entries())} icons")

    async def get_icon_by_media_id(
        self,
        media_id: str,
        api_client: YotoApiClient,
    ) -> Optional[bytes]:
        """
        Get icon bytes by media ID from the public manifest.

        Lazily fetches the public manifest on first call using authenticated API.
        Downloads the icon from the manifest URL on demand.

        Args:
            media_id: The media ID from DisplayIcon.mediaId
            api_client: YotoApiClient instance (required for first manifest fetch)

        Returns:
            Icon image bytes, or None if not found
        """
        if media_id.startswith("yoto:#"):
            media_id = media_id.removeprefix("yoto:#")
        # Check if we have it cached in memory
        if media_id in self._icon_bytes_cache:
            logger.debug(f"Icon {media_id} found in memory cache")
            return self._icon_bytes_cache[media_id]

        # Ensure manifests are loaded (lazy fetch on first call)
        await self._ensure_public_icons_manifest(api_client)
        await self._ensure_user_icon_manifest(api_client)

        # Check if it's in the public manifest
        for manifest in (
            self._user_manifest_by_media_id,
            self._public_manifest_by_media_id,
        ):
            if media_id in manifest:
                break
        else:
            logger.warning(f"Icon {media_id} not found in any manifest")
            return None

        icon = manifest[media_id]

        async with self._running_requests_lock:
            if icon.url in self._running_requests:
                # Another request is already in progress for this icon
                logger.debug(f"Waiting for ongoing download of icon {media_id}")
                future = self._running_requests[icon.url]
                await future
                return self._icon_bytes_cache.get(media_id)
            else:
                self._running_requests[icon.url] = Future()

        # Download the icon from the URL
        try:
            logger.debug(f"Downloading icon {media_id} from {icon.url}")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(icon.url)
                response.raise_for_status()
                icon_bytes = response.content
            self._icon_bytes_cache[media_id] = icon_bytes
            self._running_requests[icon.url].set_result(True)
            del self._running_requests[icon.url]

            # TODO: Cache to disk using icon.mediaId as filename
            # TODO: Implement cache expiration/management strategy

            logger.info(f"Downloaded icon {media_id}: {len(icon_bytes)} bytes")
            return icon_bytes

        except Exception as e:
            logger.error(f"Error downloading icon {media_id}: {e}")
            return None
