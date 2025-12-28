"""
Icon Search Service.

Advanced search across official and yotoicons sources with support for:
- Partial and fuzzy matching on titles
- Tag-based filtering
- Combined searches
"""

from __future__ import annotations

from enum import Enum
import json
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Literal, Optional

from difflib import SequenceMatcher
from loguru import logger

from yoto_up_server.utils.sanitation import sanitize_filename

if TYPE_CHECKING:
    from yoto_up_server.models import DisplayIcon

class SearchSource(str, Enum):
    OFFICIAL = "official"
    YOTOICONS = "yotoicons"

class IconSearchService:
    """
    Advanced search service for icons.
    
    Searches across:
    - Official icons manifest
    - Cached YotoIcons (stored individually, not query-based)
    """

    def __init__(
        self,
        official_manifest: Optional[List[DisplayIcon]] = None,
        yotoicons_cache_dir: Optional[Path] = None,
    ):
        self.official_manifest = official_manifest or []
        self.yotoicons_cache_dir = yotoicons_cache_dir
        self._yotoicons_cache: Dict[str, DisplayIcon] = {}
        
        if yotoicons_cache_dir:
            self._load_yotoicons_cache()

    def _load_yotoicons_cache(self) -> None:
        """Load all cached yotoicons from disk."""
        if not self.yotoicons_cache_dir or not self.yotoicons_cache_dir.exists():
            return
            
        from yoto_up_server.models import DisplayIcon
        
        for icon_file in self.yotoicons_cache_dir.glob("*.json"):
            try:
                with icon_file.open() as f:
                    icon = DisplayIcon.model_validate_json(f.read())
                    self._yotoicons_cache[icon.mediaId] = icon
                    logger.debug(f"Loaded yotoicon from cache: {icon.mediaId}")
            except Exception as e:
                logger.warning(f"Failed to load yotoicon cache file {icon_file}: {e}")

    def add_yotoicons_to_cache(self, icons: List[DisplayIcon]) -> None:
        """Add yotoicons to the in-memory and disk cache."""
        
        for icon in icons:
            self._yotoicons_cache[icon.mediaId] = icon
            
            # Save to disk
            if self.yotoicons_cache_dir:
                cache_file = self.yotoicons_cache_dir / f"{sanitize_filename(icon.mediaId)}.json"
                try:
                    cache_file.write_text(icon.model_dump_json())
                except Exception as e:
                    logger.error(f"Failed to save yotoicon to cache: {e}")

    def _fuzzy_match(self, query: str, text: str, threshold: float = 0.6) -> bool:
        """Fuzzy string matching."""
        ratio = SequenceMatcher(None, query.lower(), text.lower()).ratio()
        return ratio >= threshold

    def _partial_match(self, query: str, text: str) -> bool:
        """Partial string matching (substring)."""
        return query.lower() in text.lower()

    def search_by_title(
        self,
        query: str,
        fuzzy: bool = True,
        sources: List[SearchSource] | None = None,
        limit: int = 100,
    ) -> List[DisplayIcon]:
        """
        Search icons by title.
        
        Args:
            query: Search query
            fuzzy: Use fuzzy matching (True) or partial matching (False)
            sources: Which sources to search ("official", "yotoicons", or both)
            limit: Maximum results
            
        Returns:
            List of matching icons
        """
        if not sources:
            sources = [SearchSource.OFFICIAL, SearchSource.YOTOICONS]
            
        results: List[DisplayIcon] = []
        icons_to_search: List[DisplayIcon] = []
        
        if SearchSource.OFFICIAL in sources:
            icons_to_search.extend(self.official_manifest)
        if SearchSource.YOTOICONS in sources:
            icons_to_search.extend(self._yotoicons_cache.values())
        
        # Match function
        match_fn = self._fuzzy_match if fuzzy else self._partial_match
        
        for icon in icons_to_search:
            title = icon.title or ""
            if match_fn(query, title):
                results.append(icon)
        
        return results[:limit]

    def search_by_tags(
        self,
        tags: List[str],
        match_all: bool = False,
        sources: List[SearchSource] | None = None,
        limit: int = 100,
    ) -> List[DisplayIcon]:
        """
        Search icons by tags.
        
        Args:
            tags: List of tags to search for
            match_all: If True, icon must have all tags. If False, icon must have any tag.
            sources: Which sources to search
            limit: Maximum results
            
        Returns:
            List of matching icons
        """
        if not sources:
            sources = [SearchSource.OFFICIAL, SearchSource.YOTOICONS]
            
        if not tags:
            return []
        
        results: List[DisplayIcon] = []
        icons_to_search: List[DisplayIcon] = []
        
        if SearchSource.OFFICIAL in sources:
            icons_to_search.extend(self.official_manifest)
        if SearchSource.YOTOICONS in sources:
            icons_to_search.extend(self._yotoicons_cache.values())
        
        tags_lower = [t.lower() for t in tags]
        
        for icon in icons_to_search:
            icon_tags = [t.lower() for t in (icon.publicTags or [])]
            
            if match_all:
                # All search tags must be present
                if all(tag in icon_tags for tag in tags_lower):
                    results.append(icon)
            else:
                # Any search tag can be present
                if any(tag in icon_tags for tag in tags_lower):
                    results.append(icon)
        
        return results[:limit]

    def search_combined(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        fuzzy: bool = True,
        sources: List[SearchSource] | None = None,  
        limit: int = 100,
    ) -> List[DisplayIcon]:
        """
        Combined search on title and/or tags.
        
        Args:
            query: Search query for titles
            tags: Tags to filter by
            fuzzy: Use fuzzy matching for titles
            sources: Which sources to search
            limit: Maximum results
            
        Returns:
            List of matching icons (intersection of criteria if both specified)
        """
        if not sources:
            sources = [SearchSource.OFFICIAL, SearchSource.YOTOICONS]
        
        results: List[DisplayIcon] = []
        
        # Start with title search if query provided
        if query:
            results = self.search_by_title(query, fuzzy=fuzzy, sources=sources, limit=limit * 2)
        else:
            # Get all icons from selected sources
            if SearchSource.OFFICIAL in sources:
                results.extend(self.official_manifest)
            if SearchSource.YOTOICONS in sources:
                results.extend(self._yotoicons_cache.values())
        
        # Filter by tags if provided
        if tags:
            tag_results = set(
                icon.mediaId 
                for icon in self.search_by_tags(tags, match_all=False, sources=sources)
            )
            results = [icon for icon in results if icon.mediaId in tag_results]
        
        return results[:limit]

    def search(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        fuzzy: bool = True,
        sources: List[SearchSource] | None = None,
        limit: int = 100,
    ) -> List[DisplayIcon]:
        """
        Unified search interface.
        
        Default behavior: combined search on title and tags.
        If only query: search by title
        If only tags: search by tags
        If both: combined search (intersection)
        """
        if query or tags:
            return self.search_combined(
                query=query,
                tags=tags,
                fuzzy=fuzzy,
                sources=sources,
                limit=limit,
            )
        
        # Return all icons if no search criteria
        if not sources:
            sources = [SearchSource.OFFICIAL, SearchSource.YOTOICONS]
        
        results: List[DisplayIcon] = []
        if SearchSource.OFFICIAL in sources:
            results.extend(self.official_manifest)
        if SearchSource.YOTOICONS in sources:
            results.extend(self._yotoicons_cache.values())
        
        return results[:limit]

    def get_all_icons(
        self,
        sources: List[SearchSource] | None = None,
    ) -> List[DisplayIcon]:
        """Get all icons from selected sources."""
        if not sources:
            sources = [SearchSource.OFFICIAL, SearchSource.YOTOICONS]
        
        results: List[DisplayIcon] = []
        if SearchSource.OFFICIAL in sources:
            results.extend(self.official_manifest)
        if SearchSource.YOTOICONS in sources:
            results.extend(self._yotoicons_cache.values())
        
        return results
