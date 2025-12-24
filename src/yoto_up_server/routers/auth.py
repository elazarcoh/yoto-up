"""
Authentication router.

Handles device-code OAuth flow for Yoto API authentication.
"""

import os
from typing import Optional

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from loguru import logger
from pydantic import BaseModel

# Import config from the existing yoto_up package
from yoto_up.yoto_app import config as yoto_config
from yoto_up_server.dependencies import ApiServiceDep
from yoto_up_server.templates.auth import (
    AuthPage,
    AuthStatusPartial,
    DeviceCodeInstructions,
)
from yoto_up_server.templates.base import render_page, render_partial

router = APIRouter()


class DeviceCodeResponse(BaseModel):
    """Response from device code request."""

    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int


class TokenResponse(BaseModel):
    """Response from token exchange."""

    access_token: str
    refresh_token: str
    id_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: int = 86400


@router.get("/", response_class=HTMLResponse)
async def auth_page(request: Request, api_service: ApiServiceDep) -> str:
    """Render the authentication page."""
    is_authenticated = api_service.is_authenticated()

    return render_page(
        title="Authentication - Yoto Up",
        content=AuthPage(is_authenticated=is_authenticated),
        request=request,
    )


@router.get("/status", response_class=HTMLResponse)
async def auth_status(request: Request, api_service: ApiServiceDep) -> str:
    """Return current authentication status as HTML partial."""
    is_authenticated = api_service.is_authenticated()

    return render_partial(AuthStatusPartial(is_authenticated=is_authenticated))


@router.post("/oauth-start", response_class=HTMLResponse)
async def start_oauth_flow(request: Request):
    """
    Start the OAuth authorization code flow.

    Redirects user to Yoto login page with authorization request.
    """
    import secrets
    from urllib.parse import urlencode

    client_id = yoto_config.CLIENT_ID

    if not client_id:
        return render_partial(
            AuthStatusPartial(
                is_authenticated=False,
                error="Client ID not configured",
            )
        )

    try:
        # Generate state token for CSRF protection
        state = secrets.token_urlsafe(32)

        # Store state in app state storage
        request.app.state.oauth_states[state] = True

        # Build authorization URL  (matching Flet app's approach)
        auth_params = {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": "http://localhost:8000/auth/oauth-callback",
            "scope": "profile offline_access",
            "audience": "https://api.yotoplay.com",
            "state": state,
        }

        auth_url = f"https://login.yotoplay.com/authorize?{urlencode(auth_params)}"
        logger.info(f"OAuth flow started, redirecting to: {auth_url}")

        # Return an HTML response that performs a redirect
        html_content = f"""
        <script>
            // Redirect to OAuth authorization endpoint
            window.location.href = '{auth_url}';
        </script>
        <p>Redirecting to Yoto login...</p>
        """
        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"Error starting OAuth flow: {e}")
        return render_partial(
            AuthStatusPartial(
                is_authenticated=False,
                error="Failed to start authentication. Please try again.",
            )
        )


