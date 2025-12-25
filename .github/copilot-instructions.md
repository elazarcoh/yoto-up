# Yoto Up - AI Coding Agent Instructions

## Project Overview

**Yoto Up** is a multipurpose tool for managing Yoto card content (audio playlists) with three interfaces:
- **CLI** (Typer + Rich) - command-line tools
- **TUI** (Textual) - terminal user interface  
- **Web Server** (FastAPI + pydom) - browser-based interface for playlists, cards, uploads, icons

---

## Architecture Patterns

### 1. **Session-Based Authentication (No Disk Tokens)**
- **Location**: `src/yoto_up_server/middleware/session_middleware.py` + `services/session_*.py`
- **Pattern**: Session middleware sets context variables (`_session_id_context`) and `request.state.session_id` for each request
- **Key Classes**:
  - `SessionService`: In-memory session storage + cookie encryption
  - `SessionAwareApiService`: Proxy service that wraps `YotoApiClient` per-session
  - The service's `_current_session_id` attribute gets set by `require_session_auth` dependency
- **Cookie Details**: `"yoto_session"` (encrypted, HTTPOnly, SameSite=lax, 30-day TTL)
- **Auto-refresh**: Access tokens refresh via refresh tokens from cookies when expired

### 2. **Dependency Injection with dependency-injector**
- **Location**: `src/yoto_up_server/container.py` + `dependencies.py`
- **Pattern**: `Container` class manages all service singletons; wired into routers + middleware
- **Usage in Routes**: Annotated type hints like `SessionAwareApiServiceDep`, `ContainerDep`
  ```python
  async def playlists_page(request: Request, session_api: AuthenticatedSessionApiDep):
      # session_api is auto-injected and already has current_session_id set
  ```
- **Wired Modules**: auth, cards, icons, playlists, upload, dependencies, session_middleware

### 3. **Component-Based HTML Rendering with pydom**
- **Location**: `src/yoto_up_server/templates/`
- **Pattern**: Extend `pydom.Component` class, implement `render()` returning `pydom.html` (aliased `d`)
  ```python
  class MyComponent(Component):
      def render(self):
          return d.Div(classes="...tailwind classes...")(
              d.H1()("Title"),
              d.P()("Content"),
          )
  ```
- **Rendering**: `render_page(title, content, request)` wraps in `BaseLayout` + auto-detects auth state
- **HTMX Integration**: `hx_post="/endpoint"`, `hx_target="#id"`, `hx_swap="innerHTML"` for dynamic updates
- **Auth Detection**: `render_page()` checks `request.state.session_id` → validates session → passes `is_authenticated` to `BaseLayout`

### 4. **Router Organization**
- **Pattern**: One router per feature (playlists, cards, icons, upload, auth)
- **Response Types**: HTML pages via `render_page()` or HTML partials via `render_partial()` for HTMX
- **Protected Routes**: Require `AuthenticatedSessionApiDep` in function signature (dependency validates auth or raises `AuthenticationError`)

### 5. **API Client Wrapping**
- **YotoApiClient** (`src/yoto_up/yoto_api_client.py`): Direct API calls (get_my_content, create_card, upload_audio, etc.)
- **SessionAwareApiService**: Per-session wrapper around YotoApiClient
  - Methods: `get_my_content()`, `get_card()`, `create_card()`, `update_card()`, `delete_card()`, etc.
  - All methods use `self._get_session_id()` to resolve session → get session object → create/reuse API client
  - **Critical**: Use yoto_client from dependency injection, **not** creating YotoApiClient directly.

---

## Common Workflows

### Adding a New Route/Page
1. Create component class in `templates/feature.py` extending `Component`
2. Create router in `routers/feature.py`, import dependencies + components
3. Define route: `@router.get("/", response_class=HTMLResponse)` → call `render_page(title, ComponentClass(), request)`
4. For authenticated routes: Add `session_api: AuthenticatedSessionApiDep` parameter
5. For HTMX updates: Return `render_partial(component)` instead of `render_page()`

### Authentication Flow
1. User clicks "Start Authentication" → POST `/auth/oauth-start`
2. Server redirects to Yoto OAuth → user signs in → returns to `/auth/callback?code=...`
3. Exchange code for tokens → create session → set encrypted cookie → redirect to `/playlists/`
4. Middleware validates cookie on each request → sets `request.state.session_id`
5. Auto-refresh: If access token expired, middleware refreshes via refresh token

### Making API Calls
```python
# ✅ CORRECT: Use YotoApiDep which has session context
cards = await yoto_client.get_my_content()  # Gets current session, creates client, calls API
```

### Testing Authentication State
```python
# In render_page(), auto-detects if user is authenticated and passes to BaseLayout
# Navigation component conditionally shows "Logout" vs "Login"
```

---

## Project-Specific Conventions

