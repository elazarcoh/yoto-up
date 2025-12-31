# Build stage
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies
# Copy lockfile and pyproject.toml first to leverage cache
COPY pyproject.toml uv.lock ./

# Install dependencies without the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-editable

# Copy the project source code
COPY README.md ./
COPY src/ ./src/

# Install the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable

# Runtime stage
FROM python:3.13-slim-bookworm

# Create a non-root user
RUN useradd -m -r app

WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV YOTO_WEB_HOST=0.0.0.0
ENV YOTO_WEB_PORT=8000
# Configure app paths to use writable directories
ENV CACHE_DIR=/app/cache
ENV DATA_DIR=/app/data

# Create necessary directories and set permissions
RUN mkdir -p /app/cache /app/data && \
    chown -R app:app /app/cache /app/data

# Switch to the non-root user
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "-m", "yoto_web_server.cli", "serve", "--host", "0.0.0.0", "--no-reload", "--no-browser"]