@router.post("/device-code", response_class=HTMLResponse)
async def start_device_auth(request: Request, api_service: ApiServiceDep):
    """
    Start the device code authentication flow (LEGACY - use /oauth-start instead).

    Calls the real Yoto OAuth endpoint to request a device code.
    Returns HTML partial with the device code instructions.
    """
    client_id = yoto_config.CLIENT_ID

    if not client_id:
        return render_partial(
            AuthStatusPartial(
                is_authenticated=False,
                error="Client ID not configured",
            )
        )

    try:
        # Call real Yoto OAuth endpoint
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://login.yotoplay.com/oauth/device/code",
                data={
                    "client_id": client_id,
                    "scope": "profile offline_access",
                    "audience": "https://api.yotoplay.com",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

        # Parse device code response
        device_code = DeviceCodeResponse(**data)

        # Store device code in session for polling
        request.app.state.pending_device_code = device_code
        request.app.state.poll_count = 0  # Reset poll count

        logger.info(f"Device code requested: user_code={device_code.user_code}")

        return render_partial(
            DeviceCodeInstructions(
                user_code=device_code.user_code,
                verification_uri=device_code.verification_uri,
                interval=device_code.interval,
            )
        )

    except httpx.HTTPError as e:
        logger.error(f"Device code request failed: {e}")
        return render_partial(
            AuthStatusPartial(
                is_authenticated=False,
                error=f"Authentication failed: {str(e)}",
            )
        )
    except Exception as e:
        logger.error(f"Unexpected error in device code request: {e}")
        return render_partial(
            AuthStatusPartial(
                is_authenticated=False,
                error=f"Authentication failed: {str(e)}",
            )
        )


@router.post("/poll", response_class=HTMLResponse)
async def poll_device_auth(request: Request, api_service: ApiServiceDep):
    """
    Poll for device authentication completion.

    This endpoint is called via HTMX polling to check if the user
    has completed the device authentication flow on the OAuth provider.
    """
    pending = getattr(request.app.state, "pending_device_code", None)

    if not pending:
        return render_partial(
            AuthStatusPartial(
                is_authenticated=False,
                error="No pending authentication",
            )
        )

    client_id = yoto_config.CLIENT_ID

    try:
        # Call Yoto token endpoint to check if user has authenticated
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://login.yotoplay.com/oauth/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": pending.device_code,
                    "client_id": client_id,
                    "audience": "https://api.yotoplay.com",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0,
            )

            # Handle successful token response
            if response.status_code == 200:
                tokens = response.json()
                access_token = tokens.get("access_token")
                refresh_token = tokens.get("refresh_token")
                id_token = tokens.get("id_token")

                if access_token:
                    # Save tokens using the API service
                    await api_service.save_tokens(
                        access_token=access_token,
                        refresh_token=refresh_token,
                        id_token=id_token,
                    )

                    # Clear pending device code
                    request.app.state.pending_device_code = None
                    request.app.state.poll_count = 0

                    logger.info("Device authentication successful")

                    # Return success with HX-Trigger to stop polling
                    html = render_partial(
                        AuthStatusPartial(
                            is_authenticated=True,
                            message="Authentication successful!",
                        )
                    )
                    return Response(
                        content=html,
                        headers={"HX-Trigger": "auth-complete"},
                        media_type="text/html",
                    )

            # Handle OAuth error responses
            try:
                error_data = response.json()
                error_code = error_data.get("error")

                if error_code == "authorization_pending":
                    # User hasn't completed authentication yet - keep polling
                    logger.debug("Authorization pending")
                    return render_partial(
                        DeviceCodeInstructions(
                            user_code=pending.user_code,
                            verification_uri=pending.verification_uri,
                            interval=pending.interval,
                        )
                    )

                if error_code == "slow_down":
                    # Server asked us to slow down polling
                    new_interval = pending.interval + 5
                    logger.debug(f"Slow down requested, new interval: {new_interval}")
                    return render_partial(
                        DeviceCodeInstructions(
                            user_code=pending.user_code,
                            verification_uri=pending.verification_uri,
                            interval=new_interval,
                        )
                    )

                if error_code == "expired_token":
                    # Device code expired
                    logger.warning("Device code expired")
                    request.app.state.pending_device_code = None
                    return render_partial(
                        AuthStatusPartial(
                            is_authenticated=False,
                            error="Device code expired. Please start authentication again.",
                        )
                    )

                # Other OAuth error
                error_description = error_data.get("error_description", error_code)
                logger.error(f"OAuth error: {error_code} - {error_description}")
                return render_partial(
                    AuthStatusPartial(
                        is_authenticated=False,
                        error=f"Authentication error: {error_description}",
                    )
                )
            except (ValueError, KeyError):
                # Response wasn't JSON or didn't have expected fields
                logger.error(
                    f"Unexpected token response: {response.status_code} - {response.text}"
                )
                return render_partial(
                    AuthStatusPartial(
                        is_authenticated=False,
                        error="Authentication failed: Unexpected response from server",
                    )
                )

    except httpx.TimeoutException:
        logger.warning("Token polling timeout")
        # Return same instructions to continue polling
        return render_partial(
            DeviceCodeInstructions(
                user_code=pending.user_code,
                verification_uri=pending.verification_uri,
                interval=pending.interval,
            )
        )
    except httpx.HTTPError as e:
        logger.error(f"Token polling failed: {e}")
        return render_partial(
            AuthStatusPartial(
                is_authenticated=False,
                error=f"Polling failed: {str(e)}",
            )
        )
    except Exception as e:
        logger.error(f"Unexpected error during polling: {e}")
        return render_partial(
            AuthStatusPartial(
                is_authenticated=False,
                error=f"Polling failed: {str(e)}",
            )
        )


@router.post("/logout")
async def logout(request: Request, api_service: ApiServiceDep):
    """Log out and clear tokens."""
    api_service.clear_tokens()

    return Response(
        headers={
            "HX-Redirect": "/auth/",
        }
    )


@router.get("/oauth-callback")
async def oauth_callback(
    request: Request,
    api_service: ApiServiceDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """
    Handle OAuth authorization code callback from Yoto.

    Exchanges authorization code for access token.
    Redirects to home page on success, returns to auth page on error.
    """

    try:
        # Verify state token for CSRF protection
        if not state or state not in request.app.state.oauth_states:
            logger.warning("State mismatch in OAuth callback")
            return RedirectResponse(url="/auth/?error=invalid_state", status_code=302)

        # Clean up used state
        del request.app.state.oauth_states[state]

        # Handle authorization errors
        if error:
            logger.error(f"OAuth authorization error: {error}")
            error_desc = request.query_params.get("error_description", error)
            return RedirectResponse(
                url=f"/auth/?error={error}&error_description={error_desc}",
                status_code=302,
            )

        # Exchange authorization code for tokens
        if not code:
            logger.error("No authorization code in callback")
            return RedirectResponse(url="/auth/?error=no_code", status_code=302)

        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://login.yotoplay.com/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": "http://localhost:8000/auth/oauth-callback",
                    "client_id": yoto_config.CLIENT_ID,
                    "client_secret": os.getenv("YOTO_CLIENT_SECRET", ""),
                },
            )

            if token_response.status_code != 200:
                logger.error(
                    f"Token exchange failed: {token_response.status_code} - {token_response.text}"
                )
                return RedirectResponse(
                    url="/auth/?error=token_exchange_failed", status_code=302
                )

            token_data = token_response.json()
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            id_token = token_data.get("id_token")

            if not access_token:
                logger.error("No access token in response")
                return RedirectResponse(
                    url="/auth/?error=no_access_token", status_code=302
                )

            # Save tokens
            await api_service.save_tokens(access_token, refresh_token, id_token)
            logger.info("OAuth authentication successful, tokens saved")

            # Verify tokens were saved and API is initialized
            await api_service.initialize()
            is_auth = api_service.is_authenticated()
            logger.info(f"API authentication status after token save: {is_auth}")

            # Redirect to home page
            return RedirectResponse(url="/", status_code=302)

    except httpx.HTTPError as e:
        logger.error(f"HTTP error during OAuth callback: {e}")
        return RedirectResponse(url="/auth/?error=http_error", status_code=302)
    except Exception as e:
        logger.error(f"Error handling OAuth callback: {e}")
        return RedirectResponse(url="/auth/?error=callback_error", status_code=302)
