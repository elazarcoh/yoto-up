# Yoto API Client

Production-ready Python client for the Yoto API with comprehensive error handling, type safety, and clean architecture.

## Features

- **🔐 Robust Authentication**: Device code OAuth flow with automatic token refresh
- **🔄 Smart Retry Logic**: Configurable retry with exponential backoff
- **🛡️ Comprehensive Error Handling**: Specific exceptions for different error types
- **📝 Type Safety**: Full Pydantic model validation for requests and responses
- **⚡ Async/Await**: Built on httpx for efficient async operations
- **🏗️ Clean Architecture**: Separation of authentication and API operations
- **🔍 Production Ready**: Timeouts, rate limiting, proper logging

## Architecture

The client is split into two main classes:

### `YotoAuthClient`
Handles all authentication concerns:
- OAuth device code flow
- Token storage and retrieval
- Automatic token refresh
- Thread-safe token management

### `YotoApiClient`
Provides clean API for Yoto operations:
- Content management (cards/playlists)
- Media upload (audio, images, icons)
- Device management
- Automatic authentication handling

## Installation

```bash
pip install httpx pydantic loguru
```

## Quick Start

```python
import asyncio
from pathlib import Path
from yoto_up.yoto_api_client import YotoApiClient, YotoApiConfig

async def main():
    # Configure
    config = YotoApiConfig(client_id="your_client_id")
    token_file = Path.home() / ".yoto" / "tokens.json"
    
    # Use client
    async with YotoApiClient(config, token_file) as client:
        # Authenticate if needed
        if not client.is_authenticated():
            await client.authenticate()
        
        # Get content
        cards = await client.get_my_content()
        print(f"You have {len(cards)} playlists")
        
        # Create new playlist
        card = await client.create_card(title="My Playlist")
        print(f"Created: {card.title}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Configuration

```python
config = YotoApiConfig(
    client_id="your_client_id",      # Required
    base_url="https://api.yotoplay.com",  # Default
    auth_url="https://login.yotoplay.com",  # Default
    timeout=30.0,                    # Request timeout in seconds
    max_retries=3,                   # Max retry attempts
    retry_delay=1.0,                 # Initial retry delay
    retry_backoff=2.0,               # Backoff multiplier
)
```

## Error Handling

The client provides specific exceptions for different error scenarios:

```python
from yoto_up.yoto_api_client import (
    YotoApiError,         # Base exception
    YotoAuthError,        # Authentication failures
    YotoRateLimitError,   # Rate limiting
    YotoValidationError,  # Request validation errors
    YotoNotFoundError,    # Resource not found
    YotoServerError,      # Server-side errors
    YotoNetworkError,     # Network connectivity issues
    YotoTimeoutError,     # Request timeouts
)

try:
    cards = await client.get_my_content()
except YotoAuthError as e:
    print(f"Authentication failed: {e}")
except YotoRateLimitError as e:
    print(f"Rate limited, retry after {e.retry_after}s")
except YotoNotFoundError as e:
    print(f"Resource not found: {e}")
except YotoApiError as e:
    print(f"API error: {e}")
```

## API Reference

### Authentication

```python
# Device code flow
await client.authenticate(
    callback=lambda url, code: print(f"Visit {url}, code: {code}"),
    timeout=300,
)

# Check authentication status
if client.is_authenticated():
    print("Authenticated!")

# Clear tokens
client.reset_authentication()
```

### Content Management

```python
# Get all content
cards = await client.get_my_content()

# Get specific card
card = await client.get_card(card_id="abc123")

# Create card
card = await client.create_card(
    title="My Playlist",
    content={"chapters": []},
    metadata={"description": "..."},
)

# Update card
card.title = "Updated Title"
updated_card = await client.update_card(card)

# Delete card
await client.delete_card(card_id="abc123")
```

### Media Upload

```python
# Upload audio file
sha256, audio_bytes = client.calculate_sha256(Path("audio.mp3"))

# Get upload URL
upload_response = await client.get_audio_upload_url(
    sha256=sha256,
    filename="audio.mp3",
)

# Upload if needed
if upload_response.upload.upload_url:
    await client.upload_audio_file(
        upload_url=upload_response.upload.upload_url,
        audio_bytes=audio_bytes,
    )

# Wait for transcoding
transcoded = await client.poll_for_transcoding(
    upload_id=upload_response.upload.upload_id,
    loudnorm=False,
    poll_interval=2.0,
    max_attempts=60,
    callback=lambda attempt, max_attempts: print(f"{attempt}/{max_attempts}"),
)

