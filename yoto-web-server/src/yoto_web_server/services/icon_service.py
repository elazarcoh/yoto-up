"""
Icon Service.

Handles icon browsing, searching, and management.
Fetches public icons from Yoto API manifest and downloads them on demand.
"""

from __future__ import annotations

import base64
import json
import re
import time
from asyncio import Future, Lock
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from loguru import logger
from pydantic import (
    BaseModel,
)
from selectolax.lexbor import LexborHTMLParser

from yoto_web_server.api.client import YotoApiClient
from yoto_web_server.core.config import get_settings
from yoto_web_server.services.icon_search_service import IconSearchService, SearchSource
from yoto_web_server.utils.sanitation import sanitize_filename

if TYPE_CHECKING:
    from yoto_web_server.api.models import DisplayIcon, DisplayIconManifest


def icon_bytes_to_data_url(value: bytes) -> str:
    if value.startswith(b"\x89PNG"):
        mime_type = "image/png"
    elif value.startswith(b"\xff\xd8\xff"):
        mime_type = "image/jpeg"
    elif value.startswith(b"GIF"):
        mime_type = "image/gif"
    elif value.startswith(b"WEBP"):
        mime_type = "image/webp"
    else:
        mime_type = "image/png"  # default
    base64_data = base64.b64encode(value).decode("utf-8")
    src = f"data:{mime_type};base64,{base64_data}"
    return src


class IconRetrieveSource(str, Enum):
    OFFICIAL = "official"
    USER = "user"
    ONLINE_YOTOICONS = "yotoicons"
    CACHED_YOTOICONS = "yotoicons_cache"
    CACHED = "cached"  # any cached icons
    ONLINE = "online"  # any online source


ALL_ONLINE_SOURCES = [
    IconRetrieveSource.ONLINE_YOTOICONS,
]
ALL_CACHED_SOURCES = [
    IconRetrieveSource.CACHED_YOTOICONS,
    IconRetrieveSource.OFFICIAL,
]


class YotoIconsSearchResult(BaseModel):
    id: str
    category: str
    tags: list[str]
    author: str
    downloads: int
    img_url: str


class YotoIconsSearcher:
    BASE_URL = "https://www.yotoicons.com"
    SEARCH_URL = f"{BASE_URL}/icons"

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        self.client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)

    async def close(self):
        await self.client.aclose()

    def _get_cache_path(self, tag: str, page: int) -> Path:
        # Create a safe filename for the tag
        safe_tag = "".join([c for c in tag if c.isalnum() or c in (" ", "_")]).rstrip()
        return self.cache_dir / f"search_{safe_tag}_p{page}.json"

    async def fetch_page_data(
        self, tag: str, page: int = 1, use_cache: bool = True
    ) -> list[YotoIconsSearchResult]:
        if use_cache:
            cache_path = self._get_cache_path(tag, page)
            if cache_path.exists():
                # 1-day cache
                if time.time() - cache_path.stat().st_mtime < 86400:
                    try:
                        return [
                            YotoIconsSearchResult(**icon_dict)
                            for icon_dict in json.loads(cache_path.read_text())
                        ]
                    except Exception:
                        pass

        params = {"tag": tag, "page": page, "sort": "popular", "type": "singles"}

        try:
            resp = await self.client.get(self.SEARCH_URL, params=params)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Error fetching page {page} for '{tag}': {e}")
            return []

        # Use selectolax for fast parsing
        parser = LexborHTMLParser(resp.text)
        icons: list[YotoIconsSearchResult] = []

        # The data is in the 'onclick' attribute of 'div.icon'
        for node in parser.css("div.icon"):
            onclick = node.attributes.get("onclick", "")
            if not onclick:
                continue

            # Pattern: populate_icon_modal('id', 'category', 'tag1', 'tag2', 'author', 'downloads')
            match = re.search(
                r"populate_icon_modal\('(\d+)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'(\d+)'\)",
                onclick,
            )
            if match:
                icon_id, category, tag1, tag2, author, downloads = match.groups()
                icons.append(
                    YotoIconsSearchResult(
                        id=icon_id,
                        category=category,
                        tags=[tag1, tag2],
                        author=author,
                        downloads=int(downloads),
                        img_url=f"{self.BASE_URL}/static/uploads/{icon_id}.png",
                    )
                )

        if use_cache and icons:
            # Serialize Pydantic models to JSON
            cache_data = [icon.model_dump(mode="json") for icon in icons]
            self._get_cache_path(tag, page).write_text(json.dumps(cache_data))

        return icons

    async def search(self, query: str, max_pages: int = 5) -> list[YotoIconsSearchResult]:
        """Search for icons using multiple pages in parallel."""
        import asyncio

        tasks = [self.fetch_page_data(query, page) for page in range(1, max_pages + 1)]
        results = await asyncio.gather(*tasks)

        all_icons: list[YotoIconsSearchResult] = []
        seen_ids = set()
        for page_icons in results:
            for icon in page_icons:
                if icon.id not in seen_ids:
                    all_icons.append(icon)
                    seen_ids.add(icon.id)

        # Sort by downloads as a proxy for quality/popularity
        all_icons.sort(key=lambda x: x.downloads, reverse=True)

        return all_icons


