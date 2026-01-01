"""
Icon Search Service.

Advanced search across official and yotoicons sources with support for:
- Partial and fuzzy matching on titles and tags
- Combined query searching
"""

from __future__ import annotations

from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from yoto_web_server.utils.sanitation import sanitize_filename

if TYPE_CHECKING:
    from yoto_web_server.models import DisplayIcon


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
        official_manifest: list[DisplayIcon] | None = None,
        yotoicons_cache_dir: Path | None = None,
    ):
        self.official_manifest = official_manifest or []
        self.yotoicons_cache_dir = yotoicons_cache_dir
        self._yotoicons_cache: dict[str, DisplayIcon] = {}

        if yotoicons_cache_dir:
            self._load_yotoicons_cache()

    def _load_yotoicons_cache(self) -> None:
        """Load all cached yotoicons from disk."""
        if not self.yotoicons_cache_dir or not self.yotoicons_cache_dir.exists():
            return

        from yoto_web_server.models import DisplayIcon

        for icon_file in self.yotoicons_cache_dir.glob("*.json"):
            try:
                with icon_file.open() as f:
                    icon = DisplayIcon.model_validate_json(f.read())
                    self._yotoicons_cache[icon.mediaId] = icon
                    logger.debug(f"Loaded yotoicon from cache: {icon.mediaId}")
            except Exception as e:
                logger.warning(f"Failed to load yotoicon cache file {icon_file}: {e}")

    def add_yotoicons_to_cache(self, icons: list[DisplayIcon]) -> None:
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

    def _matches_query(self, query: str, text: str, fuzzy: bool = True) -> bool:
        """Check if text matches the query using fuzzy or partial matching."""
        match_fn = self._fuzzy_match if fuzzy else self._partial_match
        return match_fn(query, text)

    def search(
        self,
        query: str | None = None,
        fuzzy: bool = True,
        sources: list[SearchSource] | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[list[DisplayIcon], int]:
        """
        Search icons by query matching against title and tags with pagination.

        Args:
            query: Search query (matches against both title and tags)
            fuzzy: Use fuzzy matching (True) or partial matching (False)
            sources: Which sources to search ("official", "yotoicons", or both)
            page: Page number (1-indexed)
            per_page: Results per page

        Returns:
            Tuple of (list of matching icons for this page, total count)
        """
        if not sources:
            sources = [SearchSource.OFFICIAL, SearchSource.YOTOICONS]

        # If no query provided, return all icons
        if not query:
            results: list[DisplayIcon] = []
            if SearchSource.OFFICIAL in sources:
                results.extend(self.official_manifest)
            if SearchSource.YOTOICONS in sources:
                results.extend(self._yotoicons_cache.values())
        else:
            # Build list of icons to search
            icons_to_search: list[DisplayIcon] = []
            if SearchSource.OFFICIAL in sources:
                icons_to_search.extend(self.official_manifest)
            if SearchSource.YOTOICONS in sources:
                icons_to_search.extend(self._yotoicons_cache.values())

            # Search query in title and tags
            results: list[DisplayIcon] = []
            for icon in icons_to_search:
                # Check title
                title = icon.title or ""
                if self._matches_query(query, title, fuzzy):
                    results.append(icon)
                    continue

                # Check tags
                tags = icon.public_tags or []
                if any(self._matches_query(query, tag, fuzzy) for tag in tags):
                    results.append(icon)

        # Apply pagination
        total = len(results)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_results = results[start_idx:end_idx]

        return paginated_results, total

    def get_all_icons(
        self,
        sources: list[SearchSource] | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[list[DisplayIcon], int]:
        """Get all icons from selected sources with pagination."""
        if not sources:
            sources = [SearchSource.OFFICIAL, SearchSource.YOTOICONS]

        results: list[DisplayIcon] = []
        if SearchSource.OFFICIAL in sources:
            results.extend(self.official_manifest)
        if SearchSource.YOTOICONS in sources:
            results.extend(self._yotoicons_cache.values())

        # Apply pagination
        total = len(results)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_results = results[start_idx:end_idx]

        return paginated_results, total