### Python/Code Style
- **Type Hints**: Full type hints required (pydantic models, Optional, Union, etc.)
- **Async/Await**: All I/O operations are async (FastAPI + httpx)
- **Logging**: Use `from loguru import logger` → `logger.info(msg)`, `logger.error(msg)`
- **Error Handling**: `AuthenticationError` for auth failures, caught by middleware

### HTML/CSS  
- **Tailwind CSS v4** (CDN from cdn.jsdelivr.net)
- **No inline styles** — all via Tailwind classes
- **Example**: `d.Div(classes="max-w-md mx-auto bg-white shadow rounded-lg p-8")(children)`

### Environment Setup
- **Python 3.13+** required
- **For server dev**: use `uv` for virtual env management
- **Key env vars**: `SESSION_ENCRYPTION_KEY` (required, Fernet key), `.env` file or export
- **Debug mode**: `YOTO_UP_DEBUG=true` enables debug logging

#### Running the Server

**Use VS Code Tasks instead of terminal commands** - this prevents server interruption when editing files:

1. **Open Tasks**: `Ctrl+Shift+D` → select "Start Yoto Server (with reload)" or use `Terminal > Run Task`
2. **Available Tasks** in `.vscode/tasks.json`:
   - **Start Yoto Server (with reload)** - Hot reload enabled, auto-restarts on code changes
   - **Start Yoto Server (no reload)** - Stable run without auto-restart
   - **Start Yoto Server (debug mode)** - With reload + debug output directory
   - **Kill Yoto Server processes** - Force stop all Python processes

**Why tasks?** The task runner maintains the server process independently from your editor, preventing accidental kills when you reload/restart VS Code.

**Manual start** (if not using tasks):
```bash
# Set encryption key first
$env:SESSION_ENCRYPTION_KEY = (python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Start server with reload
uv run python src/yoto_up_server/cli.py --reload --no-browser
```

### File Structure
```
src/
  yoto_up/           # Core Yoto API client + models
    yoto_api_client.py
    models.py        # Card, Track, Chapter pydantic models
  yoto_up_server/    # FastAPI web server
    main.py          # Entry point
    container.py     # DI setup
    middleware/      # Session + CSRF middleware
    services/        # Business logic (session, API wrapper, upload, icon)
    routers/         # API routes
    templates/       # HTML components (pydom)
    dependencies.py  # Dependency injection helpers
```

---

## Critical Integration Points

### Session Lifecycle
- **Create**: `SessionService.create_session(access_token, refresh_token)` → returns session_id + encrypted payload
- **Validate**: `SessionService.validate_and_decrypt_cookie(cookie_value)` → CookiePayload
- **Rehydrate**: If cookie exists but session not in memory (server restart), `session_api_service.rehydrate_session_from_cookie()`
- **Logout**: `session_api_service.logout_session(session_id)` → deletes from memory + clears cookie

### API Client Reuse
- `SessionAwareApiService._api_clients[session_id]` caches per-session YotoApiClient
- Token is manually set on client via `client.auth._token_data = TokenData(...)`
- Temp token files created in system temp dir but not persisted

### Middleware Flow
1. SessionMiddleware.dispatch: Extract cookie → validate → set request.state + context var
2. Route handler: Dependency `AuthenticatedSessionApiDep` calls `require_session_auth()`
3. `require_session_auth()`: Validates session + refreshes token if expired → sets `session_api.set_current_session_id()`
4. Handler calls `session_api` methods → all use current session context

---

## Common Pitfalls to Avoid

1. **Forgetting `await`** on async API calls (`get_my_content()`, `create_card()`, etc.)
2. **Passing explicit session_id** when using proxy methods — let `_get_session_id()` handle it via context
3. **Hardcoding cookie name** — always import `SESSION_COOKIE_NAME` from `session_middleware`
4. **Missing type hints** on route handlers — dependency injection relies on type annotations
5. **Not checking `is_authenticated`** in `render_page()` call — auth detection is automatic but must pass `request`
6. **Mixing pydom component names** — use `d.Div()` not `d.div()` (case-sensitive)
7. **HTMX swap strategies** — use `hx_swap="innerHTML"` for partial updates, not `hx_swap="outerHTML"`

---

## Debugging Tips

- **Server logs**: Check stdout for loguru output (session rehydration, API client creation, auth flows)
- **Browser DevTools**: Check cookies (yoto_session should be present after login), Network tab for HTMX requests
- **Session state**: Add `logger.debug(f"Session: {request.state.session_id}")` in routes
- **API errors**: SessionAwareApiService logs token refresh failures → check if refresh token is expired

---

## Key Files to Reference

| File | Purpose |
|------|---------|
| `services/session_service.py` | Session storage + cookie encryption |
| `services/session_aware_api_service.py` | Per-session API wrapper |
| `middleware/session_middleware.py` | Cookie validation + context setup |
| `dependencies.py` | Dependency injection helpers |
| `routers/auth.py` | OAuth flow + login/logout |
| `templates/base.py` | Navigation + layout (shows auth state) |
| `container.py` | DI container setup |
