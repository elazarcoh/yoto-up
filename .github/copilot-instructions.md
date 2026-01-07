# Yoto Web Server - AI Coding Instructions

## Project Overview
This is a standalone FastAPI web server for managing Yoto cards and playlists.
- **Framework:** FastAPI (Python 3.13+)
- **Package Manager:** `uv` (replaces pip/poetry)
- **Architecture:** Service-oriented with Dependency Injection (`dependency-injector`)
- **Frontend:** Server-Side Rendered (SSR) using `pydom` (Python-to-HTML), `HTMX` for dynamic interactions, `Alpine.js` for client-side state, and `Tailwind CSS` (via CDN).

## Core Architecture

### Dependency Injection
- **Container:** Defined in `src/yoto_web_server/container.py`.
- **Wiring:** Modules are wired in `src/yoto_web_server/main.py` (lifespan) and `container.py` (wiring_config).
- **Usage:** Inject services into routers using `dependency_injector.wiring.Provide` and `FastAPI.Depends`.
- **Pattern:**
  ```python
  from dependency_injector.wiring import inject, Provide
  from fastapi import Depends
  from yoto_web_server.container import Container

  @router.get("/")
  @inject
  async def endpoint(
      service: Service = Depends(Provide[Container.service_name])
  ): ...
  ```

### UI & Templating (`pydom`)
- **No HTML files:** All UI is built in Python using `pydom`.
- **Components:** Located in `src/yoto_web_server/templates/`. Inherit from `pydom.Component`.
- **HTMX:** Use the `htmx` helper from `yoto_web_server.utils.setup_htmx`.
  - Example: `d.Button(htx_get="/url")("Click Me")`
- **Tailwind V4:** Use `classes="..."` prop on elements.
- **Structure:** `render_page` in `templates/base.py` wraps content in the main layout.

### Services
- **Session Management:** `SessionService` handles encrypted cookies.
- **API Client:** `YotoApiClient` wraps external Yoto API calls with auth context. Get it like this:
  ```python
  @router.get("/some-endpoint")
  @inject
  async def some_endpoint(
      client: YotoApiDep
  ): ...
  ```
- **Background Tasks:** `UploadProcessingService` handles long-running audio processing.
- **Audio:** `AudioProcessorService` uses `ffmpeg` and `pydub` for normalization.

## Local Development Workflow

### Commands (using `uv`)
- **Start Server:** `uv run yoto-server serve --reload`
- **Run Tests:** `uv run pytest`
- **Lint:** `uv run ruff check src/yoto_web_server`
- **Format:** `uv run ruff format src/yoto_web_server`
- **Type Check:** `uv run mypy src/yoto_web_server`

### Using docker-compose
- **Start Dev Environment:** `docker compose up yoto-web-server-dev --watch`

### Configuration
- **Settings:** Managed via `pydantic-settings` in `src/yoto_web_server/core/config.py`.
- **Env Vars:** `SESSION_ENCRYPTION_KEY` is critical for session management.

## Key Conventions
1.  **Async First:** All I/O (DB, API, File) must be async.
2.  **Type Hints:** Strict typing required (checked by mypy).
3.  **Logging:** Use `loguru` (`from loguru import logger`).
4.  **Error Handling:** Use `FastAPI.HTTPException` in routers; custom exceptions in services.
5.  **Path Handling:** Use `pathlib.Path` for all file operations.
6.  **Browser Verification (MCP):** Use the `playwright` MCP to verify implementations across all relevant flows.
7.  **Authentication During Browser Verification:** If authentication is required, you should try to authenticate (click on the relevant UI element). It is expected that the browser will automate the login process, so copilot should just click on any element that relates to authentication (e.g. "Start Authentication").

## Important development practices

* Always test the changes using the playwright mcp tool. 
