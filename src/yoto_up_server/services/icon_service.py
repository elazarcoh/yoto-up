"""
Icon Service.

Handles icon browsing, searching, and management.
Fetches public icons from Yoto API manifest and downloads them on demand.
"""

import hashlib
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

import httpx
from loguru import logger
from PIL import Image

from yoto_up import paths
from yoto_up.icons import render_icon
from yoto_up_server.models import DisplayIcon, DisplayIconManifest


class IconService:
    """
    Service for icon management.
    
    - Fetches public icon manifest from Yoto API on initialization
    - Provides icon searching and retrieval by media ID
    - Downloads icons on demand (no caching for now, see TODO below)
    - Manages local icon caching for CLI/TUI usage
    """
    
    # Public icons manifest URL (from Yoto API)
    YOTO_MANIFEST_URL = "https://api.yotoplay.com/displayIcons"
    
    def __init__(self) -> None:
        self._cache_dir = paths.OFFICIAL_ICON_CACHE_DIR
        self._yotoicons_dir = paths.YOTOICONS_CACHE_DIR
        self._user_icons_dir = paths.USER_ICONS_DIR
        
        # Ensure directories exist
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._yotoicons_dir.mkdir(parents=True, exist_ok=True)
        self._user_icons_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory index for local icons
        self._local_index: Dict[str, Dict[str, Any]] = {}
        self._local_index_built = False
        
        # In-memory manifest of public icons
        self._public_manifest: Optional[DisplayIconManifest] = None
        self._public_manifest_by_media_id: Dict[str, DisplayIcon] = {}
        
        # In-memory cache for downloaded icons (bytes)
        self._icon_bytes_cache: Dict[str, bytes] = {}
    
    async def initialize(self) -> None:
        """Initialize the service by fetching the public icons manifest."""
        try:
            await self._fetch_public_manifest()
        except Exception as e:
            logger.warning(
                f"Failed to fetch public manifest (will use demo/cache): {e}"
            )
            # Fallback: use empty manifest, will try to fetch from authenticated API later
            self._public_manifest = DisplayIconManifest(displayIcons=[])
            self._public_manifest_by_media_id = {}
        
        # Always build local index
        self._build_local_index()
        
        logger.info(
            f"IconService initialized: "
            f"{len(self._public_manifest_by_media_id)} public icons, "
            f"{len(self._local_index)} local icons"
        )
    
    async def _fetch_public_manifest(self) -> None:
        """Fetch the public icons manifest from Yoto API."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.debug(f"Fetching public manifest from {self.YOTO_MANIFEST_URL}")
                response = await client.get(self.YOTO_MANIFEST_URL)
                response.raise_for_status()
                data = response.json()
            
            # Parse the manifest
            self._public_manifest = DisplayIconManifest.parse_obj(data)
            
            # Build lookup index by mediaId
            self._public_manifest_by_media_id = {
                icon.mediaId: icon
                for icon in self._public_manifest.displayIcons
            }
            
            logger.info(
                f"Fetched public manifest: {len(self._public_manifest.displayIcons)} icons"
            )
        except Exception as e:
            logger.error(f"Error fetching public manifest: {e}")
            raise
    
    def _build_local_index(self):
        """Build the in-memory icon index from cache directories."""
        if self._local_index_built:
            return
        
        self._local_index = {}
        
        # Index official icons
        self._index_from_dir(self._cache_dir, "official")
        
        # Index yotoicons
        self._index_from_dir(self._yotoicons_dir, "yotoicons")
        
        # Index user icons
        self._index_from_dir(self._user_icons_dir, "local")
        
        self._local_index_built = True
        logger.info(f"Local icon index built: {len(self._local_index)} icons")
    
    def _index_from_dir(self, directory: Path, source: str):
        """Index icons from a directory."""
        if not directory.exists():
            return
        
        for path in directory.glob("*.png"):
            icon_id = path.stem
            
            # Try to load metadata
            meta = {}
            meta_path = path.with_suffix(".json")
            if meta_path.exists():
                try:
                    with meta_path.open() as f:
                        meta = json.load(f)
                except Exception:
                    pass
            
            self._local_index[icon_id] = {
                "id": icon_id,
                "path": str(path),
                "source": source,
                "name": meta.get("name", icon_id),
                "tags": meta.get("tags", []),
                "keywords": meta.get("keywords", []),
            }
    
    async def get_icon_by_media_id(self, media_id: str) -> Optional[bytes]:
        """
        Get icon bytes by media ID from the public manifest.
        
        Downloads the icon from the manifest URL on demand.
        
        Args:
            media_id: The media ID from DisplayIcon.mediaId
        
        Returns:
            Icon image bytes, or None if not found
        """
        # Check if we have it cached in memory
        if media_id in self._icon_bytes_cache:
            logger.debug(f"Icon {media_id} found in memory cache")
            return self._icon_bytes_cache[media_id]
        
        # Check if it's in the public manifest
        if media_id not in self._public_manifest_by_media_id:
            logger.warning(f"Icon {media_id} not found in public manifest")
            return None
        
        icon = self._public_manifest_by_media_id[media_id]
        
        # Download the icon from the URL
        try:
            logger.debug(f"Downloading icon {media_id} from {icon.url}")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(icon.url)
                response.raise_for_status()
                icon_bytes = response.content
            
            # TODO: Cache to disk using icon.mediaId as filename
            # TODO: Implement cache expiration/management strategy
            
            # Cache in memory for now
            self._icon_bytes_cache[media_id] = icon_bytes
            
            logger.info(f"Downloaded icon {media_id}: {len(icon_bytes)} bytes")
            return icon_bytes
            
        except Exception as e:
            logger.error(f"Error downloading icon {media_id}: {e}")
            return None
    
    def get_public_manifest(self) -> DisplayIconManifest:
        """Get the cached public icons manifest."""
        return self._public_manifest or DisplayIconManifest(displayIcons=[])
    
    def search_icons(
        self,
        query: Optional[str] = None,
        source: Optional[str] = None,
        fuzzy: bool = False,
        threshold: float = 0.6,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Search icons in local index.
        
        Args:
            query: Search query string.
            source: Filter by source: official, yotoicons, local.
            fuzzy: Enable fuzzy matching.
            threshold: Fuzzy match threshold (0-1).
            limit: Maximum results to return.
        
        Returns:
            List of matching icon dictionaries.
        """
        self._build_local_index()
        
        results = list(self._local_index.values())
        
        # Filter by source
        if source:
            results = [r for r in results if r["source"] == source]
        
        # Filter by query
        if query:
            query_lower = query.lower()
            
            if fuzzy:
                # Fuzzy matching
                try:
                    from rapidfuzz import fuzz
                    
                    def match_score(icon):
                        name = icon.get("name", "").lower()
                        tags = " ".join(icon.get("tags", [])).lower()
                        keywords = " ".join(icon.get("keywords", [])).lower()
                        
                        name_score = fuzz.partial_ratio(query_lower, name) / 100
                        tags_score = fuzz.partial_ratio(query_lower, tags) / 100
                        keywords_score = fuzz.partial_ratio(query_lower, keywords) / 100
                        
                        return max(name_score, tags_score, keywords_score)
                    
                    scored = [(icon, match_score(icon)) for icon in results]
                    scored = [(icon, score) for icon, score in scored if score >= threshold]
                    scored.sort(key=lambda x: x[1], reverse=True)
                    results = [icon for icon, _ in scored]
                    
                except ImportError:
                    # Fall back to simple matching
                    results = [r for r in results if self._simple_match(r, query_lower)]
            else:
                # Exact substring matching
                results = [r for r in results if self._simple_match(r, query_lower)]
        
        return results[:limit]
    
    def _simple_match(self, icon: Dict[str, Any], query: str) -> bool:
        """Simple substring matching."""
        name = icon.get("name", "").lower()

        tags = " ".join(icon.get("tags", [])).lower()
        keywords = " ".join(icon.get("keywords", [])).lower()
        
        return query in name or query in tags or query in keywords
    
    async def search_online(
        self,
        query: str,
        session_api,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Search YotoIcons online.
        
        Args:
            query: Search query string.
            session_api: SessionAwareApiService instance.
            limit: Maximum results.
        
        Returns:
            List of matching icon dictionaries.
        """
        try:
            # Use the API's yotoicons search if available
            if hasattr(session_api, "search_yotoicons"):
                results = await session_api.search_yotoicons(query, limit=limit)
                return results
            
            logger.warning("Online icon search not available in API")
            return []
            
        except Exception as e:
            logger.error(f"Online icon search failed: {e}")
            return []
    
    def get_icon(self, icon_id: str) -> Optional[Dict[str, Any]]:
        """Get icon by ID."""
        self._build_index()
        return self._index.get(icon_id)
    
    def get_icon_path(self, icon_id: str, size: int = 16) -> Optional[str]:
        """Get path to icon image file."""
        icon = self.get_icon(icon_id)
        if icon:
            return icon.get("path")
        return None
    
    async def upload_icon(
        self,
        content: bytes,
        filename: str,
        session_api,
    ) -> Dict[str, Any]:
        """
        Upload an icon image.
        
        Args:
            content: Image file content.
            filename: Original filename.
            session_api: SessionAwareApiService instance.
        
        Returns:
            Uploaded icon dictionary.
        """
        # Load and validate image
        from io import BytesIO
        
        img = Image.open(BytesIO(content))
        
        # Resize to 16x16 if necessary
        if img.size != (16, 16):
            img = img.resize((16, 16), Image.Resampling.NEAREST)
        
        # Convert to RGB if necessary
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        # Generate icon ID from content hash
        icon_id = hashlib.sha256(content).hexdigest()[:16]
        
        # Save locally
        local_path = self._user_icons_dir / f"{icon_id}.png"
        img.save(local_path, "PNG")
        
        # Upload to Yoto if API available
        try:
            if hasattr(session_api, "upload_icon"):
                result = await session_api.upload_icon(local_path)
                logger.info(f"Icon uploaded to Yoto: {result}")
        except Exception as e:
            logger.error(f"Failed to upload icon to Yoto: {e}")
        
        # Update index
        icon_data = {
            "id": icon_id,
            "path": str(local_path),
            "source": "local",
            "name": Path(filename).stem,
            "tags": [],
            "keywords": [],
        }
        self._index[icon_id] = icon_data
        
        return icon_data
    
    async def create_from_pixels(
        self,
        pixels: List[List[str]],
        name: str,
        session_api,
    ) -> Dict[str, Any]:
        """
        Create an icon from pixel data.
        
        Args:
            pixels: 16x16 array of hex color strings.
            name: Icon name.
            session_api: SessionAwareApiService instance.
        
        Returns:
            Created icon dictionary.
        """
        # Create image from pixels
        img = Image.new("RGB", (16, 16))
        
        for y, row in enumerate(pixels):
            for x, color in enumerate(row):
                # Parse hex color
                if color.startswith("#"):
                    color = color[1:]
                r = int(color[0:2], 16)
                g = int(color[2:4], 16)
                b = int(color[4:6], 16)
                img.putpixel((x, y), (r, g, b))
        
        # Generate icon ID from pixel data
        pixel_str = "".join("".join(row) for row in pixels)
        icon_id = hashlib.sha256(pixel_str.encode()).hexdigest()[:16]
        
        # Save locally
        local_path = self._user_icons_dir / f"{icon_id}.png"
        img.save(local_path, "PNG")
        
        # Upload to Yoto if API available
        try:
            if hasattr(session_api, "upload_icon"):
                result = await session_api.upload_icon(local_path)
                logger.info(f"Icon uploaded to Yoto: {result}")
        except Exception as e:
            logger.error(f"Failed to upload icon to Yoto: {e}")
        
        # Update index
        icon_data = {
            "id": icon_id,
            "path": str(local_path),
            "source": "local",
            "name": name,
            "tags": [],
            "keywords": [],
        }
        self._index[icon_id] = icon_data
        
        return icon_data
    
    async def refresh_cache(self, session_api: Optional = None) -> None:
        """
        Refresh the icon cache from the API.
        
        Args:
            session_api: Optional SessionAwareApiService instance. Uses service's API if not provided.
        """
        if session_api is None:
            session_api = self._api_service
        
        if session_api is None:
            logger.warning("Cannot refresh icon cache: API not available")
            return
        
        try:
            # Refresh public icons
            await session_api.get_public_icons(show_in_console=False)
            
            # Refresh user icons
            await session_api.get_user_icons(show_in_console=False)
            
            # Rebuild index
            self._index_built = False
            self._build_index()
            
            logger.info("Icon cache refreshed")
            
        except Exception as e:
            logger.error(f"Failed to refresh icon cache: {e}")
    
    def clear_cache(self) -> bool:
        """Clear all cached icons from disk."""
        try:
            import shutil
            
            # Clear official icons cache
            if self._cache_dir.exists():
                shutil.rmtree(self._cache_dir)
                self._cache_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Cleared official icons cache: {self._cache_dir}")
            
            # Clear yotoicons cache
            if self._yotoicons_dir.exists():
                shutil.rmtree(self._yotoicons_dir)
                self._yotoicons_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Cleared yotoicons cache: {self._yotoicons_dir}")
            
            # Clear in-memory index
            self._index = {}
            self._index_built = False
            
            logger.info("Icon cache cleared")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear icon cache: {e}")
            return False
