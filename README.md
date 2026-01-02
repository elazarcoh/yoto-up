# Yoto Web Server

A standalone FastAPI-based web server for managing Yoto cards and playlists.

## Features

- 🎵 **Playlist Management** - View, create, edit, and delete playlists
- 🎨 **Icon Browser** - Browse and assign icons to chapters and tracks
- 📱 **Device Control** - Monitor and control Yoto devices
- 🔐 **Session-Based Auth** - Secure OAuth authentication with Yoto

## Quick Start

### Using uv (recommended)

```bash
# Clone and navigate to the directory
cd yoto-web-server

# Create virtual environment and install dependencies
uv sync

# Set encryption key for session cookies
export SESSION_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Run the server
uv run yoto-server --reload
```

### Using Docker

```bash
# Build and run with docker-compose
docker-compose up --build

# Or build manually
docker build -t yoto-web-server .
docker run -p 8000:8000 -e SESSION_ENCRYPTION_KEY=your-key yoto-web-server
```

### Development Container

Open in VS Code with the Dev Containers extension for a fully configured development environment.

## Configuration

Environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `SESSION_ENCRYPTION_KEY` | Fernet key for cookie encryption | Yes |
| `YOTO_UP_DEBUG` | Enable debug mode (`true`/`false`) | No |
| `YOTO_UP_DEBUG_DIR` | Directory for debug output | No |
| `HOST` | Server host (default: `0.0.0.0`) | No |
| `PORT` | Server port (default: `8000`) | No |

## Project Structure

```
yoto-web-server/
├── src/
│   └── yoto_web_server/
│       ├── api/              # Yoto API client
│       ├── core/             # Configuration, security
│       ├── middleware/       # Session handling
│       ├── routers/          # FastAPI routes
│       ├── services/         # Business logic
│       ├── templates/        # PyDOM components
│       └── utils/            # Helpers
├── tests/
├── .devcontainer/
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## License

MIT License - See [LICENSE](LICENSE) for details.
