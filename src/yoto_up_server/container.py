"""
Dependency Injection Container using dependency-injector.

This module sets up the DI container for managing service dependencies.
"""

from dependency_injector import containers, providers

from yoto_up_server.services.api_service import ApiService
from yoto_up_server.services.audio_processor import AudioProcessorService
from yoto_up_server.services.icon_service import IconService
from yoto_up_server.services.upload_manager import UploadManager
from yoto_up_server.services.upload_session_service import UploadSessionService
from yoto_up_server.services.upload_processing_service import UploadProcessingService


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

    # Services - Singletons
    api_service = providers.Singleton(ApiService)
    
    audio_processor = providers.Factory(
        AudioProcessorService,
        target_level=config.audio.target_level.as_float(),
        true_peak=config.audio.true_peak.as_float(),
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

    upload_processing_service = providers.Singleton(
        UploadProcessingService,
        api_service=api_service,
        audio_processor=audio_processor,
        upload_session_service=upload_session_service,
    )
