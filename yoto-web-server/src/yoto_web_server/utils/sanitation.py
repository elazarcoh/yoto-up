import os
import re


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing or replacing unsafe characters.

    Args:
        filename: The original filename.

    Returns:
        A sanitized filename safe for filesystem use.
    """
    # Remove any path components
    filename = os.path.basename(filename)

    # Replace unsafe characters with underscores
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", filename)

    # Limit length to 255 characters
    return sanitized[:255]


def html_id_safe(s: str) -> str:
    """Convert a string to a safe HTML ID by replacing unsafe characters."""
    return s.replace(" ", "-").replace("#", "%23").replace("/", "-").replace(":", "-")
