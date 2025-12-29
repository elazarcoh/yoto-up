"""
Dependency Injection Container using dependency-injector.

This module sets up the DI container for managing service dependencies.
"""

import os
from pathlib import Path
from dependency_injector import containers, providers

from yoto_up_server.services.session_service import SessionService
from yoto_up_server.services.session_aware_api_service import SessionAwareApiService
from yoto_up_server.services.audio_processor import AudioProcessorService
from yoto_up_server.services.icon_service import IconService
from yoto_up_server.services.upload_session_service import UploadSessionService
from yoto_up_server.services.upload_processing_service import UploadProcessingService
from yoto_up_server.services.mqtt_service import MqttService


def get_encryption_key() -> bytes:
    """
    Get encryption key for session cookies.

    In production, this should be loaded from environment variable.
    For development, generate a key (sessions won't survive restart).
    """
    key_env = os.getenv("SESSION_ENCRYPTION_KEY")
    if key_env:
        # Key must be 32 url-safe base64-encoded bytes
        return key_env.encode("utf-8")

    raise RuntimeError(
        "No SESSION_ENCRYPTION_KEY set in environment - cannot start server!"
    )


def init_upload_processing_service(
    audio_processor: AudioProcessorService,
    upload_session_service: UploadSessionService,
):
    service = UploadProcessingService(
        audio_processor=audio_processor,
        upload_session_service=upload_session_service,
    )
    service.start()
    yield service
    service.stop()


class Container(containers.DeclarativeContainer):
    """Application DI container."""

    wiring_config = containers.WiringConfiguration(
        modules=[
            "yoto_up_server.routers.auth",
            "yoto_up_server.routers.icons",
            "yoto_up_server.routers.playlists",
            "yoto_up_server.routers.devices",
            "yoto_up_server.dependencies",
            "yoto_up_server.middleware.session_middleware",
        ]
    )

    # Configuration
    config = providers.Configuration()

    # Debug configuration
    debug_enabled = providers.Singleton(
        lambda: os.getenv("YOTO_UP_DEBUG", "").lower() == "true"
    )

    debug_dir = providers.Singleton(
        lambda: Path(os.getenv("YOTO_UP_DEBUG_DIR", "./debug"))
    )

    # Services - Singletons
    # Session services
    encryption_key = providers.Singleton(get_encryption_key)

    session_service = providers.Singleton(
        SessionService,
        encryption_key=encryption_key,
    )

    session_aware_api_service = providers.Singleton(
        SessionAwareApiService,
        session_service=session_service,
    )

    audio_processor = providers.Factory(
        AudioProcessorService,
        debug_enabled=debug_enabled,
        debug_dir=debug_dir,
    )

    icon_service = providers.Singleton(
        IconService,
    )

    upload_session_service = providers.Singleton(
        UploadSessionService,
    )

    upload_processing_service = providers.Resource(
        init_upload_processing_service,
        audio_processor=audio_processor,
        upload_session_service=upload_session_service,
    )

    mqtt_service = providers.Singleton(
        MqttService,
        api_service=session_aware_api_service,
    )
