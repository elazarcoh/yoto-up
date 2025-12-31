"""
Authentication router.

Handles OAuth flow with session-based authentication.
"""

import secrets
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from loguru import logger
from pydantic import BaseModel

from yoto_web_server.core.config import get_settings
from yoto_web_server.dependencies import SessionAwareApiServiceDep, SessionServiceDep
from yoto_web_server.middleware.session_middleware import (
    SESSION_COOKIE_SECURE,
    clear_session_cookie,
    get_cookie_payload_from_request,
    get_session_id_from_request,
    set_session_cookie,
)
from yoto_web_server.templates.auth import AuthPage, AuthStatusPartial, DeviceCodeInstructions
from yoto_web_server.templates.base import render_page, render_partial

router = APIRouter()


class TokenResponse(BaseModel):
    """Response from token exchange."""

    access_token: str
    refresh_token: str
    id_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: int = 86400


@router.get("/", response_class=HTMLResponse)
async def auth_page(request: Request) -> str:
    """Render the authentication page."""
    session_id = get_session_id_from_request(request)
    is_authenticated = session_id is not None

    return render_page(
        title="Authentication - Yoto Web Server",
        content=AuthPage(is_authenticated=is_authenticated),
        request=request,
    )


@router.get("/status", response_class=HTMLResponse)
async def auth_status(request: Request) -> str:
    """Return current authentication status as HTML partial."""
    session_id = get_session_id_from_request(request)
    is_authenticated = session_id is not None

    return render_partial(AuthStatusPartial(is_authenticated=is_authenticated))


@router.post("/oauth-start", response_class=HTMLResponse)
async def start_oauth_flow(request: Request) -> HTMLResponse:
    """
    Start the OAuth authorization code flow.

    Redirects user to Yoto login page.
    """
    settings = get_settings()
    client_id = settings.yoto_client_id

    try:
        # Generate state token for CSRF protection
        state = secrets.token_urlsafe(32)

        # Store state in app state
        if not hasattr(request.app.state, "oauth_states"):
            request.app.state.oauth_states = {}
        request.app.state.oauth_states[state] = True

        # Build authorization URL
        auth_params = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": f"http://localhost:{settings.port}/auth/oauth-callback",
            "scope": "profile offline_access",
            "audience": settings.yoto_base_url,
            "state": state,
        }

        auth_url = f"{settings.yoto_auth_url}/authorize?{urlencode(auth_params)}"
        logger.info(f"OAuth flow started, redirecting to: {auth_url}")

        html_content = f"""
        <script>
            window.location.href = '{auth_url}';
        </script>
        <p>Redirecting to Yoto login...</p>
        """
        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"Error starting OAuth flow: {e}")
        return HTMLResponse(
            content=render_partial(
                AuthStatusPartial(
                    is_authenticated=False,
                    error="Failed to start authentication. Please try again.",
                )
            )
        )


@router.get("/oauth-callback")
async def oauth_callback(
    request: Request,
    response: Response,
    session_service: SessionServiceDep,
    session_api_service: SessionAwareApiServiceDep,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
) -> RedirectResponse:
    """
    Handle OAuth callback from Yoto.

    Exchanges authorization code for tokens and creates session.
    """
    settings = get_settings()

    # Check for error
    if error:
        logger.error(f"OAuth error: {error} - {error_description}")
        return RedirectResponse(url="/auth?error=oauth_failed")

    # Verify state (CSRF protection)
    oauth_states = getattr(request.app.state, "oauth_states", {})
    if not state or state not in oauth_states:
        logger.error("Invalid OAuth state")
        return RedirectResponse(url="/auth?error=invalid_state")

    # Remove used state
    del oauth_states[state]

    if not code:
        logger.error("No authorization code in callback")
        return RedirectResponse(url="/auth?error=no_code")

    try:
        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                f"{settings.yoto_auth_url}/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.yoto_client_id,
                    "code": code,
                    "redirect_uri": f"http://localhost:{settings.port}/auth/oauth-callback",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0,
            )
            token_response.raise_for_status()
            token_data = token_response.json()

        # Create session
        import time

        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token", "")
        expires_in = token_data.get("expires_in", 86400)

        current_time = time.time()
        access_expiry = current_time + expires_in
        refresh_expiry = current_time + (30 * 24 * 60 * 60)  # 30 days

        session_id, cookie_payload = session_service.create_session(
            access_token=access_token,
            access_token_expiry=access_expiry,
            refresh_token=refresh_token,
            refresh_token_expiry=refresh_expiry,
        )

        # Create redirect response with cookie
        redirect = RedirectResponse(url="/playlists", status_code=303)
        set_session_cookie(
            redirect,
            session_service,
            cookie_payload,
            secure=SESSION_COOKIE_SECURE,
        )

        logger.info(f"OAuth flow completed, session created: {session_id[:8]}...")
        return redirect

    except httpx.HTTPStatusError as e:
        logger.error(f"Token exchange failed: {e.response.text}")
        return RedirectResponse(url="/auth?error=token_exchange_failed")
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return RedirectResponse(url="/auth?error=unexpected_error")


@router.post("/logout")
async def logout(
    request: Request,
    session_api_service: SessionAwareApiServiceDep,
) -> RedirectResponse:
    """Logout and clear session."""
    session_id = get_session_id_from_request(request)

    if session_id:
        await session_api_service.logout_session(session_id)

    redirect = RedirectResponse(url="/", status_code=303)
    clear_session_cookie(redirect)

    return redirect
