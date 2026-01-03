"""
Dependency Injection Container using dependency-injector.

Manages all service dependencies for the application.
"""

from dependency_injector import containers, providers

from yoto_web_server.core.config import get_settings
from yoto_web_server.features.example_feature_b import ExampleFeatureB
from yoto_web_server.features.youtube.service import YouTubeFeature
from yoto_web_server.services.audio_processor import AudioProcessorService
from yoto_web_server.services.icon_service import IconService
from yoto_web_server.services.mqtt_service import MqttService
from yoto_web_server.services.optional_features_service import (
    OptionalFeaturesService,
)
from yoto_web_server.services.session_aware_api_service import SessionAwareApiService
from yoto_web_server.services.session_service import SessionService
from yoto_web_server.services.upload_orchestrator_service import UploadOrchestrator
from yoto_web_server.services.upload_processing_service import UploadProcessingService
from yoto_web_server.services.upload_session_service import UploadSessionService


def get_encryption_key() -> bytes:
    """Get encryption key for session cookies."""
    settings = get_settings()
    return settings.get_encryption_key()


def init_upload_processing_service(
    audio_processor: AudioProcessorService,
    upload_session_service: UploadSessionService,
    session_aware_api_service: SessionAwareApiService,
):
    service = UploadProcessingService(
        audio_processor=audio_processor,
        upload_session_service=upload_session_service,
        session_aware_api_service=session_aware_api_service,
    )
    service.start()
    yield service
    service.stop()


class Container(containers.DeclarativeContainer):
    """Application DI container."""

    wiring_config = containers.WiringConfiguration(
        modules=[
            "yoto_web_server.routers.auth",
            "yoto_web_server.routers.icons",
            "yoto_web_server.routers.playlists",
            "yoto_web_server.routers.devices",
            "yoto_web_server.routers.optional_features",
            "yoto_web_server.features.youtube.routes",
            "yoto_web_server.dependencies",
            "yoto_web_server.middleware.session_middleware",
        ]
    )

    # Configuration
    config = providers.Configuration()

    # Debug configuration
    debug_enabled = providers.Singleton(lambda: get_settings().yoto_up_debug)

    debug_dir = providers.Singleton(lambda: get_settings().yoto_up_debug_dir)

    # Core services
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
        session_aware_api_service=session_aware_api_service,
    )

    # Upload orchestrator for unified file and URL handling
    upload_orchestrator = providers.Singleton(
        UploadOrchestrator,
        upload_session_service=upload_session_service,
        upload_processing_service=upload_processing_service,
    )

    mqtt_service = providers.Singleton(
        MqttService,
        api_service=session_aware_api_service,
    )

    example_feature_b = providers.Singleton(
        ExampleFeatureB,
        available=True,  # Toggle this to True to simulate feature available
    )

    optional_features_service = providers.Singleton(
        OptionalFeaturesService,
    )

    # YouTube feature service
    youtube_feature = providers.Singleton(
        YouTubeFeature,
    )
