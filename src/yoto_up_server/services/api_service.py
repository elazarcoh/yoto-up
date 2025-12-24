"""
API Service - Wrapper around YotoAPI for the server context.

This service manages the Yoto API client instance and authentication state.
"""

import json
from pathlib import Path
from typing import Optional

from loguru import logger

from yoto_up.yoto_api import YotoAPI
from yoto_up.yoto_app import config as yoto_config
from yoto_up import paths
from yoto_up_server.models import TokenInfo, AuthStatus


class ApiService:
    """
    Service for managing Yoto API interactions.
    
    Wraps the YotoAPI class and provides server-appropriate
    token management.
    """
    
    def __init__(self) -> None:
        self._api: Optional[YotoAPI] = None
        self._client_id: str = yoto_config.CLIENT_ID
    
    def get_api(self) -> Optional[YotoAPI]:
        """
        Get the API client, initializing if necessary.
        
        Returns None if not authenticated.
        """
        if self._api is None:
            self._api = self._try_init_api()
        return self._api
    
    def _try_init_api(self) -> Optional[YotoAPI]:
        """Attempt to initialize the API from stored tokens."""
        try:
            api = YotoAPI(
                client_id=self._client_id,
                auto_start_authentication=False,
                debug=True,
            )
            
            # Check if we have a valid access token loaded (don't use api.is_authenticated()
            # because it tries to decode JWE tokens which fails)
            if api.access_token and api.access_token.strip():
                logger.info("API initialized from stored tokens")
                return api
            
            logger.debug("No valid stored tokens found")
            return api  # Return anyway for authentication flow
            
        except Exception as e:
            logger.error(f"Failed to initialize API: {e}")
            return None
    
    def is_authenticated(self) -> bool:
        """Check if the API is authenticated."""
        api = self.get_api()
        if api is None:
            return False
        
        # Check if we have tokens loaded
        if api.access_token is None:
            return False
        
        # For now, just check if we have a non-empty access token
        # The Yoto API returns encrypted JWTs which our decode_jwt can't parse
        # but they're still valid for API calls
        return bool(api.access_token.strip())
    
    def get_auth_status(self) -> AuthStatus:
        """Get current authentication status."""
        return AuthStatus(
            authenticated=self.is_authenticated(),
        )
    
    def save_tokens(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        id_token: Optional[str] = None,
    ) -> None:
        """
        Save authentication tokens.
        
        This stores tokens to the configured token file and
        reinitializes the API client.
        """
        tokens: dict = {"access_token": access_token}
        
        if refresh_token:
            tokens["refresh_token"] = refresh_token
        if id_token:
            tokens["id_token"] = id_token
        
        try:
            # Use centralized path helpers
            paths.ensure_parents(paths.TOKENS_FILE)
            paths.atomic_write(paths.TOKENS_FILE, json.dumps(tokens))
            logger.info("Tokens saved successfully")
        except Exception as e:
            logger.error(f"Failed to save tokens: {e}")
            # Fallback: direct write
            try:
                paths.TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
                with paths.TOKENS_FILE.open("w") as f:
                    json.dump(tokens, f)
            except Exception as e2:
                logger.error(f"Fallback token save also failed: {e2}")
                raise
        
        # Reinitialize API with new tokens
        self._api = self._try_init_api()
    
    def clear_tokens(self) -> None:
        """Clear stored tokens and log out."""
        try:
            if paths.TOKENS_FILE.exists():
                paths.TOKENS_FILE.unlink()
                logger.info("Tokens cleared")
        except Exception as e:
            logger.error(f"Failed to clear tokens: {e}")
        
        self._api = None
    
    def refresh_tokens(self) -> bool:
        """
        Refresh authentication tokens.
        
        Returns True if refresh was successful.
        """
        api = self.get_api()
        if api is None:
            return False
        
        try:
            api.refresh_tokens()
            return api.is_authenticated()
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            return False
