"""
Dependency Injection Container using dependency-injector.

This module sets up the DI container for managing service dependencies.
"""

import os
from pathlib import Path
from dependency_injector import containers, providers

from yoto_up_server.services.api_service import ApiService
from yoto_up_server.services.audio_processor import AudioProcessorService
from yoto_up_server.services.icon_service import IconService
from yoto_up_server.services.upload_manager import UploadManager
from yoto_up_server.services.upload_session_service import UploadSessionService
from yoto_up_server.services.upload_processing_service import UploadProcessingService


def init_upload_processing_service(
    api_service: ApiService,
    audio_processor: AudioProcessorService,
    upload_session_service: UploadSessionService,
):
    service = UploadProcessingService(
        api_service=api_service,
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
            "yoto_up_server.routers.cards",
            "yoto_up_server.routers.icons",
            "yoto_up_server.routers.playlists",
            "yoto_up_server.routers.upload",
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
    api_service = providers.Singleton(ApiService)
    
    audio_processor = providers.Factory(
        AudioProcessorService,
        debug_enabled=debug_enabled,
        debug_dir=debug_dir,
    )

    icon_service = providers.Singleton(
        IconService,
        api_service=api_service,
    )

    upload_manager = providers.Singleton(
        UploadManager,
        api_service=api_service,
        audio_processor=audio_processor,
    )

    upload_session_service = providers.Singleton(
        UploadSessionService,
    )

    upload_processing_service = providers.Resource(
        init_upload_processing_service,
        api_service=api_service,
        audio_processor=audio_processor,
        upload_session_service=upload_session_service,
    )