print(f"URL: {transcoded.audio.url}")
print(f"Duration: {transcoded.audio.duration}s")

# Upload cover image
cover_response = await client.upload_cover_image(
    image_path=Path("cover.jpg"),
    autoconvert=True,
    cover_type=CoverType.SQUARE,
)

print(f"Cover URL: {cover_response.cover_image}")
```

### Device Management

```python
# Get all devices
devices = await client.get_devices()
for device in devices:
    print(f"{device.name}: {device.id}")

# Get device status
status = await client.get_device_status(device_id="xyz789")
print(f"Online: {status.online}")

# Get device config
config = await client.get_device_config(device_id="xyz789")
print(f"Volume: {config.volume}")

# Update device config
config.volume = 50
updated_config = await client.update_device_config(
    device_id="xyz789",
    name="My Yoto",
    config=config,
)
```

## Advanced Usage

### Custom HTTP Client

```python
import httpx

# Create custom client with specific settings
http_client = httpx.AsyncClient(
    timeout=60.0,
    limits=httpx.Limits(max_keepalive_connections=5),
    transport=httpx.AsyncHTTPTransport(retries=5),
)

async with YotoApiClient(config, token_file, http_client=http_client) as client:
    # Use client...
    pass
```

### Progress Callbacks

```python
# Authentication progress
def auth_callback(url: str, code: str):
    print(f"Visit: {url}")
    print(f"Code: {code}")
    
await client.authenticate(callback=auth_callback)

# Transcoding progress
def transcode_callback(attempt: int, max_attempts: int):
    percent = (attempt / max_attempts) * 100
    print(f"Transcoding: {percent:.1f}%")
    
transcoded = await client.poll_for_transcoding(
    upload_id=upload_id,
    callback=transcode_callback,
)
```

### Without Context Manager

```python
client = YotoApiClient(config, token_file)

try:
    await client.initialize()
    
    # Use client...
    cards = await client.get_my_content()
    
finally:
    await client.close()
```

## Comparison with Original Client

### Before (yoto_api.py)

```python
from yoto_up.yoto_api import YotoAPI

# Lots of optional features bundled in
api = YotoAPI(
    client_id=client_id,
    debug=True,
    cache_requests=True,
    cache_max_age_seconds=3600,
    auto_refresh_tokens=True,
)

# Sync authentication
if not api.is_authenticated():
    api.authenticate()

# Sync API calls
cards = api.get_myo_content()

# Version management mixed in
api.save_version(payload)
api.list_versions(card_id)

# Icon search features mixed in
api.search_cached_icons(query)
api.find_best_icons_for_text(text)
```

### After (yoto_api_client.py)

```python
from yoto_up.yoto_api_client import YotoApiClient, YotoApiConfig

# Clean configuration
config = YotoApiConfig(
    client_id=client_id,
    timeout=30.0,
    max_retries=3,
)

# Async context manager
async with YotoApiClient(config, token_file) as client:
    # Async authentication
    if not client.is_authenticated():
        await client.authenticate()
    
    # Async API calls
    cards = await client.get_my_content()

# Version management separated
# Icon search separated
# Focus on core API operations only
```

## Benefits

1. **Separation of Concerns**: Authentication, API operations, and utility features are separated
2. **Production Ready**: Proper timeouts, retries, error handling
3. **Type Safety**: Full Pydantic validation prevents runtime errors
4. **Async First**: Built for modern async Python applications
5. **Testable**: Clean interfaces make mocking and testing easy
6. **Maintainable**: Clear structure makes updates simple
7. **Focused**: Core API client without mixed-in utilities

## Migration Guide

If migrating from the old `YotoAPI` class:

1. **Authentication**:
   ```python
   # Old
   api = YotoAPI(client_id, auto_start_authentication=True)
   
   # New
   async with YotoApiClient(config, token_file) as client:
       await client.authenticate()
   ```

2. **Getting Content**:
   ```python
   # Old
   cards = api.get_myo_content()
   
   # New
   cards = await client.get_my_content()
   ```

3. **Creating Cards**:
   ```python
   # Old
   response = api.create_or_update_content(card, return_card=True)
   
   # New
   card = await client.create_card(title="...", content={...})
   ```

4. **Error Handling**:
   ```python
   # Old
   try:
       cards = api.get_myo_content()
   except Exception as e:
       print(f"Error: {e}")
   
   # New
   try:
       cards = await client.get_my_content()
   except YotoNotFoundError:
       print("Not found")
   except YotoAuthError:
       print("Auth failed")
   except YotoApiError as e:
       print(f"API error: {e}")
   ```

## License

Same as yoto-up project