class IconEntry(BaseModel):
    id: str
    path: str
    source: str
    name: str
    data: str
    tags: list[str] = []
    keywords: list[str] = []


class IconIndex:
    def __init__(self) -> None:
        self._items: dict[str, IconEntry] = {}

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

    def get(self, icon_id: str) -> IconEntry | None:
        entry = self._items.get(icon_id)
        return entry

    def all_entries(self) -> list[IconEntry]:
        return list(self._items.values())


class IconIndices:
    def __init__(self) -> None:
        self.official = IconIndex()
        self.yotoicons = IconIndex()

    @property
    def built(self) -> bool:
        return self.official.built or self.yotoicons.built

    def build_all(self, official_dir: Path, yotoicons_dir: Path) -> None:
        self.official.clear()
        self.yotoicons.clear()
        self.official.build_from_dir(official_dir, "official")
        self.yotoicons.build_from_dir(yotoicons_dir, "yotoicons")

    def clear(self) -> None:
        self.official.clear()
        self.yotoicons.clear()

    def all_entries(self) -> list[IconEntry]:
        return self.official.all_entries() + self.yotoicons.all_entries()

    def get(self, icon_id: str) -> IconEntry | None:
        for idx in (self.official, self.yotoicons):
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
        settings = get_settings()
        self._yoto_cache_dir = settings.cache_dir / "icons" / "official"
        self._yotoicons_dir = settings.cache_dir / "icons" / "yotoicons"
        self._yotoicons_search_cache_dir = self._yotoicons_dir / "search_cache"
        self._provisioning_map_file = self._yotoicons_dir / "provisioning_map.json"

        # Ensure directories exist
        self._yoto_cache_dir.mkdir(parents=True, exist_ok=True)
        self._yotoicons_dir.mkdir(parents=True, exist_ok=True)
        self._yotoicons_search_cache_dir.mkdir(parents=True, exist_ok=True)

        # In-memory indices (official, yotoicons, local)
        self._indices = IconIndices()

        # In-memory manifest of public icons
        self._public_manifest: DisplayIconManifest | None = None
        self._public_manifest_by_media_id: dict[str, DisplayIcon] = {}
        # In-memory manifest of user icons
        self._user_manifest: DisplayIconManifest | None = None
        self._user_manifest_by_media_id: dict[str, DisplayIcon] = {}

        # In-memory tracking of ongoing download requests
        self._running_requests: dict[str, Future] = {}
        self._running_requests_lock = Lock()

        # In-memory cache for downloaded/loaded icons (bytes)
        self._icon_cache: dict[str, str] = {}

        # YotoIcons caching and provisioning mapping
        self._yotoicons_to_official_mapping: dict[str, str] = {}

        # Search service (initialized after manifests are loaded)
        self._search_service: IconSearchService | None = None

    async def initialize(self) -> None:
        """Initialize the service (public manifest will be fetched on demand with auth)."""
        # Don't fetch public manifest here - it requires authentication
        # Will be lazily loaded when first accessed
        from yoto_web_server.api.models import DisplayIconManifest

        self._public_manifest = DisplayIconManifest(displayIcons=[])
        self._public_manifest_by_media_id = {}

        # Load provisioning map
        if self._provisioning_map_file.exists():
            try:
                self._yotoicons_to_official_mapping = json.loads(
                    self._provisioning_map_file.read_text()
                )
            except Exception as e:
                logger.error(f"Failed to load provisioning map: {e}")

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

            logger.info(f"Loaded public manifest: {len(self._public_manifest.displayIcons)} icons")
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

            logger.info(f"Loaded user manifest: {len(self._user_manifest.displayIcons)} icons")
            return True

        except Exception as e:
            logger.error(f"Error fetching user manifest from API: {e}")
            return False

    def _build_indices(self) -> None:
        """Build the in-memory icon indices from cache directories."""
        if self._indices.built:
            return

        self._indices.build_all(self._yoto_cache_dir, self._yotoicons_dir)

        logger.info(f"Local icon index built: {len(self._indices.all_entries())} icons")

    # ========== Cache Helper Methods ==========

    def _get_from_memory_cache(self, media_id: str) -> str | None:
        """Check if icon exists in memory cache."""
        if media_id in self._icon_cache:
            logger.debug(f"Icon {media_id} found in memory cache")
            return self._icon_cache[media_id]
        return None

    def _get_from_disk_cache(self, media_id: str) -> str | None:
        """Check if icon exists in disk indices and load into memory."""
        entry = self._indices.get(media_id)
        if entry:
            logger.debug(f"Icon {media_id} found in disk cache")
            self._icon_cache[media_id] = entry.data
            return entry.data
        return None

    def _normalize_media_id(self, media_id: str) -> str:
        """Strip yoto:# prefix if present."""
        if media_id.startswith("yoto:#"):
            return media_id.removeprefix("yoto:#")
        return media_id

    async def _download_icon_bytes(self, url: str) -> bytes:
        """Download icon bytes from URL."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    def _cache_icon_data(
        self,
        media_id: str,
        icon_bytes: bytes,
        icon_def: DisplayIcon,
        target_dir: Path,
        source: str,
    ) -> str:
        """Convert icon bytes to data URL, cache in memory and disk."""
        data_url = icon_bytes_to_data_url(icon_bytes)
        self._icon_cache[media_id] = data_url
        self._save_icon_to_disk(media_id, data_url, icon_def, target_dir, source)
        logger.info(f"Cached icon {media_id}: {len(icon_bytes)} bytes")
        return data_url

    # ========== Icon Type-Specific Methods ==========

    async def _get_yotoicons_icon(self, media_id: str) -> str | None:
        """
        Retrieve a YotoIcons icon (yotoicons:*).

        Flow: Memory cache → Disk cache → Search service cache → Download from yotoicons.com
        """
        # Check memory cache
        cached = self._get_from_memory_cache(media_id)
        if cached:
            return cached

        # Check disk cache
        cached = self._get_from_disk_cache(media_id)
        if cached:
            return cached

        # Try to get from search service cache (which has the URL)
        self._initialize_search_service()
        if not self._search_service or media_id not in self._search_service._yotoicons_cache:
            logger.warning(f"YotoIcon {media_id} not found in cache or search service")
            return None

        icon_def = self._search_service._yotoicons_cache[media_id]
        logger.debug(f"Found YotoIcon {media_id} in search cache, downloading from {icon_def.url}")

        # Download from yotoicons.com
        try:
            icon_bytes = await self._download_icon_bytes(icon_def.url)
            return self._cache_icon_data(
                media_id, icon_bytes, icon_def, self._yotoicons_dir, "yotoicons"
            )
        except Exception as e:
            logger.error(f"Error downloading YotoIcon {media_id}: {e}")
            return None

    async def _get_official_icon(self, media_id: str, api_client: YotoApiClient) -> str | None:
        """
        Retrieve an official Yoto icon (from user or public manifest).

        Flow: Memory cache → Disk cache → User manifest → Public manifest → Download
        Includes concurrent request deduplication.
        """
        # Normalize ID (strip yoto:# prefix)
        normalized_id = self._normalize_media_id(media_id)

        # Check memory cache
        cached = self._get_from_memory_cache(normalized_id)
        if cached:
            return cached

        # Check disk cache
        cached = self._get_from_disk_cache(normalized_id)
        if cached:
            return cached

        # Ensure manifests are loaded
        await self._ensure_public_icons_manifest(api_client)
        await self._ensure_user_icon_manifest(api_client)

        # Find icon in manifests
        icon_def: DisplayIcon | None = None
        source: str = ""

        if normalized_id in self._user_manifest_by_media_id:
            icon_def = self._user_manifest_by_media_id[normalized_id]
            source = "user"
        elif normalized_id in self._public_manifest_by_media_id:
            icon_def = self._public_manifest_by_media_id[normalized_id]
            source = "official"
        else:
            logger.warning(f"Icon {normalized_id} not found in any manifest")
            return None

        # Download with concurrent request deduplication
        return await self._download_with_deduplication(
            normalized_id, icon_def, self._yoto_cache_dir, source
        )

    async def _download_with_deduplication(
        self,
        media_id: str,
        icon_def: DisplayIcon,
        target_dir: Path,
        source: str,
    ) -> str | None:
        """
        Download icon with concurrent request deduplication.

        If another request is already downloading the same URL, wait for it.
        Otherwise, download and notify other waiting requests.
        """
        async with self._running_requests_lock:
            # Double-check cache (might have been populated while waiting for lock)
            cached = self._get_from_memory_cache(media_id)
            if cached:
                return cached

            # Check if download is already in progress
            if icon_def.url in self._running_requests:
                logger.debug(f"Waiting for ongoing download of icon {media_id}")
                future = self._running_requests[icon_def.url]
                # Release lock before awaiting
                await future
                return self._icon_cache.get(media_id)

            # Start new download - create future for other requests to wait on
            self._running_requests[icon_def.url] = Future()

        # Download the icon (outside the lock)
        try:
            logger.debug(f"Downloading icon {media_id} from {icon_def.url}")
            icon_bytes = await self._download_icon_bytes(icon_def.url)
            data_url = self._cache_icon_data(media_id, icon_bytes, icon_def, target_dir, source)

            # Notify waiting requests
            self._running_requests[icon_def.url].set_result(True)
            del self._running_requests[icon_def.url]

            return data_url

        except Exception as e:
            logger.error(f"Error downloading icon {media_id}: {e}")
            # Notify waiting requests of failure
            if icon_def.url in self._running_requests:
                self._running_requests[icon_def.url].set_exception(e)
                del self._running_requests[icon_def.url]
            return None

    # ========== Main Entry Point ==========

    async def get_icon_by_media_id(
        self,
        media_id: str,
        api_client: YotoApiClient,
    ) -> str | None:
        """
        Get icon by media ID from the public manifest or yotoicons.com.

        Lazily fetches the public manifest on first call using authenticated API.
        Downloads the icon from the manifest URL or yotoicons.com on demand.

        Args:
            media_id: The media ID from DisplayIcon.mediaId (e.g., "yotoicons:123", "yoto:#abc", or "abc")
            api_client: YotoApiClient instance (required for manifest fetch and downloads)

        Returns:
            Icon data URL (base64), or None if not found
        """
        # Dispatch based on icon type
        if media_id.startswith("yotoicons:"):
            return await self._get_yotoicons_icon(media_id)
        else:
            return await self._get_official_icon(media_id, api_client)

    def _initialize_search_service(self) -> None:
        """Initialize the search service with current manifests."""
        if self._search_service is not None:
            return  # Already initialized

        official_icons = self._public_manifest.displayIcons if self._public_manifest else []
        self._search_service = IconSearchService(
            official_manifest=official_icons,
            yotoicons_cache_dir=self._yotoicons_dir,
        )
        logger.debug("Initialized IconSearchService")

    async def get_icons(
        self,
        api_client: YotoApiClient,
        sources: list[IconRetrieveSource],
        query: str | None = None,
        fuzzy: bool = True,
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[list[DisplayIcon], int]:
        """
        Get a list of icons with advanced search and pagination.

        Args:
            api_client: API client for manifest loading
            sources: Icon sources (user, official, yotoicons, yotoicons_cache)
            query: Search query for titles
            fuzzy: Use fuzzy matching on titles
            page: Page number (1-indexed)
            per_page: Results per page

        Returns:
            Tuple of (list of icons for this page, total count)
        """
        await self._ensure_public_icons_manifest(api_client)
        await self._ensure_user_icon_manifest(api_client)
        self._initialize_search_service()
        assert self._search_service is not None

        # Handle live online search
        if IconRetrieveSource.ONLINE in sources:
            sources = ALL_ONLINE_SOURCES
        if any(s in sources for s in ALL_ONLINE_SOURCES):
            online_sources = [s for s in sources if s in ALL_ONLINE_SOURCES]
            if not query:
                return [], 0
            icons = await self.search_online(query, online_sources=online_sources)
            # Add to cache for future access
            if icons:
                self._search_service.add_yotoicons_to_cache(icons)
            # Apply pagination
            total = len(icons)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            return icons[start_idx:end_idx], total

        # User icons
        if IconRetrieveSource.USER in sources:
            icons = self._user_manifest.displayIcons if self._user_manifest else []
            total = len(icons)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            return icons[start_idx:end_idx], total

        # Use search service for official and yotoicons_cache
        if IconRetrieveSource.CACHED in sources:
            sources = ALL_CACHED_SOURCES
        search_sources: list[SearchSource] = []
        if IconRetrieveSource.OFFICIAL in sources:
            search_sources.append(SearchSource.OFFICIAL)
        if IconRetrieveSource.CACHED_YOTOICONS in sources:
            search_sources.append(SearchSource.YOTOICONS)

        if not search_sources:
            return [], 0

        # Perform search with pagination
        icons, total = self._search_service.search(
            query=query,
            fuzzy=fuzzy,
            sources=search_sources,
            page=page,
            per_page=per_page,
        )

        return icons, total

    async def search_online(
        self, query: str, online_sources: list[IconRetrieveSource]
    ) -> list[DisplayIcon]:
        """Search yotoicons.com online and return DisplayIcon objects."""
        results: list[DisplayIcon] = []

        if (
            IconRetrieveSource.ONLINE_YOTOICONS in online_sources
            or IconRetrieveSource.ONLINE in online_sources
        ):
            online_results = await self._search_yotoicons_online(query)
            results.extend(online_results)

        # TODO: Sort results by relevance if needed

        return results

    async def _search_yotoicons_online(self, query: str) -> list[DisplayIcon]:
        from yoto_web_server.api.models import DisplayIcon

        searcher = YotoIconsSearcher(self._yotoicons_search_cache_dir)
        try:
            results = await searcher.search(query)

            display_icons = []
            for res in results:
                icon = DisplayIcon(
                    createdAt="",  # Not available
                    displayIconId=f"yotoicons:{res.id}",
                    mediaId=f"yotoicons:{res.id}",
                    public=True,
                    publicTags=res.tags,
                    title=f"{res.category} by {res.author}",
                    url=res.img_url,  # Will be cached lazily when requested
                    userId="yotoicons",
                    new=False,
                )
                display_icons.append(icon)

            return display_icons

        finally:
            await searcher.close()

    async def resolve_media_id(self, media_id: str, api_client: YotoApiClient) -> str:
        """
        Resolve a media ID to an official Yoto media ID.
        If it's a yotoicons ID, it provisions it (upload to Yoto) and returns the new official ID.
        Otherwise returns the ID as is (without yoto:# prefix - that's added by the caller).
        """
        if media_id.startswith("yotoicons:"):
            official_id = await self._provision_yotoicon_id(media_id, api_client)
            if not official_id:
                # Provisioning failed - log error and raise exception
                logger.error(f"Failed to provision YotoIcon {media_id}")
                raise ValueError(f"Failed to provision YotoIcon {media_id}")
            return official_id
        # Remove yoto:# prefix if present (caller adds it back if needed)
        if media_id.startswith("yoto:#"):
            return media_id.removeprefix("yoto:#")
        return media_id

    async def _provision_yotoicon_id(self, icon_id: str, api_client: YotoApiClient) -> str | None:
        """
        Download a YotoIcon and upload it to Yoto API.
        Returns the official mediaId.
        """
        # Check if we already have a mapping
        if icon_id in self._yotoicons_to_official_mapping:
            official_id = self._yotoicons_to_official_mapping[icon_id]
            logger.info(f"Using cached mapping for {icon_id} -> {official_id}")
            return official_id

        yotoicons_id = icon_id.removeprefix("yotoicons:")
        url = f"https://www.yotoicons.com/static/uploads/{yotoicons_id}.png"

        try:
            logger.info(f"Provisioning YotoIcon {yotoicons_id}...")

            # 1. Download
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    icon_bytes = resp.content

                logger.debug(f"Downloaded {yotoicons_id}: {len(icon_bytes)} bytes")
            except httpx.HTTPError as download_err:
                logger.error(f"Failed to download icon from {url}: {download_err}", exc_info=True)
                raise

            # 2. Upload to Yoto
            try:
                logger.debug(f"Uploading {len(icon_bytes)} bytes to Yoto API...")
                upload_resp = await api_client.upload_icon(
                    icon_bytes, filename=f"yotoicons_{yotoicons_id}.png"
                )

                logger.debug(f"Upload response received: {upload_resp!r}")
                official_media_id = upload_resp.mediaId
                logger.debug(
                    f"Upload response mediaId: {official_media_id!r} (type: {type(official_media_id).__name__}, length: {len(official_media_id) if official_media_id else 'N/A'})"
                )

                if not official_media_id:
                    logger.error("Upload returned empty mediaId")
                    raise ValueError("Upload returned empty mediaId")

                # Ensure the ID is clean (without yoto:# prefix)
                # The API may return either "yoto:#xxx" or just "xxx"
                if official_media_id.startswith("yoto:#"):
                    logger.debug("Stripping yoto:# prefix from mediaId")
                    official_media_id = official_media_id.removeprefix("yoto:#")

                # Validate ID format (should be 43 characters)
                if len(official_media_id) != 43:
                    logger.error(
                        f"Unexpected mediaId length: {len(official_media_id)} chars (expected 43): {official_media_id!r}"
                    )
                    raise ValueError(
                        f"Invalid mediaId format from API: expected 43 chars, got {len(official_media_id)}"
                    )

                logger.info(f"Successfully uploaded to Yoto: {official_media_id}")

                # 3. Store mapping
                self._yotoicons_to_official_mapping[icon_id] = official_media_id
                self._provisioning_map_file.write_text(
                    json.dumps(self._yotoicons_to_official_mapping, indent=2)
                )

                # 4. Invalidate user manifest cache so the new icon shows up
                self._user_manifest_by_media_id = {}
                self._user_manifest = None

                logger.info(f"Provisioning complete: {icon_id} -> {official_media_id}")
                return official_media_id
            except Exception as upload_err:
                logger.error(f"Failed to upload icon to Yoto: {upload_err}", exc_info=True)
                raise

        except Exception as e:
            logger.error(f"Failed to provision YotoIcon {icon_id}: {e}", exc_info=True)
            return None

    def _save_icon_to_disk(
        self,
        media_id: str,
        data: str,
        icon_def: DisplayIcon,
        target_dir: Path,
        source: str,
    ) -> None:
        try:
            filename = f"{sanitize_filename(media_id)}.json"
            file_path = target_dir / filename

            entry = IconEntry(
                id=media_id,
                path=str(file_path),
                source=source,
                name=icon_def.title or icon_def.displayIconId or media_id,
                data=data,
                tags=icon_def.publicTags or [],
                keywords=icon_def.publicTags or [],
            )

            with file_path.open("w") as f:
                f.write(entry.model_dump_json(indent=2))

            # Update index
            self._indices.official.add_entry(entry)

            logger.debug(f"Saved icon {media_id} to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save icon {media_id} to disk: {e}")
